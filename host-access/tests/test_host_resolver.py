import pytest
from unittest.mock import patch, MagicMock
from relation.host_resolver import HostResolver

class TestHostResolver:
    def test_resolve_found(self):
        """IP → host_id 解析成功"""
        resolver = HostResolver("http://localhost:8001/api/v1")

        with patch("relation.host_resolver.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"host_id": "host_es_master_01", "host_name": "master-1"}
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp

            result = resolver.resolve("10.33.17.100")
            assert result["host_id"] == "host_es_master_01"

    def test_resolve_not_found(self):
        """IP 在 rag 拓扑无匹配"""
        resolver = HostResolver("http://localhost:8001/api/v1")

        with patch("relation.host_resolver.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp

            result = resolver.resolve("99.99.99.99")
            assert result is None

    def test_resolve_rag_unreachable(self):
        """rag 不可达"""
        resolver = HostResolver("http://localhost:8001/api/v1")

        with patch("relation.host_resolver.httpx.get", side_effect=Exception("Connection refused")):
            result = resolver.resolve("10.33.17.100")
            assert result is None
