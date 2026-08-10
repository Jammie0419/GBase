# SPDX-License-Identifier: MIT
"""
village_connector.py — Village OS connector module

Injected into GBase v2 startup flow to:
1. Register with Soul Engine on startup (capability declaration)
2. 60-second heartbeat
3. Provide WCP message sending functions (via Security Gateway)
4. Subscribe to messages from Village OS
"""

import asyncio
import contextlib
import logging
import os

logger = logging.getLogger("village-os")

VILLAGE_OS_URL = os.environ.get("VILLAGE_OS_URL", "http://127.0.0.1:8765")
VILLAGE_NAME = "village:gbase:standard"
NODE_NAME = "gbase-v2"
VILLAGE_FROM = f"{VILLAGE_NAME}:{NODE_NAME}"
HEARTBEAT_INTERVAL = 60  # seconds
ENABLED = os.environ.get("VILLAGE_OS_DISABLED") != "1"


# ── Utilities ──


async def _http_post(path: str, data: dict) -> dict:
    """Send an HTTP POST request to Village OS."""
    import aiohttp

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(f"{VILLAGE_OS_URL}{path}", json=data, timeout=aiohttp.ClientTimeout(total=5)) as resp,
        ):
            return await resp.json()
    except Exception as e:
        logger.warning("[Village] Request failed: %s", e)
        return {"status": "error", "reason": str(e)}


async def _http_get(path: str) -> dict:
    """Send an HTTP GET request to Village OS."""
    import aiohttp

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(f"{VILLAGE_OS_URL}{path}", timeout=aiohttp.ClientTimeout(total=5)) as resp,
        ):
            return await resp.json()
    except Exception as e:
        logger.warning("[Village] GET request failed: %s", e)
        return {"status": "error", "reason": str(e)}


# ── Core API ──


async def register() -> dict:
    """Register with Village OS Soul Engine."""
    if not ENABLED:
        return {"status": "disabled"}

    payload = {
        "type": "capability",
        "from": VILLAGE_FROM,
        "body": {
            "name": "GBase v2",
            "version": "2.0",
            "type": "agent",
            "identity": os.environ.get("IDENTITY", "standard"),
            "capabilities": [
                "chat",
                "learning",
                "search",
                "skills",
                "email_v3",  # removed feishu_messaging
            ],
            "endpoints": {
                # feishu: removed for release
            },
        },
    }
    result = await _http_post("/wcp/message", payload)
    if result.get("status") == "ok":
        logger.info("[Village] ✅ Registered with Soul Engine")
    else:
        logger.warning("[Village] ⚠ Registration failed: %s", result)
    return result


async def send_heartbeat() -> dict:
    """Send heartbeat to Village OS."""
    if not ENABLED:
        return {"status": "disabled"}

    payload = {
        "type": "heartbeat",
        "from": VILLAGE_FROM,
        "body": {
            "status": "ok",
            "uptime": __import__("time").time(),
            "mode": os.environ.get("IDENTITY", "standard"),
        },
    }
    return await _http_post("/wcp/message", payload)


async def send_message(msg_type: str, body: dict, to: str = "*") -> dict:
    """Send WCP message via Village OS Security Gateway.

    Example:
        await send_message("mail", {
            "to": "yufei:)node1.gbase",
            "subject": "From GBase",
            "body": "Hello Yufei"
        })
    """
    payload = {"type": msg_type, "from": VILLAGE_FROM, "to": to, "body": body}
    return await _http_post("/wcp/message", payload)


async def send_email(to: str, subject: str, body: str) -> dict:
    """Send sprite mail via Village OS (auto-passes Security Gateway)."""
    return await send_message("mail", {"to": to, "subject": subject, "body": body, "action": "send"})


async def check_health() -> dict:
    """Check Village OS health status."""
    return await _http_get("/health")


async def get_history(limit: int = 10) -> list:
    """Get Village OS message history."""
    result = await _http_get(f"/wcp/history?limit={limit}")
    return result.get("messages", [])


async def get_soul_status() -> dict:
    """Get Soul Engine status."""
    result = await _http_get("/wcp/status")
    return result.get("soul_stats", {})


# ── Startup Loop ──


async def start(_loop: asyncio.AbstractEventLoop = None) -> asyncio.Task:
    """Start Village OS heartbeat and registration loop in the background.

    Usage:
        village_connector = await village.start()
        # On exit:
        village_connector.cancel()
    """
    if not ENABLED:
        logger.info("[Village] Village OS access disabled (VILLAGE_OS_DISABLED=1)")
        return None

    async def _loop():
        # Initial registration
        await register()

        while True:
            with contextlib.suppress(Exception):
                await send_heartbeat()
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    task = asyncio.create_task(_loop())
    logger.info("[Village] Heartbeat loop started (every %ds)", HEARTBEAT_INTERVAL)
    return task


# ── 类封装（供 main.py 等模块以 OO 方式调用） ──


class VillageConnector:
    """Village OS 连接器 — 封装函数式接口为面向对象。

    用法:
        connector = VillageConnector()
        await connector.send_message("agent-2", "hello")
    """

    def __init__(self):
        self.enabled = ENABLED
        self.node_name = NODE_NAME
        self.village_name = VILLAGE_NAME

    async def register_node(self):
        """注册本节点到 Village OS。"""
        return await register()

    async def heartbeat(self):
        """发送心跳。"""
        return await send_heartbeat()

    async def send_message(self, to: str, content: str):
        """向另一个 Agent 发送消息。"""
        return await send_message(to, content)

    async def send_email(self, to: str, subject: str, body: str):
        """发送邮件。"""
        return await send_email(to, subject, body)

    async def check_health(self) -> dict:
        """检查 Village OS 健康状态。"""
        return await check_health()

    def get_status(self) -> dict:
        """返回连接器状态。"""
        return {
            "enabled": self.enabled,
            "node_name": self.node_name,
            "village_name": self.village_name,
        }
