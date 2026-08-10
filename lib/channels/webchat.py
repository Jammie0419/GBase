#!/usr/bin/env python3
"""
webchat.py — GBase WebSocket Chat Channel

A production-grade WebSocket chat backend for GBase agents.
Supports streaming responses, file uploads, knowledge injection, tool chain visibility,
and persistent chat sessions with history browsing.

Usage:
    channel = WebChatChannel(kernel, storage)
    app = channel.create_app()
"""

import asyncio
import base64
import contextlib
import json
import logging
import mimetypes
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from lib.compat import GBASE_DATA_DIR
from lib.session import JsonlSessionManager
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("gbase.webchat")


class WebChatChannel:
    """WebSocket-based chat channel with streaming responses."""

    def __init__(
        self,
        kernel: Any,
        storage: Any | None = None,
        data_dir: str | None = None,
        max_upload_mb: int = 10,
    ):
        self.kernel = kernel
        self.storage = storage
        self.data_dir = data_dir or str(GBASE_DATA_DIR)
        self.max_upload_mb = max_upload_mb
        self._static_dir = Path(__file__).parent.parent.parent / "webchat"
        self._sessions_dir = Path(self.data_dir) / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: dict[str, JsonlSessionManager] = {}

    def create_app(self, title: str = "GBase Web Chat") -> FastAPI:
        app = FastAPI(title=title)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Serve static files
        static_path = self._static_dir
        static_path.mkdir(parents=True, exist_ok=True)
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

        # Serve the main HTML page
        @app.get("/", response_class=HTMLResponse)
        async def index():
            html_path = static_path / "index.html"
            if html_path.exists():
                return HTMLResponse(html_path.read_text(encoding="utf-8"))
            return HTMLResponse("<h1>GBase Web Chat</h1><p>Frontend not found.</p>")

        @app.get("/health")
        async def health():
            return {"status": "ok", "app": "gbase-webchat"}

        # ── Session REST API ──────────────────────────────────────────

        @app.get("/api/sessions")
        async def list_sessions():
            """列出所有聊天会话，按更新时间倒序。"""
            sessions = self._scan_sessions()
            return {"sessions": sessions}

        @app.get("/api/sessions/{session_id}")
        async def get_session(session_id: str):
            """获取一个会话的所有消息。"""
            # 安全校验：session_id 只能是字母数字和 - _
            if not all(c.isalnum() or c in "-_" for c in session_id):
                return JSONResponse({"error": "invalid session_id"}, status_code=400)

            filepath = self._sessions_dir / f"{session_id}.jsonl"
            if not filepath.exists():
                return JSONResponse({"error": "session not found"}, status_code=404)

            messages = self._read_session_messages(str(filepath))
            meta = self._extract_session_meta(str(filepath))
            return {"session_id": session_id, "meta": meta, "messages": messages}

        @app.delete("/api/sessions/{session_id}")
        async def delete_session(session_id: str):
            """删除一个聊天会话（同步删除数据库文件）。"""
            if not all(c.isalnum() or c in "-_" for c in session_id):
                return JSONResponse({"error": "invalid session_id"}, status_code=400)

            filepath = self._sessions_dir / f"{session_id}.jsonl"
            if not filepath.exists():
                return JSONResponse({"error": "session not found"}, status_code=404)

            try:
                # 先关闭文件句柄（Windows 下不关闭无法删除）
                self._close_session(session_id)
                filepath.unlink()
                logger.info("Session deleted: %s", session_id)
                return {"status": "ok", "session_id": session_id}
            except Exception as e:
                logger.error("Failed to delete session %s: %s", session_id, e)
                return JSONResponse({"error": str(e)}, status_code=500)

        @app.post("/ask")
        async def ask_http(request: Request):
            """HTTP fallback for non-streaming chat (for testing)."""
            body = await request.json()
            message = body.get("message", "")
            response = await self.kernel.run(
                user_message=message,
                platform="webchat",
            )
            return JSONResponse({"reply": response})

        # WebSocket chat endpoint with session support
        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            logger.info("WebSocket connected")

            # Per-connection session state
            session_id = None
            session_mgr = None

            # Send config (model name etc.) to client on connect
            try:
                await ws.send_json({
                    "type": "config",
                    "model": getattr(self.kernel, "model", "unknown"),
                })
            except Exception:
                pass

            try:
                while True:
                    raw = await ws.receive_text()

                    # Parse incoming message (could be text or JSON with files)
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        data = {"type": "text", "content": raw}

                    msg_type = data.get("type", "text")

                    # ── Session management messages ──
                    if msg_type == "new_session":
                        # Create a brand new session
                        session_id = self._generate_session_id()
                        session_mgr = self._create_session(session_id)
                        await ws.send_json({
                            "type": "session_created",
                            "session_id": session_id,
                        })
                        logger.info("New session created: %s", session_id)
                        continue

                    if msg_type == "load_session":
                        load_sid = data.get("session_id", "")
                        if not load_sid or not all(c.isalnum() or c in "-_" for c in load_sid):
                            await ws.send_json({"type": "error", "content": "invalid session_id"})
                            continue
                        filepath = self._sessions_dir / f"{load_sid}.jsonl"
                        if not filepath.exists():
                            await ws.send_json({"type": "error", "content": "session not found"})
                            continue
                        session_id = load_sid
                        session_mgr = self._get_or_load_session(session_id)
                        # Send history to client
                        messages = self._read_session_messages(str(filepath))
                        await ws.send_json({
                            "type": "session_loaded",
                            "session_id": session_id,
                            "messages": messages,
                        })
                        logger.info("Session loaded: %s (%d messages)", session_id, len(messages))
                        continue

                    # ── Auto-create session if none exists ──
                    if session_mgr is None and msg_type == "text":
                        session_id = self._generate_session_id()
                        session_mgr = self._create_session(session_id)
                        await ws.send_json({
                            "type": "session_created",
                            "session_id": session_id,
                        })
                        logger.info("Auto-created session: %s", session_id)

                    if msg_type == "text":
                        user_msg = data.get("content", "").strip()
                        if not user_msg:
                            continue

                        # Notify streaming start
                        await ws.send_json({"type": "status", "content": "processing"})

                        # Send knowledge hits if available
                        try:
                            if self.storage:
                                hits = self.storage.search(user_msg)
                                if hits:
                                    await ws.send_json(
                                        {
                                            "type": "knowledge",
                                            "content": hits[:5],
                                        }
                                    )
                        except Exception:
                            pass

                        # Run kernel with session context
                        try:
                            response = await self.kernel.run(
                                user_message=user_msg,
                                platform="webchat",
                                session=session_mgr,
                            )

                            # Stream response character by character for cool effect
                            # but batch into chunks for practicality
                            chunk_size = 20
                            for i in range(0, len(response), chunk_size):
                                chunk = response[i : i + chunk_size]
                                await ws.send_json(
                                    {
                                        "type": "chunk",
                                        "content": chunk,
                                    }
                                )
                                await asyncio.sleep(0.01)  # Small delay for streaming feel

                            # Send completion marker with metrics
                            await ws.send_json(
                                {
                                    "type": "done",
                                    "content": response,
                                    "meta": {
                                        "length": len(response),
                                        "session_id": session_id,
                                    },
                                }
                            )

                        except Exception as e:
                            logger.error("Kernel error: %s", e, exc_info=True)
                            await ws.send_json(
                                {
                                    "type": "error",
                                    "content": str(e),
                                }
                            )

                    elif msg_type == "file":
                        # File upload handling
                        file_name = data.get("name", "unknown")
                        file_data_b64 = data.get("data", "")
                        file_mime = data.get("mime", "")

                        if not file_data_b64:
                            await ws.send_json({"type": "error", "content": "No file data"})
                            continue

                        try:
                            file_bytes = base64.b64decode(file_data_b64)
                            file_size_mb = len(file_bytes) / (1024 * 1024)

                            if file_size_mb > self.max_upload_mb:
                                await ws.send_json(
                                    {
                                        "type": "error",
                                        "content": f"File too large: {file_size_mb:.1f}MB (max {self.max_upload_mb}MB)",
                                    }
                                )
                                continue

                            # Save to uploads
                            upload_dir = Path(self.data_dir) / "uploads"
                            upload_dir.mkdir(parents=True, exist_ok=True)
                            safe_name = file_name.replace("/", "_").replace("\\", "_")
                            save_path = upload_dir / safe_name
                            save_path.write_bytes(file_bytes)

                            # Analyze content
                            result = await self._process_upload(file_name, file_bytes, file_mime)

                            await ws.send_json(
                                {
                                    "type": "file_processed",
                                    "content": result,
                                    "meta": {"name": file_name, "size_kb": len(file_bytes) // 1024},
                                }
                            )

                        except Exception as e:
                            logger.error("File processing error: %s", e)
                            await ws.send_json(
                                {
                                    "type": "error",
                                    "content": f"File processing failed: {e}",
                                }
                            )

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.error("WebSocket error: %s", e, exc_info=True)
                with contextlib.suppress(Exception):
                    await ws.close()

        return app

    # ── Session Management Helpers ────────────────────────────────

    def _generate_session_id(self) -> str:
        """生成唯一的会话 ID。"""
        return f"chat-{int(time.time())}-{uuid.uuid4().hex[:8]}"

    def _create_session(self, session_id: str) -> JsonlSessionManager:
        """创建新的会话 JSONL 文件并返回 SessionManager。"""
        filepath = self._sessions_dir / f"{session_id}.jsonl"
        mgr = JsonlSessionManager(str(filepath))
        self._active_sessions[session_id] = mgr
        return mgr

    def _get_or_load_session(self, session_id: str) -> JsonlSessionManager:
        """获取已缓存的 session 或从文件加载。"""
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        filepath = self._sessions_dir / f"{session_id}.jsonl"
        mgr = JsonlSessionManager(str(filepath))
        self._active_sessions[session_id] = mgr
        return mgr

    def _close_session(self, session_id: str):
        """关闭并移除一个 session 的文件句柄。"""
        mgr = self._active_sessions.pop(session_id, None)
        if mgr:
            with contextlib.suppress(Exception):
                mgr.close()

    @staticmethod
    def _strip_metadata_prefix(content: str) -> str:
        """去掉 kernel 注入的各种元数据前缀，保留用户原始消息。"""
        # [task_profile: scope=... | complexity=... | ...] 前缀
        content = re.sub(r'^\[task_profile:[^\]]*\]\s*', '', content)
        # [ArchiveSearch: ...] 前缀
        content = re.sub(r'^\[ArchiveSearch:[^\]]*\]\s*', '', content)
        # [Memory: ...] 前缀
        content = re.sub(r'^\[Memory:[^\]]*\]\s*', '', content)
        # 通用 [xxx: ...] 方括号前缀（保守匹配，只去开头的）
        content = re.sub(r'^\[[A-Za-z_]+:[^\]]{0,200}\]\s*', '', content)
        return content.strip()

    def _extract_session_meta(self, filepath: str) -> dict:
        """从 JSONL 文件中提取会话元数据（标题、时间、消息数）。"""
        title = ""
        first_ts = 0.0
        last_ts = 0.0
        msg_count = 0

        try:
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    etype = entry.get("type", "")
                    ts = entry.get("_ts", 0)

                    if ts > 0:
                        if first_ts == 0:
                            first_ts = ts
                        last_ts = ts

                    if etype in ("user", "assistant"):
                        msg_count += 1
                        # 取第一条用户消息作为标题
                        if not title and etype == "user":
                            content = entry.get("content", "")
                            # 去掉 kernel 注入的元数据前缀
                            content = self._strip_metadata_prefix(content)
                            title = content[:60] if content else ""
                    elif etype == "compaction":
                        # compaction 级别越高，summary 越有代表性
                        summary = entry.get("summary", "")
                        if summary:
                            title = summary[:60]
        except Exception as e:
            logger.warning("Failed to extract session meta from %s: %s", filepath, e)

        return {
            "title": title or "新对话",
            "first_ts": first_ts,
            "last_ts": last_ts,
            "message_count": msg_count,
        }

    def _read_session_messages(self, filepath: str) -> list[dict]:
        """读取会话中的所有消息（用于前端展示）。"""
        messages = []
        try:
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    etype = entry.get("type", "")
                    if etype in ("user", "assistant"):
                        content = entry.get("content", "")
                        # 展示时去掉 kernel 注入的元数据前缀
                        if etype == "user":
                            content = self._strip_metadata_prefix(content)
                        messages.append({
                            "role": entry.get("role", etype),
                            "content": content,
                            "timestamp": entry.get("_ts", 0),
                        })
        except Exception as e:
            logger.warning("Failed to read session messages from %s: %s", filepath, e)
        return messages

    def _scan_sessions(self) -> list[dict]:
        """扫描所有会话文件，返回元数据列表（按最后更新时间倒序）。"""
        sessions = []
        if not self._sessions_dir.exists():
            return sessions

        for filepath in self._sessions_dir.glob("*.jsonl"):
            session_id = filepath.stem
            meta = self._extract_session_meta(str(filepath))
            meta["session_id"] = session_id
            # 从文件名获取最后修改时间作为 fallback
            if meta["last_ts"] == 0:
                meta["last_ts"] = filepath.stat().st_mtime
            sessions.append(meta)

        # 按最后更新时间倒序
        sessions.sort(key=lambda s: s.get("last_ts", 0), reverse=True)
        return sessions

    async def _process_upload(self, name: str, data: bytes, mime: str) -> dict:
        """Process an uploaded file and extract usable content."""
        ext = Path(name).suffix.lower()
        result = {
            "name": name,
            "mime": mime or mimetypes.guess_type(name)[0] or "application/octet-stream",
            "size": len(data),
            "preview": "",
            "content": "",
        }

        # Text files
        if ext in (
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".yaml",
            ".yml",
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".xml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".log",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
        ):
            try:
                text = data.decode("utf-8")
                result["content"] = text
                result["preview"] = text[:500]
            except UnicodeDecodeError:
                result["preview"] = "[Binary text file — cannot decode as UTF-8]"

        # PDF
        elif ext == ".pdf":
            try:
                import io

                import PyPDF2

                pdf_file = io.BytesIO(data)
                reader = PyPDF2.PdfReader(pdf_file)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                result["content"] = text
                result["preview"] = text[:500]
                result["meta"] = {"pages": len(reader.pages)}
            except ImportError:
                result["preview"] = "[PDF support requires: pip install PyPDF2]"
            except Exception as e:
                result["preview"] = f"[PDF parse error: {e}]"

        # Word documents
        elif ext in (".docx", ".doc"):
            try:
                import docx

                doc = docx.Document(io.BytesIO(data))
                text = "\n".join(p.text for p in doc.paragraphs)
                result["content"] = text
                result["preview"] = text[:500]
            except ImportError:
                result["preview"] = "[DOCX support requires: pip install python-docx]"
            except Exception as e:
                result["preview"] = f"[DOCX parse error: {e}]"

        # Excel
        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl

                wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
                rows = []
                for ws in wb.worksheets[:1]:  # First sheet only
                    for row in ws.iter_rows(values_only=True):
                        rows.append(" | ".join(str(c) if c is not None else "" for c in row[:10]))
                text = "\n".join(rows[:100])
                result["content"] = text
                result["preview"] = text[:500]
            except ImportError:
                result["preview"] = "[Excel support requires: pip install openpyxl]"
            except Exception as e:
                result["preview"] = f"[Excel parse error: {e}]"

        # Images
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            import base64

            b64 = base64.b64encode(data).decode("utf-8")
            result["preview"] = f"data:{result['mime']};base64,{b64}"
            result["is_image"] = True

        # Default: binary
        else:
            result["preview"] = f"[Binary file: {name}, {len(data)} bytes]"

        return result
