# 🔄 Recursive Self-Improvement (RSI) - 递归自进化

> 检测→反思→评估→进化→验证

## 功能定位

RSI 是 GBase 的核心创新能力：自动检测问题、反思原因、评估方案、进化代码、验证效果，形成完整的自进化闭环。

## 包含文件

| 文件 | 功能 | 行数 | 来源 |
|------|------|:---:|:---:|
| `engine.py` | 进化引擎：稳定性/性能/安全评估 + 自动回滚 | 517 | v0.7.0 |
| `evaluator.py` | 进化质量评估器：多维度质量门控 | 369 | 新增 |
| `code_evolver.py` | 代码进化器：LLM 生成代码修改自身源码 | 400 | 新增 |
| `refraction.py` | 步骤级反思引擎：每次工具调用后即时评估 | 296 | 新增 |
| `self_improving.py` | 自我改进引擎：新信息吸收后分析能力影响 | 215 | 新增 |

## 核心流程

```
检测问题 (refraction) 
    ↓
提取经验 (experience)
    ↓
识别缺口 (self_improving)
    ↓
创建技能 (skill_crafter)
    ↓
进化代码 (code_evolver)
    ↓
评估质量 (evaluator)
    ↓
验证效果 (engine)
    ↓
复盘决策 (trace_review)
```

## API 接口

```python
from lib.evolution.engine import EvolutionEngine

engine = EvolutionEngine()

# 完整进化周期
result = await engine.full_evolution_cycle()

# 稳定性评估
stability = await engine.evaluate_stability()

# 性能评估
performance = await engine.evaluate_performance()

# 安全评估
safety = await engine.evaluate_security()
```

```python
from lib.evolution.evaluator import EvolutionEvaluator

evaluator = EvolutionEvaluator()

# 应用前评估
eval_result = evaluator.evaluate_before_apply(
    file_path, old_code, new_code, reason
)

# 应用后评估
after_eval = evaluator.evaluate_after_apply(file_path, before_metrics)
```

```python
from lib.evolution.code_evolver import CodeEvolver

evolver = CodeEvolver()

# 从建议进化代码
success = await evolver.evolve_from_suggestion_async(suggestion)
```

```python
from lib.evolution.refraction import evaluate_tool_call

# 步骤级反思
result = evaluate_tool_call(tool_call, tool_result)
# 立即评估：是否正确？需要换方向吗？
```

```python
from lib.evolution.self_improving import trigger_self_improving

# 新信息吸收后触发自我改进
improvements = trigger_self_improving(entry_type, entry_data)
```

## 与其他功能域的交互

- 调用 `experience`: 获取经验数据
- 调用 `skills`: 创建和使用技能
- 调用 `safety`: 进化前安全检查
- 调用 `storage`: 存储进化日志
- 被 `tools/evolve_self.py` 调用：用户触发的自进化
- 被 `kernel` 调用：refraction 实时反思

## 质量门控

```python
# 评估维度
scores = {
    "syntax": 1.0,          # 语法正确性 (20%)
    "security": 0.9,        # 安全性 (30%)
    "logic": 0.8,           # 逻辑正确性 (30%)
    "test_coverage": 0.7,   # 测试覆盖 (20%)
}

# 阈值
MIN_QUALITY_SCORE = 0.7
MIN_SECURITY_SCORE = 0.9
MIN_TEST_COVERAGE = 0.6
```

## 特点

- **完整闭环**：检测→反思→评估→进化→验证→复盘
- **质量门控**：多维度评估，不达标不应用
- **自动回滚**：效果不佳自动回滚
- **步骤级反思**：每次工具调用后即时评估
- **用户控制**：通过 `evolve_self()` 工具触发，不自动执行
- **LLM 驱动**：用 LLM 生成代码修改方案
