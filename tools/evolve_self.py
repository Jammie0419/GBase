# SPDX-License-Identifier: MIT
"""
tools/evolve_self.py

自进化工具 — 由用户触发，分析轨迹并进化自身代码。

设计原则：
- 不自动执行，需要用户明确调用
- 基于轨迹（traces）分析问题模式
- 判断是否需要进化
- LLM 生成改进方案
- 质量评估后才应用
- 效果好才保留

用法：
  evolve_self()  # 分析轨迹并尝试进化
  evolve_self(target="lib/safe_shell.py")  # 针对特定文件进化
  evolve_self(dry_run=True)  # 只分析不应用
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

from lib.compat import GBASE_BACKUP_DIR, GBASE_EVOLUTION_DIR

from lib.toolkit import tool

logger = logging.getLogger(__name__)


@tool()
async def evolve_self(
    target: str = "",
    dry_run: bool = False,
    max_changes: int = 3,
) -> dict:
    """分析轨迹并进化自身代码（用户触发）。

    Args:
        target: 可选，针对特定文件进化（如 "lib/safe_shell.py"）
        dry_run: 如果为 True，只分析不应用修改
        max_changes: 最多应用多少个修改（默认 3）

    Returns:
        {
            "success": bool,
            "analysis": {...},  # 轨迹分析结果
            "evolution_plan": [...],  # 进化计划
            "applied_changes": [...],  # 已应用的修改
            "evaluation": {...},  # 质量评估结果
        }
    """
    project_root = Path(__file__).resolve().parent.parent

    logger.info("🧬 开始自进化分析...")

    try:
        # 1. 分析轨迹，发现问题模式
        analysis = await analyze_traces(project_root, target)

        if not analysis["needs_evolution"]:
            return {
                "success": True,
                "analysis": analysis,
                "evolution_plan": [],
                "applied_changes": [],
                "message": "✅ 轨迹分析完成，未发现需要进化的问题",
            }

        logger.info("✅ 发现 %d 个改进机会", len(analysis["issues"]))

        # 2. 用 LLM 生成进化方案
        evolution_plan = await generate_evolution_plan(
            analysis, project_root, target
        )

        if not evolution_plan:
            return {
                "success": True,
                "analysis": analysis,
                "evolution_plan": [],
                "applied_changes": [],
                "message": "⚠️ LLM 未能生成有效的进化方案",
            }

        logger.info("✅ 生成了 %d 个进化方案", len(evolution_plan))

        # 3. 如果是 dry_run，只返回计划不应用
        if dry_run:
            return {
                "success": True,
                "analysis": analysis,
                "evolution_plan": evolution_plan,
                "applied_changes": [],
                "message": f"📋 Dry run 模式，生成了 {len(evolution_plan)} 个进化方案（未应用）",
            }

        # 4. 应用修改（带质量评估）
        applied_changes = await apply_evolution_plan(
            evolution_plan, project_root, max_changes
        )

        if not applied_changes:
            return {
                "success": False,
                "analysis": analysis,
                "evolution_plan": evolution_plan,
                "applied_changes": [],
                "message": "❌ 没有修改通过质量评估",
            }

        return {
            "success": True,
            "analysis": analysis,
            "evolution_plan": evolution_plan,
            "applied_changes": applied_changes,
            "message": f"✅ 成功应用 {len(applied_changes)} 个修改",
        }

    except Exception as e:
        logger.exception("自进化失败: %s", e)
        return {
            "success": False,
            "error": str(e),
            "analysis": {},
            "evolution_plan": [],
            "applied_changes": [],
        }


async def analyze_traces(project_root: Path, target: str = "") -> dict:
    """分析轨迹数据，发现问题模式。

    Returns:
        {
            "needs_evolution": bool,  # 是否需要进化
            "issues": [...],  # 发现的问题
            "patterns": {...},  # 问题模式统计
            "trace_count": int,  # 分析的轨迹数量
        }
    """
    trace_dir = project_root / "data" / "traces"

    if not trace_dir.exists():
        return {
            "needs_evolution": False,
            "issues": [],
            "patterns": {},
            "trace_count": 0,
        }

    # 读取最近的轨迹文件
    trace_files = sorted(trace_dir.glob("*.jsonl"), reverse=True)[:20]

    issues = []
    patterns = {
        "tool_failures": {},
        "error_messages": {},
        "slow_tools": {},
    }

    for trace_file in trace_files:
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)

                    # 分析工具调用失败
                    if entry.get("_type") == "tool_call":
                        tool_name = entry.get("tool_name", "")
                        status = entry.get("status", "")

                        if target and target not in tool_name:
                            continue

                        if status == "error":
                            error_msg = entry.get("error", "")[:100]
                            patterns["tool_failures"][tool_name] = (
                                patterns["tool_failures"].get(tool_name, 0) + 1
                            )
                            patterns["error_messages"][error_msg] = (
                                patterns["error_messages"].get(error_msg, 0) + 1
                            )

                        # 分析慢工具
                        duration = entry.get("duration_ms", 0)
                        if duration > 5000:
                            patterns["slow_tools"][tool_name] = (
                                patterns["slow_tools"].get(tool_name, 0) + 1
                            )

        except Exception as e:
            logger.debug("分析轨迹失败 %s: %s", trace_file, e)
            continue

    # 判断是否需要进化
    total_failures = sum(patterns["tool_failures"].values())
    needs_evolution = total_failures >= 3 or len(patterns["slow_tools"]) >= 2

    # 生成问题列表
    for tool_name, count in sorted(
        patterns["tool_failures"].items(), key=lambda x: x[1], reverse=True
    )[:5]:
        issues.append(
            {
                "type": "tool_failure",
                "tool": tool_name,
                "count": count,
                "severity": "high" if count >= 3 else "medium",
            }
        )

    for tool_name, count in sorted(
        patterns["slow_tools"].items(), key=lambda x: x[1], reverse=True
    )[:3]:
        issues.append(
            {
                "type": "slow_execution",
                "tool": tool_name,
                "count": count,
                "severity": "medium",
            }
        )

    return {
        "needs_evolution": needs_evolution,
        "issues": issues,
        "patterns": patterns,
        "trace_count": len(trace_files),
    }


async def generate_evolution_plan(
    analysis: dict, project_root: Path, target: str = ""
) -> list[dict]:
    """用 LLM 生成进化方案。

    Returns:
        [
            {
                "file": "lib/safe_shell.py",
                "old_code": "...",
                "new_code": "...",
                "reason": "...",
                "expected_improvement": "..."
            }
        ]
    """
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com/v1",
        )

        # 构建提示词
        prompt = build_evolution_prompt(analysis, project_root, target)

        # 调用 LLM
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是 GBase 自进化系统。根据轨迹分析结果生成代码改进方案。返回 JSON 格式。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
            ),
            timeout=60,
        )

        content = response.choices[0].message.content.strip()

        # 提取 JSON
        plan = extract_json_from_response(content)

        if plan and isinstance(plan, list):
            return plan
        else:
            return []

    except Exception as e:
        logger.warning("LLM 生成进化方案失败: %s", e)
        return []


def build_evolution_prompt(
    analysis: dict, project_root: Path, target: str
) -> str:
    """构建 LLM 提示词。"""
    issues_text = "\n".join(
        f"- {issue['type']}: {issue.get('tool', '')} (出现 {issue['count']} 次)"
        for issue in analysis["issues"][:10]
    )

    prompt = f"""GBase 自进化系统分析了最近 {analysis['trace_count']} 条轨迹，发现以下问题：

