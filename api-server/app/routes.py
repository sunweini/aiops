"""API routes for AIOps platform — conversations, auth, users, host status, topology, alerts."""

import json
import uuid
import os

from fastapi import APIRouter, HTTPException

RAG_API_BASE = os.environ.get('RAG_API_URL', 'http://host.docker.internal:8001').rstrip('/') + '/api/v1'

router = APIRouter()


# ---- Health ----

@router.get("/health")
async def health():
    return {"status": "ok", "service": "aiops-api-server"}


# ---- Conversations ----

@router.get("/conversations")
async def list_conversations(limit: int = 50):
    from app.chat.db import list_conversations as _list
    return {"conversations": _list(limit)}


@router.post("/conversations")
async def create_conversation(data: dict):
    from app.chat.db import create_conversation as _create
    title = data.get("title", "新对话")
    return _create(title)


@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, data: dict):
    from app.chat.db import (
        get_conversation as _get_conv,
        add_message as _add_msg,
        update_tokens as _upd_tokens
    )

    conv = _get_conv(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv["turn_count"] >= 20:
        raise HTTPException(status_code=400, detail="已达最大对话轮数（20 轮）")
    if conv["total_tokens"] >= 128000:
        raise HTTPException(status_code=400, detail="已达最大 token 限制（128K）")

    query = data.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    _add_msg(conv_id, "user", query)

    # Proxy to rag-api for actual RAG answer
    import httpx
    try:
        rag_resp = httpx.post(
            RAG_API_BASE + "/query",
            json={"query": query, "top_k": 5},
            timeout=60
        )
        rag_data = rag_resp.json()
        answer = rag_data.get("answer", "")
        sources = rag_data.get("sources", [])
    except Exception as e:
        answer = f"RAG 服务暂不可用。\n\n检索到的问题：{query}\n\n错误：{str(e)}"
        sources = []

    _add_msg(conv_id, "assistant", answer, [
        {"title": s.get("title", ""), "score": s.get("score"), "engine": s.get("engine")}
        for s in sources
    ])

    total_chars = len(query) + len(answer)
    _upd_tokens(conv_id, total_chars // 2)

    updated = _get_conv(conv_id)

    return {
        "answer": answer,
        "sources": [
            {"title": s.get("title"), "score": s.get("score"), "engine": s.get("engine")}
            for s in sources
        ],
        "turn_count": updated["turn_count"],
        "total_tokens": updated["total_tokens"],
        "token_limit": 128000,
        "turn_limit": 20
    }


# ---- Auth ----

@router.post("/auth/login")
async def auth_login(data: dict):
    from app.auth import authenticate, create_tokens
    username = data.get("username", "")
    password = data.get("password", "")
    user = authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return create_tokens(user)


@router.post("/auth/refresh")
async def auth_refresh(data: dict):
    from app.auth import refresh_access
    refresh_token = data.get("refresh_token", "")
    result = refresh_access(refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Refresh token 无效或已过期")
    return result


@router.post("/auth/logout")
async def auth_logout(data: dict):
    from app.auth import revoke_token
    refresh_token = data.get("refresh_token", "")
    revoke_token(refresh_token)
    return {"status": "ok"}


# ---- Users ----

@router.get("/users")
async def list_users():
    from app.auth import list_users as _list
    return {"users": _list()}


@router.post("/users")
async def create_user(data: dict):
    from app.auth import create_user as _create
    username = data.get("username", "")
    password = data.get("password", "")
    role = data.get("role", "operator")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")
    result = _create(username, password, role)
    if not result:
        raise HTTPException(status_code=409, detail="用户名已存在")
    return result


@router.delete("/users/{user_id}")
async def delete_user(user_id: int):
    from app.auth import delete_user as _delete
    if not _delete(user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"status": "ok"}


# ---- Host Status (topology + Zabbix metrics) ----

@router.get("/hosts/status")
async def hosts_status():
    """Get all hosts with metrics (optimized: 2 Zabbix API calls total)."""
    import httpx
    from app.hosts import get_all_host_metrics

    try:
        # Get topology from rag-api
        resp = httpx.get(RAG_API_BASE + "/topology/all", timeout=10)
        data = resp.json()
        raw_hosts = data.get("hosts", [])
    except Exception as e:
        return {"hosts": [], "summary": {"total": 0, "online": 0, "offline": 0}, "error": str(e)}

    # Batch query Zabbix (2 API calls: hosts + items)
    try:
        all_metrics = get_all_host_metrics()
    except Exception as e:
        print(f"Batch metrics failed: {e}")
        all_metrics = {}

    hosts = []
    online = 0
    for h in raw_hosts:
        ip = h.get("ip", "")
        info = all_metrics.get(ip, {"available": False, "metrics": {}})

        host_entry = {
            "host_id": h.get("id", ""),
            "name": h.get("name", ""),
            "ip": ip,
            "available": info["available"],
            "metrics": info["metrics"]
        }
        hosts.append(host_entry)
        if info["available"]:
            online += 1

    return {
        "hosts": hosts,
        "summary": {"total": len(hosts), "online": online, "offline": len(hosts) - online}
    }


# ---- Topology (proxied from rag) ----

@router.get("/topology/all")
async def topology_all():
    import httpx
    try:
        resp = httpx.get(RAG_API_BASE + "/topology/all", timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e), "services": [], "edges": [], "hosts": []}


# ---- Alerts ----

@router.get("/alerts/active")
async def alerts_active():
    return {"alerts": [], "total": 0}
