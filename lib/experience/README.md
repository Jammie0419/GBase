# 📚 Experience Engine (经验引擎)

> 反脆弱元认知 + 行为复盘

## 功能定位

Experience Engine 是 GBase 的学习核心：从每次对话中自动提取经验，通过反脆弱元认知规则不断改进，并通过行为复盘分析决策链。

## 包含文件

| 文件 | 功能 | 行数 |
|------|------|:---:|
| `engine.py` | 经验引擎：反脆弱元认知 + 去重 + 队列式批量提取 | 738 |
| `trace_review.py` | 行为复盘分析器：决策链复盘 + 模式提取 + 行动建议 | 520 |

## API 接口

```python
from lib.experience.engine import ExperienceEngine

engine = ExperienceEngine(storage)

# 从对话中提取经验
await engine.extract(
    user_message="帮我修复这个 bug",
    reply="已修复...",
    tool_calls_count=5,
    has_failure=True,
    failure_reason="API 超时"
)

# 批量提取（cron 调用）
await engine.flush()
```

```python
from lib.experience.trace_review import review

# 行为复盘
analysis = await review(trace_data)
# 返回: 决策链分析、模式提取、行动建议
```

## 核心机制

### 反脆弱规则

```python
_ANTI_FRAGILE_RULES = [
    {"name": "tool_excessive", ...},      # 工具调用过多
    {"name": "api_error", ...},           # API 错误
    {"name": "failed_action", ...},       # 失败尝试
    {"name": "failed_rollback", ...},     # 回滚失败
    {"name": "knowledge_miss", ...},      # 知识检索失败
    {"name": "success_pattern", ...},     # 成功模式提炼
]
```

### 元认知反思

```python
_META_REFLECTION_PROMPT = """
Situation → Action → Outcome → Lesson 四段式分析
"""
```

## 与其他功能域的交互

- 被 `kernel` 调用：每次对话后提取经验
- 调用 `storage`: 读写经验数据
- 调用 `skills.crafter`: 从经验生成新技能
- 调用 `tracer`: 获取调用链数据进行复盘
- 被 `evolution` 调用：进化前的经验分析

## 特点

- **自动提取**：每次对话后自动提取经验
- **反脆弱**：失败和成功都学习，不静默回滚
- **去重机制**：同一规则在窗口内不重复记录
- **队列式批处理**：extract() 入队 + flush() 批量提取
- **行为复盘**：决策链分析 + 模式提取 + 行动建议
