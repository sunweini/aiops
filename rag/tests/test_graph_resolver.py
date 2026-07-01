import pytest
from unittest.mock import MagicMock, patch


def test_resolve_host_by_ip_found():
    """按 IP 查 host_id — 找到"""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_record = {"host_id": "host_es_master_01", "host_name": "master-1"}
    mock_session.run.return_value.single.return_value = mock_record

    from app.retrievers.graph_retriever import resolve_host_by_ip
    result = resolve_host_by_ip(mock_driver, "10.33.17.100")
    assert result["host_id"] == "host_es_master_01"
    assert result["host_name"] == "master-1"


def test_resolve_host_by_ip_not_found():
    """按 IP 查 host_id — 未找到"""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_session.run.return_value.single.return_value = None

    from app.retrievers.graph_retriever import resolve_host_by_ip
    result = resolve_host_by_ip(mock_driver, "99.99.99.99")
    assert result is None or result.get("host_id") is None
