"""Tests for GET /api/v1/host/resolve endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_resolve_endpoint_found():
    """GET /api/v1/host/resolve?ip=10.33.17.100 → host_id"""
    with patch("app.api.routes.get_driver") as mock_get_driver:
        mock_driver = MagicMock()
        mock_get_driver.return_value = mock_driver

        with patch("app.retrievers.graph_retriever.resolve_host_by_ip") as mock_resolve:
            mock_resolve.return_value = {"host_id": "host_es_master_01", "host_name": "master-1"}

            from app.main import app
            client = TestClient(app)
            resp = client.get("/api/v1/host/resolve?ip=10.33.17.100")
            assert resp.status_code == 200
            data = resp.json()
            assert data["host_id"] == "host_es_master_01"
            assert data["host_name"] == "master-1"


def test_resolve_endpoint_not_found():
    """GET /api/v1/host/resolve?ip=99.99.99.99 → 404"""
    with patch("app.api.routes.get_driver") as mock_get_driver:
        mock_driver = MagicMock()
        mock_get_driver.return_value = mock_driver

        with patch("app.retrievers.graph_retriever.resolve_host_by_ip") as mock_resolve:
            mock_resolve.return_value = None

            from app.main import app
            client = TestClient(app)
            resp = client.get("/api/v1/host/resolve?ip=99.99.99.99")
            assert resp.status_code == 404
