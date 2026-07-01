"""Vector retrieval via SiliconFlow embedding API (no local model)."""

import asyncio
import httpx

from app.config import settings

EMBEDDING_MODEL = "Qwen/Qwen3-VL-Embedding-8B"
EMBEDDING_DIM = 4096


def _api_key() -> str | None:
    return settings.embedding_api_key or settings.llm_api_key or None


from collections import OrderedDict

_EMBED_CACHE: OrderedDict[str, list[float]] = OrderedDict()
_MAX_CACHE = 256


async def _embed_with_retry(texts: list[str]) -> list[list[float]] | None:
    """POST /v1/embeddings with exponential backoff retry, return None on final failure."""
    key = _api_key()
    if not key:
        return None

    base_url = settings.embedding_base_url
    max_retries = settings.embedding_retry_max
    backoff_ms = settings.embedding_retry_backoff_ms

    for attempt in range(1, max_retries + 2):
        try:
            def _sync():
                resp = httpx.Client(timeout=30, http2=False).post(
                    f"{base_url}/embeddings",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": EMBEDDING_MODEL, "input": texts},
                )
                resp.raise_for_status()
                return resp.json()
            data = await asyncio.to_thread(_sync)
            return [item["embedding"] for item in data["data"]]
        except Exception as e:
            if attempt <= max_retries:
                wait = backoff_ms * (2 ** (attempt - 1)) / 1000
                print(f"Embedding API error (attempt {attempt}/{max_retries + 1}): {e}, retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
            else:
                print(f"Embedding API failed after {max_retries + 1} attempts: {e}")
                return None


async def embed_text(text: str) -> list[float]:
    """Embed single text via API with LRU cache."""
    if text in _EMBED_CACHE:
        _EMBED_CACHE.move_to_end(text)
        return _EMBED_CACHE[text]

    vecs = await _embed_with_retry([text])
    if not vecs:
        return []

    vec = vecs[0]
    if len(_EMBED_CACHE) >= _MAX_CACHE:
        _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
    _EMBED_CACHE[text] = vec
    return vec


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts via API batch endpoint with retry."""
    if not texts:
        return []
    vecs = await _embed_with_retry(texts)
    return vecs or []


async def search_vector(es_client, query: str, top_k: int = 5) -> list[dict]:
    """Vector search via ES 8.x kNN using API embedding."""
    query_vec = await embed_text(query)
    if not query_vec:
        return []

    try:
        resp = es_client.search(
            index="knowledge_base",
            knn={
                "field": "content_vector",
                "query_vector": query_vec,
                "k": top_k,
                "num_candidates": 100,
            },
        )
        results = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            results.append({
                "title": src.get("title", ""),
                "content": src.get("content", ""),
                "score": hit["_score"],
                "doc_type": src.get("doc_type", ""),
                "service_id": src.get("service_id", ""),
                "engine": "vector",
            })
        return results
    except Exception as e:
        print(f"Vector search error: {e}")
        return []
