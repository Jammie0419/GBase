# 📖 Auto-Learn System (自主学习)

> RSS + 搜索定时学习

## 功能定位

Auto-Learn 系统定期从 RSS 源和网络搜索获取信息，自动学习和沉淀到知识库。

## 包含文件

| 文件 | 功能 | 行数 |
|------|------|:---:|
| `engine.py` | 自主学习引擎：定时触发 RSS 抓取 + 搜索学习 | 438 |
| `rss_fetcher.py` | RSS 抓取器：纯标准库实现的 RSS 源抓取 + 解析 | 393 |

## API 接口

```python
from lib.auto_learn.engine import AutoLearnEngine

engine = AutoLearnEngine()

# 手动触发学习
await engine.learn_from_rss()
await engine.learn_from_search(query="Python best practices")

# 配置定时学习
engine.schedule_learning(interval_hours=24)
```

## 与其他功能域的交互

- 调用 `fetcher` (lib/): 通用 HTTP 抓取
- 写入 `storage`: 学习结果存入知识库
- 被 `scheduler` 调用：定时触发学习

## 特点

- 纯标准库实现 RSS 解析，无外部依赖
- 支持去重和过滤
- 学习结果自动写入 knowledge 表
