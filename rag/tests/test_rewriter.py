"""Unit tests for query rewriter (no LLM needed for regex fallback)."""
import pytest
from app.router.query_rewriter import _regex_extract_entities


def test_regex_extracts_ip():
    entities = _regex_extract_entities("10.33.16.42 nginx 502")
    assert entities["host_ip"] == "10.33.16.42"


def test_regex_empty_on_no_ip():
    entities = _regex_extract_entities("nginx 502 排查")
    assert entities["host_ip"] == ""


def test_regex_returns_all_fields():
    entities = _regex_extract_entities("test query")
    for key in ["host_ip", "service", "port", "symptom"]:
        assert key in entities, f"Missing key: {key}"


def test_regex_multiple_ips_gets_first():
    entities = _regex_extract_entities("from 10.33.16.42 to 10.33.16.43")
    assert entities["host_ip"] == "10.33.16.42"


@pytest.mark.asyncio
async def test_rewrite_fallback_no_api_key():
    """Without API key, rewrite returns original + regex entities."""
    from app.router.query_rewriter import rewrite_and_extract
    import os
    saved_key = os.environ.get("LLM_API_KEY", "")
    os.environ.pop("LLM_API_KEY", None)
    try:
        rewritten, types, entities = await rewrite_and_extract("怎么扩容磁盘")
        assert rewritten == "怎么扩容磁盘"
        assert "sop" in types
        assert entities["host_ip"] == ""
    finally:
        if saved_key:
            os.environ["LLM_API_KEY"] = saved_key


@pytest.mark.asyncio
async def test_rewrite_fallback_incident_keywords():
    """With query containing incident keywords, fallback should classify as incident."""
    from app.router.query_rewriter import rewrite_and_extract
    import os
    saved_key = os.environ.get("LLM_API_KEY", "")
    os.environ.pop("LLM_API_KEY", None)
    try:
        rewritten, types, entities = await rewrite_and_extract("nginx 502 超时连不上")
        assert "incident" in types, f"Expected 'incident' in types: {types}"
    finally:
        if saved_key:
            os.environ["LLM_API_KEY"] = saved_key


@pytest.mark.asyncio
async def test_rewrite_fallback_topology_with_ip():
    """With query containing IP, fallback should include topology intent."""
    from app.router.query_rewriter import rewrite_and_extract
    import os
    saved_key = os.environ.get("LLM_API_KEY", "")
    os.environ.pop("LLM_API_KEY", None)
    try:
        rewritten, types, entities = await rewrite_and_extract("10.33.16.42 部署在哪")
        assert "topology" in types or "incident" in types, \
            f"Expected topology or incident in types: {types}"
    finally:
        if saved_key:
            os.environ["LLM_API_KEY"] = saved_key


@pytest.mark.asyncio
async def test_rewrite_fallback_default_sop():
    """With no special keywords, fallback defaults to sop."""
    from app.router.query_rewriter import rewrite_and_extract
    import os
    saved_key = os.environ.get("LLM_API_KEY", "")
    os.environ.pop("LLM_API_KEY", None)
    try:
        rewritten, types, entities = await rewrite_and_extract("怎么扩容磁盘")
        assert "sop" in types
    finally:
        if saved_key:
            os.environ["LLM_API_KEY"] = saved_key
