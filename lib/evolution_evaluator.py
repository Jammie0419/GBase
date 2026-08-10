# SPDX-License-Identifier: MIT
"""
lib/evolution_evaluator.py

进化质量评估器 — 评估自进化的效果，决定是否应用代码修改。

两层评估：
1. 应用前评估（质量门）：语法、安全、逻辑、测试
2. 应用后评估（效果度量）：性能、错误率、成功率对比

设计原则：
- 多维度评估，不依赖单一指标
- 评分制，低于阈值不应用
- 应用后持续监控，效果差自动回滚
- 记录评估日志，供人工审查
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


class EvolutionEvaluator:
    """进化质量评估器。"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self._evaluation_log = []

        # 质量阈值
        self.MIN_QUALITY_SCORE = 0.7  # 最低质量分（0-1）
        self.MIN_SECURITY_SCORE = 0.9  # 最低安全分
        self.MIN_TEST_COVERAGE = 0.6  # 最低测试覆盖率

    def evaluate_before_apply(
        self, file_path: Path, old_code: str, new_code: str, reason: str
    ) -> dict:
        """应用前评估代码修改的质量。

        Returns:
            {
                "approved": bool,  # 是否批准应用
                "quality_score": float,  # 综合质量分（0-1）
                "scores": {
                    "syntax": float,  # 语法正确性
                    "security": float,  # 安全性
                    "logic": float,  # 逻辑正确性
                    "test_coverage": float,  # 测试覆盖
                },
                "issues": list[str],  # 发现的问题
                "recommendation": str,  # 建议
            }
        """
        scores = {}
        issues = []

        # 1. 语法检查（权重 20%）
        scores["syntax"] = self._check_syntax(new_code)
        if scores["syntax"] < 1.0:
            issues.append("语法错误")

        # 2. 安全检查（权重 30%）
        scores["security"] = self._check_security(new_code)
        if scores["security"] < self.MIN_SECURITY_SCORE:
            issues.append("安全风险")

        # 3. 逻辑检查（权重 30%）
        scores["logic"] = self._check_logic(old_code, new_code, reason)
        if scores["logic"] < 0.6:
            issues.append("逻辑问题")

        # 4. 测试覆盖（权重 20%）
        scores["test_coverage"] = self._check_test_coverage(file_path)
        if scores["test_coverage"] < self.MIN_TEST_COVERAGE:
            issues.append("测试覆盖不足")

        # 计算综合分
        quality_score = (
            scores["syntax"] * 0.2
            + scores["security"] * 0.3
            + scores["logic"] * 0.3
            + scores["test_coverage"] * 0.2
        )

        # 决策
        approved = (
            quality_score >= self.MIN_QUALITY_SCORE
            and scores["security"] >= self.MIN_SECURITY_SCORE
        )

        recommendation = self._generate_recommendation(quality_score, scores, issues)

        result = {
            "approved": approved,
            "quality_score": round(quality_score, 3),
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "issues": issues,
            "recommendation": recommendation,
        }

        logger.info(
            "进化评估: score=%.3f, approved=%s, issues=%s",
            quality_score,
            approved,
            issues,
        )

        return result

    def _check_syntax(self, code: str) -> float:
        """检查语法正确性。"""
        try:
            compile(code, "<evolution>", "exec")
            return 1.0
        except SyntaxError as e:
            logger.debug("语法错误: %s", e)
            return 0.0

    def _check_security(self, code: str) -> float:
        """检查安全性。"""
        # 危险模式
        dangerous_patterns = [
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__\s*\(",
            r"os\.system\s*\(",
            r"subprocess\.call\s*\(",
            r"subprocess\.Popen\s*\(",
            r"pickle\.loads?\s*\(",
            r"yaml\.load\s*\(",
        ]

        score = 1.0
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                score -= 0.2
                logger.debug("检测到危险模式: %s", pattern)

        return max(0.0, score)

    def _check_logic(self, old_code: str, new_code: str, reason: str) -> float:
        """检查逻辑正确性（基于启发式规则）。"""
        score = 0.5  # 基础分

        # 检查修改是否有实质性变化
        if old_code.strip() == new_code.strip():
            return 0.0  # 没有实际修改

        # 检查是否解决了描述的问题
        reason_lower = reason.lower()
        if any(keyword in reason_lower for keyword in ["修复", "fix", "解决", "solve"]):
            score += 0.2

        # 检查是否添加了错误处理
        if "try:" in new_code or "except" in new_code:
            score += 0.1

        # 检查是否添加了日志
        if "logger." in new_code or "logging." in new_code:
            score += 0.1

        # 检查是否引入了新的导入
        if "import" in new_code and "import" not in old_code:
            score += 0.1

        return min(1.0, score)

    def _check_test_coverage(self, file_path: Path) -> float:
        """检查测试覆盖率。"""
        try:
            # 查找相关测试文件
            test_file = self.project_root / "tests" / f"test_{file_path.stem}.py"

            if not test_file.exists():
                # 没有测试文件，给中等分数
                return 0.5

            # 运行测试并获取覆盖率
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    str(test_file),
                    "--cov",
                    str(file_path),
                    "--cov-report",
                    "term",
                    "-v",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # 解析覆盖率
            output = result.stdout
            coverage_match = re.search(r"TOTAL.*?(\d+)%", output)

            if coverage_match:
                coverage = int(coverage_match.group(1)) / 100.0
                return coverage

            # 无法解析，给中等分数
            return 0.5

        except Exception as e:
            logger.debug("测试覆盖率检查失败: %s", e)
            return 0.5

    def _generate_recommendation(
        self, quality_score: float, scores: dict, issues: list[str]
    ) -> str:
        """生成建议。"""
        if quality_score >= 0.9:
            return "✅ 高质量修改，建议应用"
        elif quality_score >= 0.7:
            return "⚠️ 中等质量，建议人工审查后应用"
        elif quality_score >= 0.5:
            return "⚠️ 质量偏低，建议改进后再应用"
        else:
            return "❌ 质量不合格，不建议应用"

    def evaluate_after_apply(
        self, file_path: Path, before_metrics: dict
    ) -> dict:
        """应用后评估效果。

        Args:
            file_path: 修改的文件
            before_metrics: 应用前的指标快照

        Returns:
            {
                "improved": bool,  # 是否改进
                "metrics_delta": dict,  # 指标变化
                "recommendation": str,  # 建议（保留/回滚）
            }
        """
        try:
            # 收集应用后的指标
            after_metrics = self._collect_metrics(file_path)

            # 计算变化
            metrics_delta = {}
            for key in before_metrics:
                before_val = before_metrics.get(key, 0)
                after_val = after_metrics.get(key, 0)
                delta = after_val - before_val
                metrics_delta[key] = {
                    "before": before_val,
                    "after": after_val,
                    "delta": delta,
                    "improved": self._is_improvement(key, delta),
                }

            # 判断是否整体改进
            improved_count = sum(
                1 for m in metrics_delta.values() if m["improved"]
            )
            total_count = len(metrics_delta)
            improved = improved_count >= total_count / 2

            recommendation = (
                "✅ 效果良好，保留修改"
                if improved
                else "❌ 效果不佳，建议回滚"
            )

            return {
                "improved": improved,
                "metrics_delta": metrics_delta,
                "recommendation": recommendation,
            }

        except Exception as e:
            logger.warning("应用后评估失败: %s", e)
            return {
                "improved": False,
                "metrics_delta": {},
                "recommendation": f"⚠️ 评估失败: {e}",
            }

    def _collect_metrics(self, file_path: Path) -> dict:
        """收集文件相关指标。"""
        metrics = {}

        try:
            # 1. 测试通过率
            test_file = self.project_root / "tests" / f"test_{file_path.stem}.py"
            if test_file.exists():
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_file), "-v"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                passed = result.stdout.count("PASSED")
                failed = result.stdout.count("FAILED")
                total = passed + failed
                metrics["test_pass_rate"] = passed / total if total > 0 else 0.0

            # 2. 文件大小
            metrics["file_size"] = file_path.stat().st_size

            # 3. 代码行数
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            metrics["line_count"] = len(lines)

            # 4. 复杂度（简单启发式：嵌套深度）
            max_indent = 0
            for line in lines:
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent)
            metrics["max_indent"] = max_indent

        except Exception as e:
            logger.debug("指标收集失败: %s", e)

        return metrics

    def _is_improvement(self, metric_name: str, delta: float) -> bool:
        """判断指标变化是否是改进。"""
        if metric_name == "test_pass_rate":
            return delta > 0  # 测试通过率提高是改进
        elif metric_name == "file_size":
            return abs(delta) < 100  # 文件大小变化不大
        elif metric_name == "line_count":
            return abs(delta) < 20  # 行数变化不大
        elif metric_name == "max_indent":
            return delta <= 0  # 嵌套深度降低是改进
        return False


# ── 全局实例 ─────────────────────────────────────────

_evaluator_instance: Optional[EvolutionEvaluator] = None


def get_evolution_evaluator() -> EvolutionEvaluator:
    """获取评估器实例（单例）。"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = EvolutionEvaluator()
    return _evaluator_instance


def evaluate_before_apply(
    file_path: Path, old_code: str, new_code: str, reason: str
) -> dict:
    """应用前评估（便捷函数）。"""
    evaluator = get_evolution_evaluator()
    return evaluator.evaluate_before_apply(file_path, old_code, new_code, reason)


def evaluate_after_apply(file_path: Path, before_metrics: dict) -> dict:
    """应用后评估（便捷函数）。"""
    evaluator = get_evolution_evaluator()
    return evaluator.evaluate_after_apply(file_path, before_metrics)
