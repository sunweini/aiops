"""Integration tests for multi-recall query routing (A/B/C paths)."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestMultiRecallRouting:
    @pytest.mark.asyncio
    async def test_path_a_hits_on_ip(self):
        """When query contains IP that resolves to a host with SOPs, Path A returns directly."""
        mock_result = {
            "answer": "## [文档1] 9200 端口不可达\n排查步骤...",
            "sources": [],
            "matched_by": "ip",
        }
        mock_resolver = MagicMock()
        mock_resolver.try_path_a.return_value = mock_result
        mock_resolver.try_path_b.return_value = None

        with patch("app.api.routes.ServiceResolver", return_value=mock_resolver):
            with patch("app.api.routes.get_es_client"):
                with patch("app.api.routes.get_driver"):
                    from app.api.routes import query
                    from app.models.query import QueryRequest
                    req = QueryRequest(query="10.33.17.100 磁盘告警")
                    result = await query(req)

        assert result.matched_by == "ip"
        mock_resolver.try_path_a.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_b_hits_on_service_name(self):
        """When query mentions a service name matching aliases, Path B returns."""
        mock_result = {
            "answer": "## [文档1] 磁盘满-清理日志\n清理步骤...",
            "sources": [],
            "matched_by": "service_name",
        }
        mock_resolver = MagicMock()
        mock_resolver.try_path_a.return_value = None  # No IP
        mock_resolver.try_path_b.return_value = mock_result

        with patch("app.api.routes.ServiceResolver", return_value=mock_resolver):
            with patch("app.api.routes.get_es_client"):
                with patch("app.api.routes.get_driver"):
                    from app.api.routes import query
                    from app.models.query import QueryRequest
                    req = QueryRequest(query="nginx 磁盘满了")
                    result = await query(req)

        assert result.matched_by == "service_name"
        mock_resolver.try_path_b.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_a_preferred_over_b(self):
        """When Path A hits, Path B is not attempted."""
        mock_result = {
            "answer": "...",
            "sources": [],
            "matched_by": "ip",
        }
        mock_resolver = MagicMock()
        mock_resolver.try_path_a.return_value = mock_result

        with patch("app.api.routes.ServiceResolver", return_value=mock_resolver):
            with patch("app.api.routes.get_es_client"):
                with patch("app.api.routes.get_driver"):
                    from app.api.routes import query
                    from app.models.query import QueryRequest
                    req = QueryRequest(query="10.33.17.100 nginx 磁盘满了")
                    result = await query(req)

        assert result.matched_by == "ip"
        mock_resolver.try_path_b.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_path_c_when_ab_miss(self):
        """When A/B both miss, falls back to existing pipeline (Path C)."""
        mock_resolver = MagicMock()
        mock_resolver.try_path_a.return_value = None
        mock_resolver.try_path_b.return_value = None

        with patch("app.api.routes.ServiceResolver", return_value=mock_resolver):
            with patch("app.api.routes.get_es_client") as mock_es:
                with patch("app.api.routes.get_driver"):
                    with patch("app.api.routes.search_fulltext", return_value=[]):
                        with patch("app.api.routes.search_vector", new_callable=AsyncMock, return_value=[]):
                            with patch("app.api.routes.rewrite_and_extract", new_callable=AsyncMock, return_value=("随机无意义query", [], {})):
                                from app.api.routes import query
                                from app.models.query import QueryRequest
                                req = QueryRequest(query="随机无意义query")
                                result = await query(req)

        # Should not have matched_by from A/B
        assert result.matched_by is None or result.matched_by not in ("ip", "service_name")
