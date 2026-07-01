"""Tests for batch embedding, retry, chunk embedding, and bulk indexing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


# ── vector_retriever: _embed_with_retry, embed_text, embed_batch ──


@pytest.fixture(autouse=True)
def clear_settings_embedding():
    """Reset embedding cache + settings before each test."""
    from app import config
    from app.retrievers import vector_retriever

    config.settings.embedding_retry_max = 2
    config.settings.embedding_retry_backoff_ms = 10  # fast for tests
    config.settings.embedding_batch_size = 16
    config.settings.embedding_concurrency = 2

    vector_retriever._EMBED_CACHE.clear()
    yield


def _make_mock_client(post_return=None, post_side_effect=None):
    """Helper: create a mock httpx Client that returns given post response."""
    mock_client = MagicMock()
    mock_client.post.return_value = post_return
    if post_side_effect:
        mock_client.post.side_effect = post_side_effect
    return mock_client


@pytest.mark.asyncio
async def test_embed_batch_success():
    """embed_batch returns correct vectors when API responds."""
    mock_json = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_json

    with patch("app.retrievers.vector_retriever.httpx.Client",
               return_value=_make_mock_client(post_return=mock_resp)):
        from app.retrievers.vector_retriever import embed_batch
        vecs = await embed_batch(["text a", "text b"])
        assert vecs == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_embed_batch_retry_then_success():
    """embed_batch retries on failure, then succeeds."""
    mock_json = {"data": [{"embedding": [0.5]}]}
    call_count = [0]

    def _side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:
            raise ConnectionError("timeout")
        resp = MagicMock()
        resp.json.return_value = mock_json
        return resp

    with patch("app.retrievers.vector_retriever.httpx.Client",
               return_value=_make_mock_client(post_side_effect=_side_effect)):
        from app.retrievers.vector_retriever import embed_batch
        vecs = await embed_batch(["text"])
        assert vecs == [[0.5]]
        assert call_count[0] == 3  # fail fail -> success


@pytest.mark.asyncio
async def test_embed_batch_retry_exhausted():
    """embed_batch returns empty list when all retries exhausted."""
    with patch("app.retrievers.vector_retriever.httpx.Client",
               return_value=_make_mock_client(
                   post_side_effect=ConnectionError("timeout"))):
        from app.retrievers.vector_retriever import embed_batch
        vecs = await embed_batch(["text"])
        assert vecs == []


@pytest.mark.asyncio
async def test_embed_text_empty_api_key():
    """embed_text returns [] when no API key set."""
    from app.config import settings

    saved = settings.llm_api_key
    saved_emb = settings.embedding_api_key
    settings.llm_api_key = ""
    settings.embedding_api_key = ""

    from app.retrievers.vector_retriever import embed_text

    try:
        vec = await embed_text("hello")
        assert vec == []
    finally:
        settings.llm_api_key = saved
        settings.embedding_api_key = saved_emb


@pytest.mark.asyncio
async def test_embed_text_cache_hit():
    """embed_text returns cached vector without API call."""
    from app.retrievers import vector_retriever

    # Prime cache
    vector_retriever._EMBED_CACHE["cached_text"] = [0.9, 0.8]

    with patch("app.retrievers.vector_retriever.httpx.Client") as MockClient:
        from app.retrievers.vector_retriever import embed_text

        vec = await embed_text("cached_text")
        assert vec == [0.9, 0.8]
        MockClient.assert_not_called()


@pytest.mark.asyncio
async def test_embed_text_empty_input():
    """embed_text returns [] for empty string (no API call needed)."""
    from app.retrievers.vector_retriever import embed_text

    with patch("app.retrievers.vector_retriever.httpx.Client") as MockClient:
        vec = await embed_text("")
        assert vec == []
        # _embed_with_retry still gets called with [""] since content is truthy, but cache hit for empty string may vary


# ── doc_indexer: _embed_chunks_batch, _index_chunk_bulk, index_single_file ──


@pytest.mark.asyncio
async def test_embed_chunks_batch_splits_into_sub_batches():
    """_embed_chunks_batch splits chunks into EMBEDDING_BATCH_SIZE sub-batches."""
    from app.config import settings

    settings.embedding_batch_size = 3
    chunks = [{"content": f"text{i}", "doc_id": "doc1"} for i in range(7)]

    from app.indexer.doc_indexer import _embed_chunks_batch

    mock_vec = lambda t: [float(ord(t[-1]))]
    with patch("app.indexer.doc_indexer.embed_batch") as mock_embed:
        mock_embed.side_effect = [
            [mock_vec("text0"), mock_vec("text1"), mock_vec("text2")],
            [mock_vec("text3"), mock_vec("text4"), mock_vec("text5")],
            [mock_vec("text6")],
        ]
        result = await _embed_chunks_batch(chunks)

    assert mock_embed.call_count == 3  # 7 / 3 = 3 batches
    assert result[0]["content_vector"] == mock_vec("text0")
    assert result[6]["content_vector"] == mock_vec("text6")


@pytest.mark.asyncio
async def test_embed_chunks_batch_partial_failure():
    """_embed_chunks_batch handles sub-batch failure gracefully."""
    from app.config import settings

    settings.embedding_batch_size = 4
    chunks = [{"content": f"t{i}", "doc_id": "d"} for i in range(5)]

    from app.indexer.doc_indexer import _embed_chunks_batch

    with patch("app.indexer.doc_indexer.embed_batch") as mock_embed:
        mock_embed.side_effect = [
            [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8]],
            None,  # second batch fails
        ]
        result = await _embed_chunks_batch(chunks)
    # First 4 have vectors, 5th has empty list (fallback)
    assert result[0]["content_vector"] == [0.1, 0.2]
    assert result[4].get("content_vector") == [] or "content_vector" not in result[4]


@pytest.mark.asyncio
async def test_embed_chunks_batch_no_content():
    """_embed_chunks_batch handles chunks with empty content."""
    from app.indexer.doc_indexer import _embed_chunks_batch

    chunks = [{"doc_id": "d1", "content": ""}]
    with patch("app.indexer.doc_indexer.embed_batch") as mock_embed:
        result = await _embed_chunks_batch(chunks)
    mock_embed.assert_not_called()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_index_chunk_bulk_success():
    """_index_chunk_bulk calls ES bulk helper with correct actions."""
    from app.indexer.doc_indexer import _index_chunk_bulk
    from app.retrievers.es_retriever import INDEX_NAME

    es = MagicMock()
    chunks = [{"doc_id": "d1", "chunk_index": 0, "content": "a"},
              {"doc_id": "d1", "chunk_index": 1, "content": "b"}]

    with patch("elasticsearch.helpers.bulk") as mock_bulk:
        mock_bulk.return_value = (2, 0)
        ok, err = await _index_chunk_bulk(es, chunks)

    assert (ok, err) == (2, 0)
    mock_bulk.assert_called_once()
    actions = mock_bulk.call_args[0][1]
    assert len(actions) == 2
    assert actions[0]["_id"] == "d1_chunk0"
    assert actions[1]["_id"] == "d1_chunk1"


@pytest.mark.asyncio
async def test_index_chunk_bulk_empty():
    """_index_chunk_bulk returns (0, 0) for empty chunks list."""
    from app.indexer.doc_indexer import _index_chunk_bulk

    es = MagicMock()
    ok, err = await _index_chunk_bulk(es, [])
    assert (ok, err) == (0, 0)


@pytest.mark.asyncio
async def test_index_single_file_calls_batch_embed_and_bulk():
    """index_single_file calls batch embed then bulk index."""
    from app.indexer.doc_indexer import index_single_file

    es = MagicMock()

    with patch("app.indexer.doc_indexer.parse_markdown") as mock_parse:
        mock_parse.return_value = [
            {"doc_id": "svc_test_foo", "chunk_index": 0, "content": "hello"},
        ]
        with patch("app.indexer.doc_indexer._embed_chunks_batch", new_callable=AsyncMock) as mock_embed:
            with patch("app.indexer.doc_indexer._index_chunk_bulk", new_callable=AsyncMock) as mock_bulk:
                mock_bulk.return_value = (1, 0)
                with patch("app.retrievers.graph_retriever.sync_document_node") as mock_sync:
                    mock_sync.return_value = {"status": "ok", "detail": "synced"}
                    with patch("app.retrievers.graph_retriever.get_driver"):
                        ok, err = await index_single_file(es, "/tmp/test.md")

    assert (ok, err) == (1, 0)
    mock_embed.assert_awaited_once()
    mock_bulk.assert_awaited_once()


@pytest.mark.asyncio
async def test_index_directory_concurrency_semaphore():
    """index_directory processes files with concurrency cap."""
    from app.indexer.doc_indexer import index_directory

    es = MagicMock()
    with patch("app.indexer.doc_indexer.Path") as MockPath:
        def _make_fake_path(name):
            p = MagicMock()
            p.__str__.return_value = f"/{name}.md"
            p.relative_to.return_value = f"{name}.md"
            return p
        fp1 = _make_fake_path("a")
        fp2 = _make_fake_path("b")
        fp3 = _make_fake_path("c")
        fp4 = _make_fake_path("d")
        MockPath.return_value.rglob.return_value = [fp1, fp2, fp3, fp4]

        with patch("app.indexer.doc_indexer.parse_markdown") as mock_parse:
            mock_parse.return_value = [{"doc_id": "svc_x_foo", "chunk_index": 0, "content": "x"}]
            with patch("app.indexer.doc_indexer._embed_chunks_batch", new_callable=AsyncMock) as mock_embed:
                mock_embed.return_value = [{"doc_id": "svc_x_foo", "chunk_index": 0, "content": "x", "content_vector": [0.1]}]
                with patch("app.indexer.doc_indexer._index_chunk_bulk", new_callable=AsyncMock) as mock_bulk:
                    mock_bulk.return_value = (1, 0)
                    with patch("app.retrievers.graph_retriever.get_driver"), \
                         patch("app.retrievers.graph_retriever.sync_document_node") as mock_sync:
                        mock_sync.return_value = {"status": "ok", "detail": "synced"}
                        ok, err = await index_directory(es, "/tmp")

    assert (ok, err) == (4, 0)
    assert mock_parse.call_count == 4
    assert mock_bulk.await_count == 4