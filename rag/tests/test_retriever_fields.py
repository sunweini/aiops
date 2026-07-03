"""Test that vector and ES retrievers return expected fields."""
import pytest
from unittest.mock import MagicMock


class TestVectorRetrieverFields:
    @pytest.mark.asyncio
    async def test_search_vector_returns_service_ids(self):
        """search_vector must return service_ids array field."""
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.85,
                        "_source": {
                            "title": "test doc",
                            "content": "test content",
                            "doc_type": "sop",
                            "service_ids": ["svc_es", "svc_nginx"],
                            "tags": ["es", "9200"],
                            "chunk_type": "child",
                            "parent_id": "parent_123",
                            "doc_id": "doc_42",
                        }
                    }
                ]
            }
        }

        from app.retrievers.vector_retriever import search_vector
        with pytest.MonkeyPatch.context() as m:
            m.setattr("app.retrievers.vector_retriever.embed_text",
                       __import__("asyncio").coroutine(lambda x: [0.1] * 4096))
            results = await search_vector(mock_es, "test query", top_k=5)

        assert len(results) == 1
        r = results[0]
        assert "service_ids" in r, f"Missing service_ids in vector result: {r.keys()}"
        assert r["service_ids"] == ["svc_es", "svc_nginx"]
        assert "tags" in r
        assert r["tags"] == ["es", "9200"]
        assert "chunk_type" in r
        assert r["chunk_type"] == "child"
        assert "parent_id" in r
        assert r["parent_id"] == "parent_123"
        assert "doc_id" in r
        assert r["doc_id"] == "doc_42"
        assert r["engine"] == "vector"

    @pytest.mark.asyncio
    async def test_search_vector_defaults_when_fields_missing(self):
        """search_vector must default missing fields to empty values."""
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.5,
                        "_source": {
                            "title": "minimal doc",
                            "content": "bare minimum",
                        }
                    }
                ]
            }
        }

        from app.retrievers.vector_retriever import search_vector
        with pytest.MonkeyPatch.context() as m:
            m.setattr("app.retrievers.vector_retriever.embed_text",
                       __import__("asyncio").coroutine(lambda x: [0.1] * 4096))
            results = await search_vector(mock_es, "test query", top_k=5)

        assert len(results) == 1
        r = results[0]
        assert r["service_ids"] == []
        assert r["tags"] == []
        assert r["chunk_type"] == "flat"
        assert r["parent_id"] == ""
        assert r["doc_id"] == ""
        assert "service_id" not in r, "Old service_id field should not be present"


class TestEsRetrieverDocsByIdsFields:
    def test_get_docs_by_ids_returns_tags(self):
        """get_docs_by_ids must include tags in returned documents."""
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 1.0,
                        "_source": {
                            "title": "SOP test",
                            "content": "content here",
                            "doc_type": "sop",
                            "chunk_type": "parent",
                            "parent_id": "",
                            "service_ids": ["svc_es"],
                            "tags": ["es", "9200", "重启"],
                        }
                    }
                ]
            }
        }

        from app.retrievers.es_retriever import get_docs_by_ids
        results = get_docs_by_ids(mock_es, ["doc_1"])

        assert len(results) == 1
        r = results[0]
        assert "tags" in r, f"Missing tags in get_docs_by_ids result: {r.keys()}"
        assert r["tags"] == ["es", "9200", "重启"]
        assert "doc_id" in r
        assert "service_ids" in r
        assert r["service_ids"] == ["svc_es"]
