# SPDX-License-Identifier: MIT
"""
lib/self_improving.py

自我改进引擎 — 当新信息被吸收时，分析对自身能力的影响并触发调整。

实现 EVOLUTION.md 中描述的：
"检测到新信息被吸收时 → 触发 self-improving：这些新信息对我的能力有什么影响？需要调整什么吗？"

设计原则：
- 异步执行：不阻塞主流程
- 基于规则 + 启发式：快速判断，不需要 LLM
- 可累积：改进建议写入日志，供后续执行
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 改进规则库 ─────────────────────────────────────

_IMPROVING_RULES = [
    {
        "name": "knowledge_gap_filled",
        "check": lambda ctx: (
            ctx.get("type") == "knowledge"
            and ctx.get("auto_imported", False)
        ),
        "action": "skill_suggestion",
        "suggestion": "知识库已自动导入，建议使用 search_knowledge 验证检索效果",
        "priority": "medium",
    },
    {
        "name": "error_pattern_learned",
        "check": lambda ctx: (
            ctx.get("type") == "experience"
            and "error" in ctx.get("summary", "").lower()
        ),
        "action": "tool_hint_update",
        "suggestion": "从错误经验中学习，考虑更新工具参数提示",
        "priority": "high",
    },
    {
        "name": "skill_created",
        "check": lambda ctx: (
            ctx.get("type") == "knowledge"
            and "技能" in ctx.get("summary", "")
        ),
        "action": "skill_test",
        "suggestion": "新技能已创建，建议在下次对话中测试其效果",
        "priority": "medium",
    },
    {
        "name": "recurring_issue",
        "check": lambda ctx: (
            ctx.get("type") == "experience"
            and ctx.get("rule") in ("tool_excessive", "knowledge_miss")
        ),
        "action": "workflow_optimization",
        "suggestion": "重复出现问题 ({rule})，考虑优化工作流程或创建专用技能",
        "priority": "high",
    },
    {
        "name": "new_capability",
        "check": lambda ctx: (
            ctx.get("type") == "knowledge"
            and any(kw in ctx.get("summary", "") for kw in ["工具", "技能", "功能", "能力"])
        ),
        "action": "capability_awareness",
        "suggestion": "新能力已学习，后续遇到相关任务时优先使用",
        "priority": "low",
    },
]


class SelfImprovingEngine:
    """自我改进引擎。"""

    def __init__(self):
        self._improvement_log = []

    def analyze_and_improve(self, entry_type: str, entry_data: dict) -> list[dict]:
        """分析新吸收的信息，生成改进建议。

        Args:
            entry_type: "knowledge" | "experience" | "skills"
            entry_data: 写入的数据内容

        Returns:
            改进建议列表: [{"action": str, "suggestion": str, "priority": str}]
        """
        # 构建分析上下文
        summary = ""
        if isinstance(entry_data, dict):
            summary = entry_data.get("summary", "")
            if not summary and "content" in entry_data:
                content = entry_data["content"]
                if isinstance(content, dict):
                    summary = content.get("summary", content.get("title", ""))
                elif isinstance(content, str):
                    summary = content[:200]

        context = {
            "type": entry_type,
            "summary": summary,
            "entry": entry_data,
        }
        # 如果 entry_data 是 dict，展平到 context 中
        if isinstance(entry_data, dict):
            context.update(entry_data)

        improvements = []

        # 应用规则
        for rule in _IMPROVING_RULES:
            try:
                if rule["check"](context):
                    suggestion = rule["suggestion"].format(**context)
                    improvements.append({
                        "action": rule["action"],
                        "suggestion": suggestion,
                        "priority": rule["priority"],
                        "rule": rule["name"],
                    })
                    logger.info(
                        "🔧 Self-improving [%s]: %s",
                        rule["name"],
                        suggestion,
                    )
            except Exception as e:
                logger.debug("self-improving 规则 %s 检查失败: %s", rule["name"], e)

        # 记录改进日志
        if improvements:
            self._improvement_log.extend(improvements)
            self._log_improvements(entry_type, summary, improvements)

        return improvements

    def _log_improvements(self, entry_type: str, summary: str, improvements: list[dict]):
        """记录改进到日志文件。"""
        try:
            log_file = Path(__file__).parent.parent / "self-improving-log.md"

            existing = ""
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    existing = f.read()

            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            improvements_text = "\n".join(
                f"- [{imp['priority']}] {imp['suggestion']}"
                for imp in improvements
            )

            entry = f"""
## {timestamp} - 自我改进触发

**触发来源**: {entry_type}
**摘要**: {summary[:200]}

**改进建议**:
{improvements_text}

---
"""

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(existing + entry)

        except Exception as e:
            logger.debug("写入 self-improving 日志失败: %s", e)

    def get_improvement_stats(self) -> dict:
        """获取改进统计。"""
        priority_counts = {}
        action_counts = {}
        for imp in self._improvement_log:
            priority = imp.get("priority", "unknown")
            action = imp.get("action", "unknown")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            action_counts[action] = action_counts.get(action, 0) + 1

        return {
            "total_improvements": len(self._improvement_log),
            "by_priority": priority_counts,
            "by_action": action_counts,
        }


# ── 全局实例 ─────────────────────────────────────

_self_improving_engine: SelfImprovingEngine | None = None


def get_self_improving_engine() -> SelfImprovingEngine:
    """获取全局 self-improving 引擎实例。"""
    global _self_improving_engine
    if _self_improving_engine is None:
        _self_improving_engine = SelfImprovingEngine()
    return _self_improving_engine


def trigger_self_improving(entry_type: str, entry_data: dict) -> list[dict]:
    """触发自我改进分析（便捷函数）。"""
    engine = get_self_improving_engine()
    return engine.analyze_and_improve(entry_type, entry_data)
