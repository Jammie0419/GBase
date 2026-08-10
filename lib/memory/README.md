# 🧠 Mirror Memory (鉴面记忆)

> 三层记忆 + 主动回忆 + 遗忘衰减

## 功能定位

Mirror Memory 是 GBase 的长期记忆系统：模拟人类记忆的三层结构（热记忆/温记忆/自动记忆），支持主动回忆、遗忘衰减、正强化。

## 包含文件

| 文件 | 功能 | 行数 |
|------|------|:---:|
| `mirror.py` | 鉴面引擎：三层记忆（hot/warm/auto）+ 遗忘衰减 + 正强化 | 1626 |
| `cognifold.py` | 认知折叠：三层认知结构（海马体→新皮层→前额叶）+ 概念簇自组织 | 619 |
| `archive_store.py` | 归档存储：全文写入 SQLite + BM25 排序搜索 | 1034 |

## API 接口

```python
from lib.memory.mirror import MirrorEngine

mirror = MirrorEngine()

# 写入记忆
await mirror.remember(
    content="用户喜欢简洁的代码风格",
    category="preference",
    importance=0.8
)

# 主动回忆
memories = await mirror.recall("代码风格", limit=5)

# 遗忘衰减（自动）
await mirror.decay()

# 正强化
await mirror.reinforce(memory_id)
```

```python
from lib.memory.cognifold import Cognifold

cognifold = Cognifold()

# 认知折叠：将复杂信息压缩为概念簇
concepts = await cognifold.fold(complex_data)

# 概念自组织
organized = await cognifold.organize(concepts)
```

```python
from lib.memory.archive_store import ArchiveStore

store = ArchiveStore()

# 归档会话
await store.archive(session_data)

# BM25 搜索
results = await store.search("关键词", limit=10)
```

## 三层记忆架构

| 层级 | 特点 | 持久性 | 访问速度 |
|------|------|:---:|:---:|
| **Hot (热记忆)** | 当前对话上下文 | 低 | 极快 |
| **Warm (温记忆)** | 近期重要信息 | 中 | 快 |
| **Auto (自动记忆)** | 长期沉淀的知识 | 高 | 慢 |

## 与其他功能域的交互

- 被 `kernel` 调用：对话时读写记忆
- 调用 `storage`: 持久化存储
- 被 `experience` 调用：经验注入记忆
- 被 `tools/mirror_tool.py` 调用：工具层记忆操作
- 被 `dag/agents.py` 调用：DAG 工作流记忆访问

## 特点

- **三层记忆**：模拟人类记忆的 hot/warm/auto 结构
- **遗忘衰减**：不重要的记忆自动衰减
- **正强化**：被访问的记忆增强
- **主动回忆**：基于语义相似度检索
- **认知折叠**：复杂信息压缩为概念簇
- **BM25 搜索**：全文检索支持
- **自动审查**：定期整理和清理记忆
