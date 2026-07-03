"""Unit tests for get_service_alias_map and get_service_sops."""
import pytest
from unittest.mock import MagicMock


def _make_mock_driver(records):
    """Helper: mock Neo4j driver returning given records."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    mock_session.run.return_value.data.return_value = records
    return mock_driver


class TestGetServiceAliasMap:
    def test_returns_map_keyed_by_service_id(self):
        """Returns dict keyed by service_id with name and aliases."""
        records = [
            {"id": "svc_es", "name": "elasticsearch", "aliases": ["es", "弹性搜索"]},
            {"id": "svc_nginx", "name": "nginx", "aliases": ["nginx", "nginx代理"]},
        ]
        driver = _make_mock_driver(records)

        from app.retrievers.graph_retriever import get_service_alias_map
        result = get_service_alias_map(driver)

        assert "svc_es" in result
        assert result["svc_es"]["name"] == "elasticsearch"
        assert result["svc_es"]["aliases"] == ["es", "弹性搜索"]
        assert "svc_nginx" in result
        assert result["svc_nginx"]["aliases"] == ["nginx", "nginx代理"]

    def test_empty_when_no_services(self):
        """Returns empty dict when Neo4j has no Service nodes."""
        driver = _make_mock_driver([])

        from app.retrievers.graph_retriever import get_service_alias_map
        result = get_service_alias_map(driver)

        assert result == {}

    def test_handles_null_aliases(self):
        """Service with no aliases property returns empty aliases list."""
        records = [
            {"id": "svc_test", "name": "test", "aliases": None},
        ]
        driver = _make_mock_driver(records)

        from app.retrievers.graph_retriever import get_service_alias_map
        result = get_service_alias_map(driver)

        assert result["svc_test"]["aliases"] == []

    def test_exception_returns_empty(self):
        """Neo4j error returns empty dict."""
        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("connection failed")

        from app.retrievers.graph_retriever import get_service_alias_map
        result = get_service_alias_map(mock_driver)

        assert result == {}


class TestGetServiceSops:
    def test_returns_sop_docs_for_service(self):
        """Returns SOP documents linked to a service."""
        records = [
            {"doc_id": "svc_es_sop-9200", "title": "9200 端口不可达", "doc_type": "sop", "updated_at": "2024-06-01"},
        ]
        driver = _make_mock_driver(records)

        from app.retrievers.graph_retriever import get_service_sops
        result = get_service_sops(driver, "svc_es")

        assert len(result) == 1
        assert result[0]["doc_id"] == "svc_es_sop-9200"
        assert result[0]["doc_type"] == "sop"

    def test_filters_only_sop_docs(self):
        """get_service_sops only returns doc_type='sop' documents."""
        records = [
            {"doc_id": "svc_es_sop-9200", "title": "9200 SOP", "doc_type": "sop", "updated_at": "2024-06-01"},
            {"doc_id": "svc_es_sop-restart", "title": "重启 SOP", "doc_type": "sop", "updated_at": "2024-05-01"},
        ]
        driver = _make_mock_driver(records)

        from app.retrievers.graph_retriever import get_service_sops
        result = get_service_sops(driver, "svc_es")

        assert len(result) == 2
        assert all(r["doc_type"] == "sop" for r in result)

    def test_empty_when_no_sops(self):
        """Returns empty list when service has no SOPs."""
        driver = _make_mock_driver([])

        from app.retrievers.graph_retriever import get_service_sops
        result = get_service_sops(driver, "svc_unknown")

        assert result == []

    def test_exception_returns_empty(self):
        """Neo4j error returns empty list."""
        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("timeout")

        from app.retrievers.graph_retriever import get_service_sops
        result = get_service_sops(mock_driver, "svc_es")

        assert result == []


class TestGetServiceSopsBatch:
    def test_returns_sops_for_multiple_services(self):
        """Batch query returns SOPs across multiple services."""
        records = [
            {"doc_id": "sop-es-9200", "title": "ES 9200 SOP", "doc_type": "sop", "updated_at": "2024-06-01"},
            {"doc_id": "sop-nginx-80", "title": "Nginx 80 SOP", "doc_type": "sop", "updated_at": "2024-05-01"},
        ]
        driver = _make_mock_driver(records)

        from app.retrievers.graph_retriever import get_service_sops_batch
        result = get_service_sops_batch(driver, ["svc_es", "svc_nginx"])

        assert len(result) == 2
        doc_ids = [r["doc_id"] for r in result]
        assert "sop-es-9200" in doc_ids
        assert "sop-nginx-80" in doc_ids

    def test_deduplicates_by_doc_id(self):
        """Same doc linked to multiple services is returned only once."""
        records = [
            {"doc_id": "sop-shared", "title": "Shared SOP", "doc_type": "sop", "updated_at": "2024-06-01"},
            {"doc_id": "sop-shared", "title": "Shared SOP", "doc_type": "sop", "updated_at": "2024-06-01"},
        ]
        driver = _make_mock_driver(records)

        from app.retrievers.graph_retriever import get_service_sops_batch
        result = get_service_sops_batch(driver, ["svc_a", "svc_b"])

        assert len(result) == 1
        assert result[0]["doc_id"] == "sop-shared"

    def test_empty_service_ids_returns_empty(self):
        """Empty input returns empty output without querying Neo4j."""
        driver = _make_mock_driver([])

        from app.retrievers.graph_retriever import get_service_sops_batch
        result = get_service_sops_batch(driver, [])

        assert result == []

    def test_exception_returns_empty(self):
        """Neo4j error returns empty list."""
        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("timeout")

        from app.retrievers.graph_retriever import get_service_sops_batch
        result = get_service_sops_batch(mock_driver, ["svc_es"])

        assert result == []
