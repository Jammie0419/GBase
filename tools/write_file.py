# SPDX-License-Identifier: MIT
"""
tools/write_file.py

写FileTools。与 read_file 对称，供 LLM 按需Create/ModifyFile。
安全约束：
- Only write within opprime workspace directories
- 自动Create父Directory
- [Evolution #7] Auto-backup before overwrite: originals saved to .gbase/.backups/
"""

import asyncio
import logging
import os
from pathlib import Path

from lib.backup import BACKUP_DIR, _is_core_file, backup_file
from lib.toolkit import get_global, tool

logger = logging.getLogger(__name__)


async def _async_evolution_check(evolution_engine, rel_path: str, abs_path: str, content: str, old_size: int):
    """异步执行进化引擎评估（不阻塞工具返回）。"""
    try:
        import asyncio
        from lib.evolution.engine import full_evolution_cycle

        # 计算新文件大小
        new_size = len(content.encode("utf-8"))

        # 直接调用进化周期函数，传入已捕获的旧大小（避免重复读取/写入）
        result = await asyncio.to_thread(
            full_evolution_cycle, abs_path, old_size, new_size, content
        )
        if result and result.get("conclusion"):
            logger.info(
                "🧬 进化引擎评估 %s: %s",
                rel_path,
                result["conclusion"],
            )
    except Exception as e:
        logger.debug("进化评估异常（不影响主流程）: %s", e)

# ──────────────────────────────────────────────
# 🏡 自找家门：每个实例自动推导自己的家Directory
# Strategy: use parent of __file__'s tools/ dir as home
# ──────────────────────────────────────────────
_my_home = str(Path(__file__).resolve().parent.parent)

# 允许Write的根Directory
# 优先级：环境变量 > 自动推导家Directory > Default硬编码
_env_roots = os.environ.get("OPPRIME_ALLOWED_ROOTS")
if _env_roots:
    ALLOWED_ROOTS = [r.strip() for r in _env_roots.split(os.pathsep) if r.strip()]
    # 保证家Directory一定在允许列表里（即使环境变量忘了写）
    if _my_home not in ALLOWED_ROOTS:
        ALLOWED_ROOTS.insert(0, _my_home)
else:
    # 自动推导 + 常用公共Directory作为 fallback
    _common_roots = [
        os.path.expanduser("~"),
        os.path.expanduser("~/.qclaw"),
        os.path.expanduser("~/Projects"),
        "/home",  # 云端DefaultDirectory
    ]
    ALLOWED_ROOTS = [_my_home] + [r for r in _common_roots if r != _my_home]

# 始终允许写入当前工作目录
_CWD = os.path.abspath(os.getcwd())
if _CWD not in ALLOWED_ROOTS:
    ALLOWED_ROOTS.insert(0, _CWD)


def _resolve_path(filepath: str) -> tuple[str, str]:
    """解析FilePath，返回 (绝对Path, ErrorInfo)。"""
    expanded = os.path.expanduser(filepath)
    expanded = os.path.abspath(expanded)

    resolved_roots = [os.path.abspath(os.path.expanduser(r)) for r in ALLOWED_ROOTS]
    # 跨平台路径前缀检查（兼容 Windows 反斜杠）
    allowed = any(
        (expanded.startswith(root + os.sep) or expanded.startswith(root + "/") or expanded == root)
        for root in resolved_roots
    )

    if not allowed:
        return "", (
            f"Write被拒绝：Path {expanded} 不在允许范围内。\n"
            f"允许的根Directory：\n" + "\n".join(f"  - {r}" for r in ALLOWED_ROOTS)
        )

    parent = os.path.dirname(expanded)
    os.makedirs(parent, exist_ok=True)

    return expanded, ""


def _build_context(filepath: str) -> str:
    """构建File上下文Summary（供 LLM 判断是否还要继续改）。"""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return "(File刚Create，暂None内容)"

    lines = content.split("\n")
    total = len(lines)

    if total <= 20:
        preview = content
    else:
        first = "\n".join(lines[:5])
        last = "\n".join(lines[-5:])
        preview = f"{first}\n... (中间 {total - 10} 行) ...\n{last}"

    return f"File已Write ({total} 行, {len(content)} 字符):\n```\n{preview}\n```"


@tool()
async def write_file(filepath: str, content: str, mode: str = "w") -> dict:
    """Create或ModifyFile。Write前自动备份（如果Enabled了 backup 模块）。

    Args:
        filepath: FilePath（绝对Path或相对于 ~/opprime 的相对Path）
        content: File内容（文本）
        mode: Write模式，'w' 覆盖Write（Default），'a' 追加

    Returns:
        包含Write结果的字典：path / size / context / backup / error
    """
    path, err = _resolve_path(filepath)
    if err:
        return {"error": err}

    if mode not in ("w", "a"):
        return {"error": f"不支持的 mode: {mode}，仅支持 'w'（覆盖）或 'a'（追加）"}

    # ── 波段一：写前自动备份 ──
    backup_id = None
    backup_note = ""
    if mode == "w" and os.path.exists(path):
        backup_id = backup_file(path)
        if backup_id:
            is_core = _is_core_file(path)
            tag = "🔴检查点" if is_core else "📦备份"
            backup_note = f"\n{tag}: 原File已备份到 {BACKUP_DIR}/{backup_id}"

    # ── 自进化：写入前捕获旧文件大小（用于进化引擎评估）──
    old_size = 0
    if mode == "w" and os.path.exists(path):
        try:
            old_size = os.path.getsize(path)
        except Exception:
            old_size = 0

    try:
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)

        size = os.path.getsize(path)
        context = _build_context(path)

        result = {
            "path": path,
            "size": size,
            "mode": mode,
            "context": context,
            "backup": backup_note.strip() if backup_note else None,
            "note": "如需继续编辑此File，再次调用 write_file 即可（mode='w' 覆盖）。",
        }
        if backup_id:
            result["backup_id"] = backup_id
            result["restore_cmd"] = f"用 rollback_restore(backup_id='{backup_id}') 可回滚"

        # ── 自进化：文件写入后触发进化引擎评估 ──
        try:
            _evolution = get_global("evolution_engine")
            if _evolution and mode == "w":  # 只评估覆盖写，不评估追加
                # 计算相对路径用于触发规则匹配
                _rel_path = os.path.relpath(path, os.getcwd())
                asyncio.create_task(
                    _async_evolution_check(_evolution, _rel_path, path, content, old_size)
                )
        except Exception as _evo_err:
            logger.debug("进化引擎触发失败（不阻塞主流程）: %s", _evo_err)

        return result
    except Exception as e:
        return {"error": f"Write失败: {e}"}