{issues_text}

请分析这些问题，并生成代码改进方案。要求：
1. 只修改 GBase 自身的源代码（lib/*.py, tools/*.py）
2. 针对实际问题生成修复代码
3. 使用精确的代码替换（old_code → new_code）
4. 确保修改后的代码语法正确
5. 返回 JSON 数组格式：

```json
[
  {{
    "file": "lib/example.py",
    "old_code": "要替换的原始代码（必须精确匹配源文件）",
    "new_code": "替换后的新代码",
    "reason": "修改原因",
    "expected_improvement": "预期改进效果"
  }}
]
```

注意：
- old_code 必须与源文件中的代码完全匹配（包括缩进、空格）
- 如果无法确定具体修改，返回空数组 []
- 优先修复高严重度问题
- 每个修改都要有明确的原因和预期效果
"""

    if target:
        prompt += f"\n**重点关注文件**: {target}\n"

    return prompt


def extract_json_from_response(content: str) -> Optional[list[dict]]:
    """从 LLM 响应中提取 JSON。"""
    try:
        # 尝试提取 ```json ... ``` 块
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            json_str = json_match.group(1)
            return json.loads(json_str)

        # 尝试直接解析
        return json.loads(content)

    except Exception:
        return None


async def apply_evolution_plan(
    plan: list[dict], project_root: Path, max_changes: int
) -> list[dict]:
    """应用进化方案（带质量评估）。"""
    from lib.evolution.evaluator import evaluate_before_apply, evaluate_after_apply

    applied = []

    for change in plan[:max_changes]:
        try:
            file_path = change.get("file", "")
            old_code = change.get("old_code", "")
            new_code = change.get("new_code", "")
            reason = change.get("reason", "")

            if not file_path or not old_code or not new_code:
                continue

            full_path = project_root / file_path

            if not full_path.exists():
                logger.warning("文件不存在: %s", file_path)
                continue

            # 应用前评估
            eval_result = evaluate_before_apply(full_path, old_code, new_code, reason)

            if not eval_result["approved"]:
                logger.warning(
                    "❌ 质量评估不通过: %s (score=%.3f)",
                    eval_result["issues"],
                    eval_result["quality_score"],
                )
                continue

            # 收集应用前指标
            before_metrics = {
                "file_size": full_path.stat().st_size,
            }

            # 备份
            backup_path = backup_file(full_path, project_root)
            if not backup_path:
                continue

            # 读取并修改
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_code not in content:
                logger.warning("旧代码不存在: %s", file_path)
                continue

            new_content = content.replace(old_code, new_code, 1)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 测试
            test_passed = test_changes(full_path, project_root)

            if test_passed:
                # 应用后评估
                after_eval = evaluate_after_apply(full_path, before_metrics)

                if after_eval["improved"]:
                    logger.info("✅ 修改成功: %s", file_path)
                    applied.append(
                        {
                            "file": file_path,
                            "reason": reason,
                            "quality_score": eval_result["quality_score"],
                            "evaluation": after_eval["recommendation"],
                        }
                    )
                    log_evolution(full_path, reason, True, project_root)
                else:
                    logger.warning("❌ 效果不佳，回滚: %s", file_path)
                    rollback_file(full_path, backup_path)
                    log_evolution(full_path, reason, False, project_root)
            else:
                logger.warning("❌ 测试失败，回滚: %s", file_path)
                rollback_file(full_path, backup_path)
                log_evolution(full_path, reason, False, project_root)

        except Exception as e:
            logger.warning("应用修改失败: %s", e)
            continue

    return applied


def backup_file(file_path: Path, project_root: Path) -> Optional[Path]:
    """备份文件。"""
    try:
        backup_dir = GBASE_BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = backup_dir / backup_name

        import shutil
        shutil.copy2(file_path, backup_path)

        return backup_path

    except Exception as e:
        logger.warning("备份失败: %s", e)
        return None


def rollback_file(file_path: Path, backup_path: Path):
    """回滚文件。"""
    try:
        import shutil
        shutil.copy2(backup_path, file_path)
    except Exception as e:
        logger.warning("回滚失败: %s", e)


def test_changes(file_path: Path, project_root: Path) -> bool:
    """测试修改。"""
    try:
        # 语法检查
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        compile(source, file_path, "exec")

        # 运行相关测试
        test_file = project_root / "tests" / f"test_{file_path.stem}.py"
        if test_file.exists():
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_file), "-v"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0

        return True  # 没有测试文件，默认通过

    except Exception as e:
        logger.warning("测试失败: %s", e)
        return False


def log_evolution(
    file_path: Path, reason: str, success: bool, project_root: Path
):
    """记录进化日志。"""
    try:
        log_file = GBASE_EVOLUTION_DIR / "evolution-log.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                existing = f.read()

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status = "✅ 成功" if success else "❌ 失败（已回滚）"

        try:
            rel_path = file_path.relative_to(project_root)
        except ValueError:
            rel_path = file_path

        entry = f"""
## {timestamp} - 自进化 {status}

**文件**: {rel_path}
**原因**: {reason}

---
"""

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(existing + entry)

    except Exception as e:
        logger.warning("写入进化日志失败: %s", e)
