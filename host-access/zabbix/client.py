"""Zabbix JSON-RPC client — 只读 host.get / item.get / history.get."""

import time

import httpx

from config import settings


class ZabbixClient:
    """Zabbix API client with token caching."""

    def __init__(
        self,
        url: str = None,
        user: str = None,
        password: str = None,
        token_ttl: int = 900,
    ):
        self.url = url or settings.zabbix_url
        self.user = user or settings.zabbix_user
        self.password = password or settings.zabbix_password
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

    def get_latest_metrics(self, hostid: str, item_keys: list[str]) -> dict:
        """Return latest values for the given item keys."""
        items = self.get_host_items(hostid)
        key_to_itemid = {
            item["key_"]: item["itemid"]
            for item in items
            if item["key_"] in item_keys
        }
        if not key_to_itemid:
            return {}

        history = self._rpc_call(
            "history.get",
            {
                "itemids": list(key_to_itemid.values()),
                "output": "extend",
                "limit": 1,
                "sortfield": "clock",
                "sortorder": "DESC",
            },
        )

        itemid_to_key = {iid: key for key, iid in key_to_itemid.items()}
        result = {}
        for h in history:
            key = itemid_to_key.get(h["itemid"])
            if key:
                result[key] = h.get("value", "N/A")
        return result

    def discover_network_interfaces(self, hostid: str) -> list[str]:
        """Return unique network interface names for a host.

        Parses ``net.if.in[<iface>]`` / ``net.if.out[<iface>]`` item keys.
        """
        items = self.get_host_items(hostid)
        ifaces: list[str] = []
        for item in items:
            key = item.get("key_", "")
            if key.startswith("net.if.in[") or key.startswith("net.if.out["):
                iface = key.split("[", 1)[1].rstrip("]")
                if iface and iface not in ifaces:
                    ifaces.append(iface)
        return ifaces
