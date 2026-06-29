import pytest
from unittest.mock import patch, MagicMock
import json


class TestZabbixClient:
    def test_login_and_get_token(self):
        """user.login 返回 token"""
        from zabbix.client import ZabbixClient
        client = ZabbixClient("http://fake/api_jsonrpc.php", "Admin", "zabbix")

        with patch("zabbix.client.httpx.Client") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"result": "fake-token-123", "id": 1, "jsonrpc": "2.0"}
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

            token = client.login()
            assert token == "fake-token-123"

    def test_get_host_by_ip_found(self):
        """按 IP 查 Zabbix host — 找到"""
        from zabbix.client import ZabbixClient
        client = ZabbixClient("http://fake/api_jsonrpc.php", "Admin", "zabbix")
        client._token = "fake-token"
        client._token_exp = 9999999999

        mock_response = {
            "result": [{"hostid": "10101", "name": "master-1", "status": "0", "available": "1"}],
            "id": 2, "jsonrpc": "2.0"
        }

        with patch("zabbix.client.httpx.Client") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

            host = client.get_host_by_ip("10.33.17.100")
            assert host["hostid"] == "10101"
            assert host["name"] == "master-1"

    def test_get_host_by_ip_not_found(self):
        """按 IP 查 Zabbix host — 未找到"""
        from zabbix.client import ZabbixClient
        client = ZabbixClient("http://fake/api_jsonrpc.php", "Admin", "zabbix")
        client._token = "fake-token"
        client._token_exp = 9999999999

        with patch("zabbix.client.httpx.Client") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"result": [], "id": 2, "jsonrpc": "2.0"}
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

            host = client.get_host_by_ip("99.99.99.99")
            assert host is None

    def test_token_cache_reuse(self):
        """同进程内多次调用复用 token"""
        from zabbix.client import ZabbixClient
        client = ZabbixClient("http://fake/api_jsonrpc.php", "Admin", "zabbix")
        client._token = "cached-token"
        client._token_exp = 9999999999  # 未过期

        token = client._get_token()
        assert token == "cached-token"

    def test_discover_network_interfaces(self):
        """发现主机网络接口"""
        from zabbix.client import ZabbixClient
        client = ZabbixClient("http://fake/api_jsonrpc.php", "Admin", "zabbix")

        mock_items = [
            {"key_": "net.if.in[eth0]"},
            {"key_": "net.if.out[eth0]"},
            {"key_": "net.if.in[bond0]"},
            {"key_": "system.cpu.util"},
        ]

        with patch.object(client, "get_host_items", return_value=mock_items):
            ifaces = client.discover_network_interfaces("10101")
            assert "eth0" in ifaces
            assert "bond0" in ifaces
            assert len(ifaces) == 2
