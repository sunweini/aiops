"""Zabbix JSON-RPC client — 只读 host.get / item.get / history.get."""

import os
import time

import httpx


class ZabbixClient:
    """Zabbix API client with token caching."""

    def __init__(
        self,
        url: str = None,
        user: str = None,
        password: str = None,
        token_ttl: int = 900,
    ):
        self.url = url or os.environ.get('ZABBIX_URL', 'http://f.oetsky.com/api_jsonrpc.php')
        self.user = user or os.environ.get('ZABBIX_USER', 'sunweini')
        self.password = password or os.environ.get('ZABBIX_PASSWORD', 'Asd5229230.')
        self.token_ttl = token_ttl
        self._token: str | None = None
        self._token_exp: float = 0

    # ---- transport ----------------------------------------------------- #

    def _post(self, payload: dict) -> dict:
        """Send a JSON-RPC payload and return the parsed response body."""
        with httpx.Client(timeout=30) as client:
            resp = client.post(self.url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Zabbix API error: {data['error']}")
            return data

    def _rpc_call(self, method: str, params: dict) -> dict:
        """Authenticated JSON-RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "auth": self._get_token(),
            "id": 1,
        }
        return self._post(payload).get("result")

    def _rpc_call_no_auth(self, method: str, params: dict) -> dict:
        """Unauthenticated JSON-RPC call (used for login)."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        return self._post(payload).get("result")

    # ---- auth ---------------------------------------------------------- #

    def _get_token(self) -> str:
        """Return cached token if still valid, otherwise re-login."""
        if self._token and time.time() < self._token_exp:
            return self._token
        return self.login()

    def login(self) -> str:
        """Authenticate via user.login and cache the token."""
        result = self._rpc_call_no_auth(
            "user.login", {"user": self.user, "password": self.password}
        )
        self._token = result
        self._token_exp = time.time() + self.token_ttl
        return result

    def logout(self) -> None:
        """Invalidate the cached token."""
        if self._token:
            try:
                self._rpc_call("user.logout", [])
            except Exception:
                pass
            self._token = None

    # ---- hosts --------------------------------------------------------- #

    def get_all_hosts(self) -> list[dict]:
        """Get all hosts from Zabbix (single API call).

        Returns list of hosts with their interfaces.
        """
        result = self._rpc_call(
            "host.get",
            {
                "output": ["hostid", "name", "status", "available"],
                "selectInterfaces": ["ip"],
            },
        )
        return [
            {
                "hostid": h["hostid"],
                "name": h["name"],
                "status": h["status"],
                "available": h.get("available", "1"),
                "interfaces": h.get("interfaces", []),
            }
            for h in result
        ]

    def get_host_by_ip(self, ip: str) -> dict | None:
        """Find a Zabbix host by interface IP.

        Uses Zabbix's ``search`` parameter on ``host.get``, which by default
        searches across host interfaces' IP/DNS fields.
        """
        result = self._rpc_call(
            "host.get",
            {"search": {"ip": ip}, "searchByAny": False, "limit": 1},
        )
        if not result:
            return None
        host = result[0]
        return {
            "hostid": host["hostid"],
            "name": host["name"],
            "status": host["status"],
            "available": host.get("available", "1"),
        }

    # ---- hosts --------------------------------------------------------- #

    def get_hosts_by_ips(self, ips: list[str]) -> list[dict]:
        """Find Zabbix hosts matching the given IPs (single batch call).

        Uses Zabbix ``search`` with ``searchByAny=True`` to match any of the IPs.
        Only returns hosts that exist in Zabbix.
        """
        if not ips:
            return []
        # Zabbix search accepts list of values for a field
        result = self._rpc_call(
            "host.get",
            {
                "output": ["hostid", "name", "status", "available"],
                "selectInterfaces": ["ip"],
                "filter": {"ip": ips},
            },
        )
        return [
            {
                "hostid": h["hostid"],
                "name": h["name"],
                "status": h["status"],
                "available": h.get("available", "1"),
                "interfaces": h.get("interfaces", []),
            }
            for h in result
        ]

    # ---- items / metrics ---------------------------------------------- #

    def get_host_items(self, hostid: str) -> list[dict]:
        """Return all monitoring items for a host."""
        return self._rpc_call(
            "item.get",
            {
                "hostids": [hostid],
                "output": ["itemid", "key_", "name", "lastvalue"],
            },
        )

    def get_items_by_hosts(self, hostids: list[str], keys: list[str] = None) -> list[dict]:
        """Return monitoring items for specific hosts (single batch call).

        Args:
            hostids: List of Zabbix host IDs to query
            keys: Optional list of item key patterns to filter (exact match or prefix)
        """
        if not hostids:
            return []
        params = {
            "hostids": hostids,
            "output": ["itemid", "key_", "name", "lastvalue", "hostid"],
            "selectHosts": ["hostid"],
        }
        # Use search to filter by key if specified
        if keys:
            params["search"] = {"key_": keys}
            params["searchByAny"] = True
        return self._rpc_call("item.get", params)

    def get_latest_metrics(self, hostid: str, item_key_patterns: list[str]) -> dict:
        """Return latest values for items matching the given key patterns.

        Uses ``lastvalue`` from ``item.get`` (no separate history.get needed).
        Supports both exact match and prefix match.

        Special handling for CPU metrics:
        - ``system.cpu.util[]`` (no params) = CPU usage
        - ``system.cpu.util[,idle]`` = CPU idle (must be excluded)
        """
        items = self.get_host_items(hostid)

        result: dict[str, str] = {}
        for pattern in item_key_patterns:
            for item in items:
                key = item["key_"]
                # Special case: system.cpu.util[] must not match system.cpu.util[,idle]
                if pattern == "system.cpu.util[]":
                    if key == "system.cpu.util[]":
                        result[pattern] = item.get("lastvalue", "N/A")
                        break
                # Exact match or prefix match
                elif key == pattern or key.startswith(pattern) or pattern in key:
                    # Skip idle metrics when looking for CPU usage
                    if pattern == "system.cpu.util" and "idle" in key:
                        continue
                    result[pattern] = item.get("lastvalue", "N/A")
                    break  # Take first match for each pattern

        return result

    def discover_network_interfaces(self, hostid: str) -> list[str]:
        """Return unique network interface names for a host.

        Parses ``net.if.in[<iface>]`` / ``net.if.out[<iface>]`` item keys.
        Handles formats: ``eth0``, ``"eth0"``, ``"eth0",dropped``.
        """
        items = self.get_host_items(hostid)
        ifaces: list[str] = []
        for item in items:
            key = item.get("key_", "")
            if key.startswith("net.if.in[") or key.startswith("net.if.out["):
                # Extract interface name: net.if.in["eth0",dropped] -> eth0
                raw = key.split("[", 1)[1].rstrip("]")
                # Remove quotes and extra params: "eth0",dropped -> eth0
                iface = raw.split(",")[0].strip('"')
                if iface and iface not in ifaces:
                    ifaces.append(iface)
        return ifaces
