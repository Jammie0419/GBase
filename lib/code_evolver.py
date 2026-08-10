# SPDX-License-Identifier: MIT
"""
lib/code_evolver.py

代码进化器 — 用 LLM 生成代码修改，自动进化 GBase 自身的源代码。

这是自进化闭环的最后一环：
  发现问题 → LLM 生成修复代码 → self_edit 修改自身 → 测试 → 应用/回滚

设计原则：
- 只在高置信度时自动修改（confidence >= 0.8）
- 用 LLM 分析建议并生成代码修改
- 用 self_edit 工具修改自身源代码
- 修改后自动测试（pytest）
- 测试失败自动回滚
- 记录到 evolution-log.md
"""

import asyncio
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
    """代码进化器 — 用 LLM 生成代码修改，自动进化自身。"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self._evolution_log = []

    async def evolve_from_suggestion_async(self, suggestion: dict) -> bool:
        """根据改进建议自动进化代码（异步版本）。

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
        target_file = suggestion.get("target_file", "")

        logger.info("🧬 尝试自动进化: %s", action)

        try:
            # 用 LLM 生成代码修改
            code_changes = await self._generate_code_changes_with_llm(
                suggestion_text, action, target_file
            )

            if not code_changes:
                logger.warning("LLM 未能生成代码修改")
                return False

            # 应用代码修改
            return await self._apply_code_changes(code_changes)

        except Exception as e:
            logger.warning("代码进化失败: %s", e)
            return False

    def evolve_from_suggestion(self, suggestion: dict) -> bool:
        """根据改进建议自动进化代码（同步版本）。"""
        try:
            loop = asyncio.get_running_loop()
            # 如果在事件循环中，创建任务
            import asyncio
            task = loop.create_task(self.evolve_from_suggestion_async(suggestion))
            # 不等待结果，异步执行
            return True
        except RuntimeError:
            # 没有运行中的事件循环，创建新的
            return asyncio.run(self.evolve_from_suggestion_async(suggestion))

    async def _generate_code_changes_with_llm(
        self, suggestion: str, action: str, target_file: str
    ) -> Optional[list[dict]]:
        """用 LLM 分析建议并生成代码修改。

        Returns:
            [
                {
                    "file": "lib/safe_shell.py",
                    "old_code": "旧代码片段",
                    "new_code": "新代码片段",
                    "reason": "修改原因"
                }
            ]
        """
        try:
            # 构建 LLM 提示词
            prompt = self._build_evolution_prompt(suggestion, action, target_file)

            # 创建 LLM 客户端
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                base_url="https://api.deepseek.com/v1",
            )

            # 调用 LLM 生成代码修改
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "你是 GBase 自进化系统。根据建议生成代码修改。返回 JSON 格式。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                ),
                timeout=30,
            )

            # 解析 LLM 响应
            content = response.choices[0].message.content.strip()

            # 尝试提取 JSON
            code_changes = self._extract_json_from_response(content)

            if code_changes:
                logger.info("✅ LLM 生成了 %d 个代码修改", len(code_changes))
                return code_changes
            else:
                logger.warning("无法解析 LLM 响应")
                return None

        except Exception as e:
            logger.warning("LLM 代码生成失败: %s", e)
            return None

    def _build_evolution_prompt(
        self, suggestion: str, action: str, target_file: str
    ) -> str:
        """构建 LLM 提示词。"""
        prompt = f"""GBase 自进化系统检测到以下问题，需要你生成代码修改：

**问题类型**: {action}
**问题描述**: {suggestion}
"""

        if target_file:
            prompt += f"\n**目标文件**: {target_file}\n"

        prompt += """
请分析这个问题，并生成代码修改。要求：
1. 只修改 GBase 自身的源代码（lib/*.py, tools/*.py）
2. 使用精确的代码替换（old_code → new_code）
3. 确保修改后的代码语法正确
4. 返回 JSON 格式：

```json
[
  {
    "file": "lib/example.py",
    "old_code": "要替换的原始代码（必须精确匹配）",
    "new_code": "替换后的新代码",
    "reason": "修改原因"
  }
]
```

注意：
- old_code 必须与源文件中的代码完全匹配（包括缩进）
- 如果不确定具体修改，返回空数组 []
- 优先修复高优先级问题
"""

        return prompt

    def _extract_json_from_response(self, content: str) -> Optional[list[dict]]:
        """从 LLM 响应中提取 JSON。"""
        try:
            # 尝试提取 ```json ... ``` 块
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)

            # 尝试直接解析整个内容为 JSON
            return json.loads(content)

        except Exception as e:
            logger.debug("JSON 提取失败: %s", e)
            return None

    async def _apply_code_changes(self, code_changes: list[dict]) -> bool:
        """应用代码修改。"""
        success_count = 0

        for change in code_changes:
            try:
                file_path = change.get("file", "")
                old_code = change.get("old_code", "")
                new_code = change.get("new_code", "")
                reason = change.get("reason", "")

                if not file_path or not old_code or not new_code:
                    logger.warning("跳过不完整的代码修改")
                    continue

                # 构建完整路径
                full_path = self.project_root / file_path

                if not full_path.exists():
                    logger.warning("文件不存在: %s", full_path)
                    continue

                # 备份
                backup_path = self._backup_file(full_path)
                if not backup_path:
                    logger.warning("备份失败，跳过修改")
                    continue

                # 读取文件内容
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 检查 old_code 是否存在
                if old_code not in content:
                    logger.warning("旧代码不存在于文件中: %s", file_path)
                    continue

                # 替换代码
                new_content = content.replace(old_code, new_code, 1)

                # 写回文件
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                logger.info("✅ 已修改: %s", file_path)

                # 测试
                test_passed = self._test_changes(full_path)

                if test_passed:
                    logger.info("✅ 测试通过，保留修改")
                    self._log_evolution(full_path, reason, success=True)
                    success_count += 1
                else:
                    logger.warning("❌ 测试失败，回滚修改")
                    self._rollback_file(full_path, backup_path)
                    self._log_evolution(full_path, reason, success=False)

            except Exception as e:
                logger.warning("应用代码修改失败: %s", e)
                continue

        return success_count > 0

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

    def _rollback_file(self, filepath: Path, backup_path: Path):
        """回滚文件到备份版本。"""
        try:
            import shutil
            shutil.copy2(backup_path, filepath)
            logger.info("已回滚: %s ← %s", filepath, backup_path)
        except Exception as e:
            logger.warning("回滚失败: %s", e)

    def _test_changes(self, filepath: Path) -> bool:
        """测试修改后的代码。"""
        try:
            # 先做语法检查
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            try:
                compile(source, filepath, "exec")
                logger.info("✅ 语法检查通过")
            except SyntaxError as e:
                logger.warning("❌ 语法错误: %s", e)
                return False

            # 运行相关测试（如果存在）
            test_file = self.project_root / "tests" / f"test_{filepath.stem}.py"
            if test_file.exists():
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
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
            else:
                logger.info("⚠️ 无相关测试文件，跳过测试")
                return True  # 没有测试文件，默认通过

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
            status = "✅ 成功" if success else "❌ 失败（已回滚）"

            try:
                rel_path = filepath.relative_to(self.project_root)
            except ValueError:
                rel_path = filepath

            entry = f"""
## {timestamp} - 代码自动进化 {status}

**文件**: {rel_path}
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
