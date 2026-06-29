"""IPhost_id 关联。调 rag /api/v1/host/resolve?ip= 端点。"""

import httpx


class HostResolver:
    def __init__(self, rag_api_url: str):
        self.rag_api_url = rag_api_url.rstrip("/")

    def resolve(self, ip: str) -> dict | None:
        """按 IP 查 rag 拓扑，返回 {host_id, host_name} 或 None。"""
        try:
            resp = httpx.get(f"{self.rag_api_url}/host/resolve", params={"ip": ip}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"host_resolver error: {e}")
            return None
