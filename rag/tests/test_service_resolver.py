"""Unit tests for ServiceResolver — multi-recall pre-check logic."""
import pytest
from unittest.mock import MagicMock, patch
import time


def _make_mock_driver(host_records=None, service_records=None, sop_records=None):
    """Build mock Neo4j driver with configurable responses per query."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    call_count = [0]
    results = []

    def side_effect(*args, **kwargs):
        query = args[0] if args else ""
        result = MagicMock()
        if "Host {ip:" in query or "Host {id:" in query.replace(" ", ""):
            # resolve_host_by_ip or get_host_services
            records = host_records or []
            result.data.return_value = records
            result.single.return_value = records[0] if records else None
        elif "Service" in query and "aliases" in query:
            # get_service_alias_map
            result.data.return_value = service_records or []
        elif "HAS_DOC" in query and "sop" in query:
            # get_service_sops
            result.data.return_value = sop_records or []
        else:
            result.data.return_value = []
            result.single.return_value = None
        call_count[0] += 1
        return result

    mock_session.run.side_effect = side_effect
    mock_driver._test_session = mock_session  # expose for call_count assertions
    return mock_driver


class TestExtractIps:
    def test_extracts_single_ip(self):
        from app.router.service_resolver import ServiceResolver
        ips = ServiceResolver.extract_ips("10.33.16.42 磁盘告警")
        assert ips == ["10.33.16.42"]

    def test_extracts_multiple_ips(self):
        from app.router.service_resolver import ServiceResolver
        ips = ServiceResolver.extract_ips("from 10.33.16.42 to 10.33.16.43")
        assert "10.33.16.42" in ips
        assert "10.33.16.43" in ips

    def test_no_ip_returns_empty(self):
        from app.router.service_resolver import ServiceResolver
        ips = ServiceResolver.extract_ips("nginx 磁盘满了")
        assert ips == []

    def test_filters_invalid_ips(self):
        from app.router.service_resolver import ServiceResolver
        ips = ServiceResolver.extract_ips("999.999.999.999 is not valid")
        assert ips == []


class TestTagSort:
    def test_higher_overlap_ranks_first(self):
        from app.router.service_resolver import ServiceResolver
        sops = [
            {"doc_id": "a", "title": "重启", "tags": ["nginx", "重启"]},
            {"doc_id": "b", "title": "磁盘满", "tags": ["nginx", "磁盘满", "清理日志", "空间"]},
        ]
        sorted_sops = ServiceResolver.tag_sort(
            {"nginx", "磁盘", "满", "home", "目录", "空间"},
            sops
        )
        assert sorted_sops[0]["doc_id"] == "b", "磁盘满 SOP should rank first"

    def test_no_overlap_returns_original_order(self):
        from app.router.service_resolver import ServiceResolver
        sops = [
            {"doc_id": "a", "title": "A", "tags": ["x", "y"]},
            {"doc_id": "b", "title": "B", "tags": ["z"]},
        ]
        sorted_sops = ServiceResolver.tag_sort({"query", "token"}, sops)
        # Both score 0, order preserved
        assert sorted_sops[0]["doc_id"] == "a"

    def test_empty_query_tokens(self):
        from app.router.service_resolver import ServiceResolver
        sops = [{"doc_id": "a", "title": "A", "tags": ["nginx"]}]
        sorted_sops = ServiceResolver.tag_sort(set(), sops)
        assert len(sorted_sops) == 1


class TestResolveByName:
    def test_exact_alias_match(self):
        from app.router.service_resolver import ServiceResolver
        mock_driver = _make_mock_driver(service_records=[
            {"id": "svc_nginx", "name": "company-nginx-cluster", "aliases": ["nginx", "company-nginx"]},
        ])
        resolver = ServiceResolver(mock_driver, MagicMock())
        matches = resolver.resolve_by_name("nginx 磁盘满了")
        assert len(matches) >= 1
        assert matches[0][0] == "svc_nginx"
        assert matches[0][1] >= 0.8

    def test_no_match_returns_empty(self):
        from app.router.service_resolver import ServiceResolver
        mock_driver = _make_mock_driver(service_records=[
            {"id": "svc_es", "name": "elasticsearch", "aliases": ["es"]},
        ])
        resolver = ServiceResolver(mock_driver, MagicMock())
        matches = resolver.resolve_by_name("完全无关的问题")
        assert matches == []

    def test_multiple_services_match(self):
        from app.router.service_resolver import ServiceResolver
        mock_driver = _make_mock_driver(service_records=[
            {"id": "svc_nginx", "name": "nginx", "aliases": ["nginx"]},
            {"id": "svc_es", "name": "elasticsearch", "aliases": ["es", "弹性搜索"]},
        ])
        resolver = ServiceResolver(mock_driver, MagicMock())
        matches = resolver.resolve_by_name("nginx es 都挂了")
        service_ids = [m[0] for m in matches]
        assert "svc_nginx" in service_ids
        assert "svc_es" in service_ids


class TestAliasMapCache:
    def test_cache_hit_within_ttl(self):
        from app.router.service_resolver import ServiceResolver
        mock_driver = _make_mock_driver(service_records=[
            {"id": "svc_es", "name": "es", "aliases": ["es"]},
        ])
        resolver = ServiceResolver(mock_driver, MagicMock())
        resolver.CACHE_TTL = 300

        # First call loads
        map1 = resolver.get_alias_map()
        assert "svc_es" in map1

        # Second call should use cache (no additional Neo4j queries)
        map2 = resolver.get_alias_map()
        assert map2 == map1

    def test_cache_expired_after_ttl(self):
        from app.router.service_resolver import ServiceResolver
        mock_driver = _make_mock_driver(service_records=[
            {"id": "svc_es", "name": "es", "aliases": ["es"]},
        ])
        resolver = ServiceResolver(mock_driver, MagicMock())
        resolver.CACHE_TTL = 0  # Expire immediately

        resolver.get_alias_map()
        time.sleep(0.01)
        resolver.get_alias_map()  # Should reload

        # Verify Neo4j was queried twice
        assert mock_driver._test_session.run.call_count >= 2
