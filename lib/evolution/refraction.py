# SPDX-License-Identifier: MIT
"""
lib/refraction.py

步骤级反思引擎 — 每次工具调用后评估：结果对吗？还差多远？继续还是换方向？

这是自进化系统的核心组件之一，实现 EVOLUTION.md 中描述的：
"每次工具调用后 → 触发 refraction：调用结果对吗？还差多远？需要继续还是换方向？"

设计原则：
- 轻量级：不阻塞主流程，异步执行
- 基于规则：快速判断，不需要 LLM 调用
- 可累积：观察结果写入 trace，供 trace_review 后续分析
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── 评估规则库 ─────────────────────────────────────

_REFRACTION_RULES = [
    {
        "name": "error_persistent",
        "check": lambda ctx: ctx.get("consecutive_errors", 0) >= 3,
        "verdict": "fail",
        "recommendation": "⚠️ 连续失败 {consecutive_errors} 次！必须立即停止当前方案，重新规划。检查：1) 工具参数是否正确 2) 是否需要换用其他工具 3) 环境是否就绪",
        "severity": "high",
    },
    {
        "name": "command_not_found",
        "check": lambda ctx: (
            ctx.get("has_error", False)
            and any(
                keyword in ctx.get("error_msg", "").lower()
                for keyword in [
                    "not recognized",  # Windows: 'pwd' is not recognized
                    "不是内部或外部命令",  # Windows Chinese
                    "command not found",  # Linux/Mac
                    "未找到命令",  # Linux Chinese
                ]
            )
        ),
        "verdict": "fail",
        "recommendation": "🚫 命令不存在！立即检查操作系统环境。Windows 使用 dir/type/echo，Linux/Mac 使用 ls/cat/echo。不要混用！",
        "severity": "high",
    },
    {
        "name": "tool_loop_detected",
        "check": lambda ctx: (
            ctx.get("same_tool_failures", 0) >= 2
            and ctx.get("consecutive_errors", 0) >= 2
        ),
        "verdict": "fail",
        "recommendation": "🔄 检测到工具循环失败！同一工具连续失败 {same_tool_failures} 次。必须换用其他工具或彻底改变方案！",
        "severity": "high",
    },
    {
        "name": "result_empty",
        "check": lambda ctx: (
            ctx.get("has_error", False) is False
            and ctx.get("result_size", 0) < 10
            and ctx.get("tool_type") not in ("write", "delete", "execute")
        ),
        "verdict": "warning",
        "recommendation": "结果为空，可能查询条件不对或目标不存在",
        "severity": "medium",
    },
    {
        "name": "slow_execution",
        "check": lambda ctx: ctx.get("duration_ms", 0) > 10000,
        "verdict": "warning",
        "recommendation": "执行耗时 {duration_ms}ms (>10s)，考虑是否有更高效的方式",
        "severity": "low",
    },
    {
        "name": "large_result",
        "check": lambda ctx: ctx.get("result_size", 0) > 50000,
        "verdict": "info",
        "recommendation": "结果很大 ({result_size} 字符)，后续处理注意内存和 token 限制",
        "severity": "low",
    },
    {
        "name": "file_not_found",
        "check": lambda ctx: (
            ctx.get("has_error", False)
            and "not found" in ctx.get("error_msg", "").lower()
        ),
        "verdict": "fail",
        "recommendation": "文件不存在，检查路径或先创建文件",
        "severity": "high",
    },
    {
        "name": "permission_denied",
        "check": lambda ctx: (
            ctx.get("has_error", False)
            and ("permission" in ctx.get("error_msg", "").lower()
                 or "denied" in ctx.get("error_msg", "").lower())
        ),
        "verdict": "fail",
        "recommendation": "权限不足，检查文件权限或换目录",
        "severity": "high",
    },
    {
        "name": "search_no_results",
        "check": lambda ctx: (
            ctx.get("tool_name", "").startswith("search")
            and ctx.get("result_size", 0) < 50
        ),
        "verdict": "warning",
        "recommendation": "搜索无结果，尝试换关键词或扩大搜索范围",
        "severity": "medium",
    },
    {
        "name": "success_pattern",
        "check": lambda ctx: (
            not ctx.get("has_error", False)
            and ctx.get("result_size", 0) > 100
            and ctx.get("duration_ms", 0) < 5000
        ),
        "verdict": "success",
        "recommendation": "执行成功，可以继续当前方案",
        "severity": "none",
    },
]


class RefractionEngine:
    """步骤级反思引擎。"""

    def __init__(self):
        self._context = {
            "consecutive_errors": 0,
            "total_calls": 0,
            "total_errors": 0,
            "last_tool_name": None,
            "same_tool_failures": 0,  # 同一工具连续失败次数
        }

    def evaluate(
        self,
        tool_name: str,
        args: dict,
        result: Any,
        has_error: bool,
        duration_ms: float,
    ) -> dict:
        """评估一次工具调用。

        Args:
            tool_name: 工具名称
            args: 工具参数
            result: 工具返回结果
            has_error: 是否有错误
            duration_ms: 执行耗时

        Returns:
            {
                "verdict": "success" | "warning" | "fail" | "info",
                "recommendation": str,
                "severity": "high" | "medium" | "low" | "none",
                "rule": str | None,
                "observations": list[str]
            }
        """
        # 更新上下文
        self._context["total_calls"] += 1
        if has_error:
            self._context["consecutive_errors"] += 1
            self._context["total_errors"] += 1
            # 跟踪同一工具连续失败
            if self._context["last_tool_name"] == tool_name:
                self._context["same_tool_failures"] += 1
            else:
                self._context["same_tool_failures"] = 1
            self._context["last_tool_name"] = tool_name
        else:
            self._context["consecutive_errors"] = 0
            self._context["same_tool_failures"] = 0
            self._context["last_tool_name"] = tool_name

        # 构建评估上下文
        result_str = json.dumps(result, ensure_ascii=False) if result else ""
        error_msg = str(result.get("error", "")) if isinstance(result, dict) and has_error else ""

        eval_context = {
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "has_error": has_error,
            "error_msg": error_msg,
            "duration_ms": duration_ms,
            "result_size": len(result_str),
            "tool_type": self._classify_tool(tool_name),
            **self._context,
        }

        # 收集观察结果
        observations = []

        # 应用规则
        matched_rule = None
        for rule in _REFRACTION_RULES:
            try:
                if rule["check"](eval_context):
                    matched_rule = rule
                    recommendation = rule["recommendation"].format(**eval_context)
                    observations.append(f"[{rule['name']}] {recommendation}")
            except Exception as e:
                logger.debug("refraction 规则 %s 检查失败: %s", rule["name"], e)

        # 返回评估结果
        if matched_rule:
            return {
                "verdict": matched_rule["verdict"],
                "recommendation": matched_rule["recommendation"].format(**eval_context),
                "severity": matched_rule["severity"],
                "rule": matched_rule["name"],
                "observations": observations,
            }
        else:
            # 没有匹配规则，默认为成功
            return {
                "verdict": "success",
                "recommendation": "执行正常",
                "severity": "none",
                "rule": None,
                "observations": observations,
            }

    def _classify_tool(self, tool_name: str) -> str:
        """给工具分类，用于规则匹配。"""
        tn = tool_name.lower()
        if "read" in tn:
            return "read"
        if "write" in tn or "edit" in tn:
            return "write"
        if "search" in tn or "find" in tn:
            return "search"
        if "exec" in tn or "run" in tn:
            return "execute"
        if "delete" in tn or "remove" in tn:
            return "delete"
        return "other"

    def get_stats(self) -> dict:
        """获取当前统计。"""
        return {
            "total_calls": self._context["total_calls"],
            "total_errors": self._context["total_errors"],
            "consecutive_errors": self._context["consecutive_errors"],
            "error_rate": (
                self._context["total_errors"] / self._context["total_calls"]
                if self._context["total_calls"] > 0
                else 0
            ),
        }

    def reset(self):
        """重置上下文。"""
        self._context = {
            "consecutive_errors": 0,
            "total_calls": 0,
            "total_errors": 0,
            "last_tool_name": None,
            "same_tool_failures": 0,
        }


# ── 全局实例 ─────────────────────────────────────

_refraction_engine: RefractionEngine | None = None


def get_refraction_engine() -> RefractionEngine:
    """获取全局 refraction 引擎实例。"""
    global _refraction_engine
    if _refraction_engine is None:
        _refraction_engine = RefractionEngine()
    return _refraction_engine


def evaluate_tool_call(
    tool_name: str,
    args: dict,
    result: Any,
    has_error: bool,
    duration_ms: float,
) -> dict:
    """评估工具调用（便捷函数）。"""
    engine = get_refraction_engine()
    return engine.evaluate(tool_name, args, result, has_error, duration_ms)
