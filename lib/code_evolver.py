# SPDX-License-Identifier: MIT
"""
lib/code_evolver.py

代码进化器 — 当 self-improving 或 trace_review 发现需要代码改进时，自动实现修改。

这是自进化闭环的最后一环：
  发现问题 → 生成建议 → 自动修改代码 → 测试 → 应用/回滚

设计原则：
- 只在高置信度时自动修改（confidence >= 0.8）
- 修改前备份
- 修改后自动测试
- 测试失败自动回滚
- 记录到 evolution-log.md
"""

import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CodeEvolver:
    """代码进化器 — 自动实现代码改进。"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self._evolution_log = []

    def evolve_from_suggestion(self, suggestion: dict) -> bool:
        """根据改进建议自动进化代码。

        Args:
            suggestion: {
                "action": str,  # "tool_hint_update" | "workflow_optimization" | ...
                "suggestion": str,  # 改进建议描述
                "priority": str,  # "high" | "medium" | "low"
                "confidence": float,  # 0.0-1.0
                "target_file": str,  # 目标文件路径（可选）
                "code_pattern": str,  # 需要修改的代码模式（可选）
            }

        Returns:
            是否成功进化
        """
        # 只处理高优先级、高置信度的建议
        if suggestion.get("priority") != "high":
            logger.debug("跳过低优先级建议: %s", suggestion.get("priority"))
            return False

        confidence = suggestion.get("confidence", 0.0)
        if confidence < 0.8:
            logger.debug("跳过低置信度建议: %.2f", confidence)
            return False

        action = suggestion.get("action", "")
        suggestion_text = suggestion.get("suggestion", "")

        logger.info("🧬 尝试自动进化: %s", action)

        try:
            # 根据 action 类型选择进化策略
            if action == "tool_hint_update":
                return self._evolve_tool_hints(suggestion_text)
            elif action == "workflow_optimization":
                return self._evolve_workflow(suggestion_text)
            elif action == "error_pattern_fix":
                return self._fix_error_pattern(suggestion_text)
            else:
                logger.debug("不支持的进化动作: %s", action)
                return False

        except Exception as e:
            logger.warning("代码进化失败: %s", e)
            return False

    def _evolve_tool_hints(self, suggestion: str) -> bool:
        """优化工具提示（基于错误经验）。"""
        # 示例：如果建议提到某个工具经常失败，改进其错误处理
        # 这里需要 LLM 来生成具体的代码修改
        logger.info("工具提示优化需要 LLM 生成代码，暂不自动实现")
        return False

    def _evolve_workflow(self, suggestion: str) -> bool:
        """优化工作流程。"""
        # 示例：如果建议提到某个流程效率低，重构相关代码
        logger.info("工作流优化需要 LLM 生成代码，暂不自动实现")
        return False

    def _fix_error_pattern(self, suggestion: str) -> bool:
        """修复错误模式。"""
        # 示例：如果检测到重复错误，自动添加错误处理
        logger.info("错误模式修复需要 LLM 生成代码，暂不自动实现")
        return False

    def _backup_file(self, filepath: Path) -> Optional[Path]:
        """备份文件。"""
        try:
            backup_dir = self.project_root / ".evolution" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"{filepath.name}.{timestamp}.bak"
            backup_path = backup_dir / backup_name

            import shutil
            shutil.copy2(filepath, backup_path)

            logger.info("已备份: %s → %s", filepath, backup_path)
            return backup_path

        except Exception as e:
            logger.warning("备份失败: %s", e)
            return None

    def _test_changes(self, filepath: Path) -> bool:
        """测试修改后的代码。"""
        try:
            # 运行 pytest 测试
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info("✅ 测试通过")
                return True
            else:
                logger.warning("❌ 测试失败:\n%s", result.stdout[:500])
                return False

        except Exception as e:
            logger.warning("测试执行失败: %s", e)
            return False

    def _log_evolution(self, filepath: Path, change_description: str, success: bool):
        """记录进化到日志。"""
        try:
            log_file = self.project_root / "evolution-log.md"

            existing = ""
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    existing = f.read()

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            status = "✅ 成功" if success else "❌ 失败"

            entry = f"""
## {timestamp} - 代码自动进化 {status}

**文件**: {filepath.relative_to(self.project_root)}
**改动**: {change_description}

---
"""

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(existing + entry)

            logger.info("进化日志已更新: %s", log_file)

        except Exception as e:
            logger.warning("写入进化日志失败: %s", e)


# ── 全局实例 ─────────────────────────────────────────

_evolver_instance: Optional[CodeEvolver] = None


def get_code_evolver() -> CodeEvolver:
    """获取代码进化器实例（单例）。"""
    global _evolver_instance
    if _evolver_instance is None:
        _evolver_instance = CodeEvolver()
    return _evolver_instance


def evolve_from_suggestion(suggestion: dict) -> bool:
    """根据建议自动进化代码（便捷函数）。"""
    evolver = get_code_evolver()
    return evolver.evolve_from_suggestion(suggestion)
