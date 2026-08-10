# SPDX-License-Identifier: MIT
"""
lib/skill_crafter.py

技能工匠 — 从经验中自动创建新技能。

这是自进化闭环的关键一环：
  经验提取 → 识别能力缺口 → 生成技能 → 注册到 skill_loader → 可用

当前实现：
- 监控经验库中的重复模式
- 当同一类问题出现 3+ 次时，自动生成解决方案技能
- 创建 skills/<name>/SKILL.md 文件
- 技能包含：触发词、使用说明、解决方案模板
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"


# ── 能力缺口模式库 ─────────────────────────────────────

_GAP_PATTERNS = [
    {
        "rule": "knowledge_miss",
        "threshold": 3,  # 出现 3 次就触发
        "skill_name": "auto-knowledge-importer",
        "skill_title": "自动知识导入",
        "description": "当知识库检索失败时，自动识别并导入相关项目文档",
        "triggers": ["知识库", "检索失败", "knowledge_miss", "无命中"],
        "solution_template": """# 自动知识导入技能

## 触发条件
当检测到知识检索失败（knowledge_miss）且工具调用次数较多时触发。

## 解决方案
1. 识别用户问题中的关键词
2. 扫描项目文档（rules/*.md, lib/*.py）
3. 将相关文档导入知识库
4. 重新检索并回答

## 执行步骤
```python
from scripts.seed_knowledge import main as seed_knowledge
seed_knowledge()
```

## 预期效果
知识库自动填充，后续同类问题可直接检索命中。
""",
    },
    {
        "rule": "tool_excessive",
        "threshold": 5,
        "skill_name": "task-planner",
        "skill_title": "任务规划器",
        "description": "在工具调用过多时，提供任务分解和规划能力",
        "triggers": ["工具调用", "次数偏多", "tool_excessive", "先规划"],
        "solution_template": """# 任务规划器技能

## 触发条件
当工具调用次数超过 5 次时触发。

## 解决方案
在执行工具前，先进行任务分解：
1. 明确目标
2. 拆解为子任务
3. 为每个子任务选择最优工具
4. 按顺序执行，避免重复

## 规划模板
```
目标: [用户想要什么]
子任务:
  1. [步骤1] → 工具: [tool_name]
  2. [步骤2] → 工具: [tool_name]
  ...
```

## 预期效果
减少工具调用次数，提高效率。
""",
    },
]


class SkillCrafter:
    """技能工匠 — 从经验中自动创建技能。"""

    def __init__(self, storage):
        """初始化技能工匠。

        Args:
            storage: Storage 实例，用于读取经验
        """
        self.storage = storage
        self._created_skills = set()  # 跟踪已创建的技能，避免重复

    def analyze_and_craft(self) -> list[str]:
        """分析经验并创建技能。

        Returns:
            新创建的技能名称列表
        """
        created = []

        try:
            # 读取最近 50 条经验
            experiences = self.storage.read_recent("experience", limit=50)
            if not experiences:
                logger.debug("无经验可分析")
                return created

            # 统计每条规则出现的次数
            rule_counts = {}
            for exp in experiences:
                rule = exp.get("rule", "")
                if rule:
                    rule_counts[rule] = rule_counts.get(rule, 0) + 1

            logger.info("经验规则统计: %s", rule_counts)

            # 检查是否达到阈值
            for pattern in _GAP_PATTERNS:
                rule = pattern["rule"]
                threshold = pattern["threshold"]
                count = rule_counts.get(rule, 0)

                if count >= threshold:
                    skill_name = pattern["skill_name"]

                    # 避免重复创建
                    if skill_name in self._created_skills:
                        logger.debug("技能 %s 已创建过，跳过", skill_name)
                        continue

                    # 检查技能文件是否已存在
                    skill_dir = SKILLS_DIR / skill_name
                    if skill_dir.exists():
                        logger.info("技能目录 %s 已存在，标记为已创建", skill_name)
                        self._created_skills.add(skill_name)
                        continue

                    # 创建技能
                    if self._create_skill(pattern):
                        created.append(skill_name)
                        self._created_skills.add(skill_name)
                        logger.info("✅ 自动创建技能: %s (触发: %s 出现 %d 次)", skill_name, rule, count)

        except Exception as e:
            logger.warning("技能工匠分析失败: %s", e)

        return created

    def _create_skill(self, pattern: dict) -> bool:
        """创建单个技能。

        Args:
            pattern: 技能模式定义

        Returns:
            是否创建成功
        """
        try:
            skill_name = pattern["skill_name"]
            skill_dir = SKILLS_DIR / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            # 生成 SKILL.md
            skill_content = f"""---
name: {pattern["skill_title"]}
description: {pattern["description"]}
triggers:
{chr(10).join(f'  - {t}' for t in pattern["triggers"])}
auto_generated: true
created_by: skill_crafter
---

{pattern["solution_template"]}
"""

            skill_file = skill_dir / "SKILL.md"
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(skill_content)

            logger.info("技能文件已创建: %s", skill_file)

            # 记录到进化日志
            self._log_evolution(pattern)

            return True

        except Exception as e:
            logger.warning("创建技能失败: %s", e)
            return False

    def _log_evolution(self, pattern: dict):
        """记录进化动作到日志。"""
        try:
            log_file = Path(__file__).parent.parent / "evolution-log.md"

            # 读取现有内容（如果存在）
            existing = ""
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    existing = f.read()

            # 追加新记录
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"""
## {timestamp} - 自动创建技能: {pattern["skill_name"]}

**触发规则**: {pattern["rule"]}
**技能名称**: {pattern["skill_title"]}
**描述**: {pattern["description"]}

**进化原因**: 经验库中 {pattern["rule"]} 规则多次触发，表明存在能力缺口。

---
"""

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(existing + entry)

            logger.info("进化日志已更新: %s", log_file)

        except Exception as e:
            logger.warning("写入进化日志失败: %s", e)

    def analyze_skill_usage(self) -> dict:
        """分析技能使用数据，返回使用统计和改进建议。

        Returns:
            {
                "skill_stats": {"skill_name": {"count": N, "avg_score": X.X}},
                "unused_skills": ["skill1", "skill2"],
                "low_performing_skills": ["skill3"],
                "recommendations": ["建议1", "建议2"]
            }
        """
        try:
            usage_file = Path(__file__).parent.parent / "data" / "skill_usage.jsonl"
            if not usage_file.exists():
                return {"skill_stats": {}, "unused_skills": [], "low_performing_skills": [], "recommendations": []}

            # 读取使用记录
            skill_stats = {}
            with open(usage_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        for skill in entry.get("matched_skills", []):
                            name = skill.get("name", "")
                            score = skill.get("score", 0)
                            if name:
                                if name not in skill_stats:
                                    skill_stats[name] = {"count": 0, "total_score": 0, "scores": []}
                                skill_stats[name]["count"] += 1
                                skill_stats[name]["total_score"] += score
                                skill_stats[name]["scores"].append(score)
                    except Exception:
                        continue

            # 计算平均分数
            for name, stats in skill_stats.items():
                if stats["count"] > 0:
                    stats["avg_score"] = stats["total_score"] / stats["count"]
                else:
                    stats["avg_score"] = 0

            # 获取所有已创建的技能
            all_skills = set()
            if SKILLS_DIR.exists():
                for skill_dir in SKILLS_DIR.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        all_skills.add(skill_dir.name)

            # 识别未使用的技能
            used_skills = set(skill_stats.keys())
            unused_skills = list(all_skills - used_skills)

            # 识别低表现技能（平均分数 < 0.3 或 使用次数 < 2）
            low_performing = [
                name
                for name, stats in skill_stats.items()
                if stats["avg_score"] < 0.3 or stats["count"] < 2
            ]

            # 生成建议
            recommendations = []
            if unused_skills:
                recommendations.append(f"考虑删除或改进未使用的技能: {', '.join(unused_skills[:3])}")
            if low_performing:
                recommendations.append(f"低表现技能需要优化: {', '.join(low_performing[:3])}")

            return {
                "skill_stats": skill_stats,
                "unused_skills": unused_skills,
                "low_performing_skills": low_performing,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.warning("技能使用分析失败: %s", e)
            return {"skill_stats": {}, "unused_skills": [], "low_performing_skills": [], "recommendations": []}

    def evolve_skill(self, skill_name: str, improvements: str) -> bool:
        """进化现有技能（追加改进内容到 SKILL.md）。

        Args:
            skill_name: 技能名称
            improvements: 改进内容（会追加到技能文件末尾）

        Returns:
            是否进化成功
        """
        try:
            skill_dir = SKILLS_DIR / skill_name
            skill_file = skill_dir / "SKILL.md"

            if not skill_file.exists():
                logger.warning("技能不存在: %s", skill_name)
                return False

            # 读取现有内容
            with open(skill_file, "r", encoding="utf-8") as f:
                existing_content = f.read()

            # 追加改进内容
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            evolution_section = f"""

---

## 🔄 进化记录 ({timestamp})

{improvements}
"""

            with open(skill_file, "a", encoding="utf-8") as f:
                f.write(evolution_section)

            logger.info("✅ 技能已进化: %s", skill_name)

            # 记录到进化日志
            self._log_skill_evolution(skill_name, improvements)

            return True

        except Exception as e:
            logger.warning("技能进化失败: %s", e)
            return False

    def _log_skill_evolution(self, skill_name: str, improvements: str):
        """记录技能进化到日志。"""
        try:
            log_file = Path(__file__).parent.parent / "evolution-log.md"

            existing = ""
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    existing = f.read()

            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"""
## {timestamp} - 技能进化: {skill_name}

**改进内容**:
{improvements}

---
"""

            with open(log_file, "w", encoding="utf-8") as f:
                f.write(existing + entry)

        except Exception as e:
            logger.warning("写入技能进化日志失败: %s", e)


# ── 全局实例 ─────────────────────────────────────────

_crafter_instance: Optional[SkillCrafter] = None


def get_skill_crafter(storage=None) -> SkillCrafter:
    """获取技能工匠实例（单例）。"""
    global _crafter_instance
    if _crafter_instance is None:
        if storage is None:
            from lib.storage import Storage
            storage = Storage()
            storage.setup()
        _crafter_instance = SkillCrafter(storage)
    return _crafter_instance


def analyze_experiences_and_craft_skills(storage=None) -> list[str]:
    """分析经验并创建技能（供外部调用）。

    Returns:
        新创建的技能名称列表
    """
    crafter = get_skill_crafter(storage)
    return crafter.analyze_and_craft()
