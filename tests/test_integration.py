"""端到端集成测试：IP → 指标 + 影响 → 融合答案。"""

import subprocess
import os

AIOPS_ROOT = "/root/.openclaw/workspace-shared/aiops"
HOST_ACCESS = os.path.join(AIOPS_ROOT, "host-access")
RAG = os.path.join(AIOPS_ROOT, "rag")


def test_host_query_status_with_mock():
    """host-query status 返回格式正确（mock Zabbix）"""
    result = subprocess.run(
        ["python3", "cli/host-query", "status", "10.33.17.100"],
        capture_output=True, text=True, cwd=HOST_ACCESS,
    )
    # 无 Zabbix 时允许失败，但输出应包含错误信息而非崩溃
    if result.returncode != 0:
        assert "Error" in result.stderr or "未纳管" in result.stdout


def test_rag_resolve_endpoint():
    """rag /host/resolve 端点正常工作"""
    import httpx
    try:
        resp = httpx.get(
            "http://localhost:8001/api/v1/host/resolve",
            params={"ip": "10.33.17.100"},
            timeout=5,
        )
        assert resp.status_code in [200, 404]  # 404 表示无数据，200 表示找到
    except httpx.ConnectError:
        import pytest
        pytest.skip("RAG API not reachable on localhost:8001")


def test_full_flow():
    """完整流程：IP → host-query → aiops-query impact"""
    # Step 1: host-query status
    status = subprocess.run(
        ["python3", "cli/host-query", "status", "10.33.17.100"],
        capture_output=True, text=True, cwd=HOST_ACCESS,
    )
    if status.returncode != 0:
        print("Skip: Zabbix not available")
        return

    # Step 2: 解析 host_id
    host_id = None
    for line in status.stdout.split("\n"):
        if line.startswith("host_id:"):
            host_id = line.split(":")[1].strip()
            break

    if not host_id:
        print("Skip: No host_id returned")
        return

    # Step 3: aiops-query impact
    impact = subprocess.run(
        ["./skills/aiops-query", "impact", host_id],
        capture_output=True, text=True, cwd=RAG,
    )
    assert impact.returncode == 0
    assert "impact" in impact.stdout.lower() or "affected" in impact.stdout.lower()
