# SPDX-License-Identifier: MIT
"""
tools/session_tools.py

Web 聊天会话管理工具：列出、查看会话。
"""

import json
import re
import time
from pathlib import Path

from lib.compat import GBASE_DATA_DIR

_SESSIONS_DIR = GBASE_DATA_DIR / "sessions"


def _strip_metadata_prefix(content: str) -> str:
    """去除 kernel 注入的元数据前缀。"""
    content = re.sub(r'^\[task_profile:[^\]]*\]\s*', '', content)
    content = re.sub(r'^\[ArchiveSearch:[^\]]*\]\s*', '', content)
    content = re.sub(r'^\[Memory:[^\]]*\]\s*', '', content)
    content = re.sub(r'^\[[A-Za-z_]+:[^\]]{0,200}\]\s*', '', content)
    return content.strip()


def _get_session_title(filepath: Path) -> str:
    """从 JSONL 的第一条 user 消息提取会话标题。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get('role') == 'user':
                        content = msg.get('content', '')
                        content = _strip_metadata_prefix(content)
                        return content[:80] if content else '(空)'
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return '(无法读取)'


def _count_messages(filepath: Path) -> int:
    """统计会话消息数。"""
    count = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
    except OSError:
        pass
    return count


from lib.toolkit import tool


@tool()
async def list_sessions(limit: int = 20) -> dict:
    """列出最近的 web 聊天记录（会话列表）。返回每个会话的 ID、标题、消息数和最后活跃时间。"""
    if not _SESSIONS_DIR.exists():
        return {"sessions": [], "total": 0, "ok": True}

    sessions = []
    for filepath in _SESSIONS_DIR.glob("*.jsonl"):
        stat = filepath.stat()
        session_id = filepath.stem
        title = _get_session_title(filepath)
        msg_count = _count_messages(filepath)
        sessions.append({
            "session_id": session_id,
            "title": title,
            "messages": msg_count,
            "last_active": stat.st_mtime,
            "last_active_human": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            "size_bytes": stat.st_size,
        })

    # 按最后活跃时间倒序排列
    sessions.sort(key=lambda s: s["last_active"], reverse=True)

    return {
        "sessions": sessions[:limit],
        "total": len(sessions),
        "sessions_dir": str(_SESSIONS_DIR),
        "ok": True,
    }


@tool()
async def get_session(session_id: str, max_messages: int = 50) -> dict:
    """查看指定 web 会话的详细消息内容。session_id 可从 list_sessions 获取。"""
    filepath = _SESSIONS_DIR / f"{session_id}.jsonl"
    if not filepath.exists():
        return {"error": f"会话不存在: {session_id}", "ok": False}

    messages = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    # 去除元数据前缀
                    if role == 'user':
                        content = _strip_metadata_prefix(content)
                    messages.append({
                        "role": role,
                        "content": content[:2000],  # 截断过长内容
                        "timestamp": msg.get('_ts', 0),
                    })
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        return {"error": f"读取失败: {e}", "ok": False}

    # 只返回最新的 max_messages 条
    return {
        "session_id": session_id,
        "messages": messages[-max_messages:],
        "total_messages": len(messages),
        "ok": True,
    }


@tool()
async def delete_session(session_id: str) -> dict:
    """删除指定的 web 会话记录。session_id 可从 list_sessions 获取。"""
    filepath = _SESSIONS_DIR / f"{session_id}.jsonl"
    if not filepath.exists():
        return {"error": f"会话不存在: {session_id}", "ok": False}

    try:
        filepath.unlink()
        return {"deleted": session_id, "ok": True}
    except OSError as e:
        return {"error": f"删除失败: {e}", "ok": False}
