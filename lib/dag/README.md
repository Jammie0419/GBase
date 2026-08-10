# 🧬 DAG Workflow (DAG 工作流)

> DAG 编排 + 状态机驱动

## 功能定位

DAG (Directed Acyclic Graph) 工作流系统提供确定性的任务编排能力，支持 YAML/JSON 定义工作流，状态机驱动执行。

## 包含文件

| 文件 | 功能 | 行数 |
|------|------|:---:|
| `engine.py` | DAG 确定性编排引擎：YAML/JSON 定义工作流，状态机驱动执行 | 744 |
| `agents.py` | DAG Agent 函数库：将 cron 脚本注册为 DAG 引擎可调用的类型化函数 | 556 |
| `orchestrator.py` | DAG-first 任务路由：已知工作流走 DAG，未知走 LLM fallback | 465 |

## API 接口

```python
from lib.dag.engine import DAGEngine

# 从 YAML 加载工作流
dag = DAGEngine.from_yaml("workflows/my_task.yaml")

# 执行
result = await dag.execute()
```

```python
from lib.dag.orchestrator import DAGOrchestrator

orchestrator = DAGOrchestrator()

# 智能路由：已知工作流走 DAG，未知走 LLM
result = await orchestrator.route(task_description)
```

```python
from lib.dag.agents import register_agent_function

# 注册自定义 Agent 函数
@register_agent_function("analyze_code")
async def analyze_code(file_path: str) -> dict:
    # 分析代码
    return {"issues": [...]}
```

## 与其他功能域的交互

- 被 `kernel` 调用：复杂任务的工作流编排
- 调用 `scheduler`: 定时任务触发
- 调用 `tools`: 执行具体的工具函数
- 与 `experience` 集成：工作流执行经验记录

## 特点

- **确定性执行**：状态机驱动，可预测
- **灵活定义**：支持 YAML/JSON 描述工作流
- **智能路由**：DAG-first + LLM fallback
- **函数注册**：将任意函数注册为 DAG 节点
