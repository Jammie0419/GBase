# 🌐 Multi-Agent Communication (多 Agent 通信)

> Village OS + 跨 Agent 任务协议

## 功能定位

Multi-Agent 通信系统支持多个 GBase 实例之间的协作、任务分发和结果收集。

## 包含文件

| 文件 | 功能 | 行数 |
|------|------|:---:|
| `village_connector.py` | Village OS 连接器：注册 + 心跳 + WCP 消息收发 | 220 |
| `battle_protocol.py` | Agent 间任务协议：发送任务 + 自动返回结果 | 159 |

## API 接口

```python
from lib.multi_agent.village_connector import VillageConnector

connector = VillageConnector()

# 注册到 Village
await connector.register(agent_id="gbase-01")

# 发送心跳
await connector.heartbeat()

# 发送消息
await connector.send_message(target_agent="gbase-02", message={...})
```

```python
from lib.multi_agent.battle_protocol import BattleProtocol

protocol = BattleProtocol()

# 发送任务给其他 Agent
result = await protocol.send_task(
    target_agent="gbase-02",
    task="analyze this code",
    data={"file": "example.py"}
)
```

## 与其他功能域的交互

- 被 `kernel` 调用：多 Agent 协作场景
- 调用 `storage`: 存储 Agent 注册信息
- 调用 `session`: 管理跨 Agent 会话

## 特点

- 支持 Agent 自动发现
- 任务分发和结果收集
- 心跳检测和重连机制
