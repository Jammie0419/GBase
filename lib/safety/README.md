# 🚨 Lifeline & Safety (自救与安全)

> 快照→回滚→熔断 + 沙箱 + 路径校验

## 功能定位

Safety 系统提供多层次保护：文件快照、自动回滚、熔断机制、沙箱隔离、路径校验，确保 Agent 操作的安全性。

## 包含文件

| 文件 | 功能 | 行数 | 状态 |
|------|------|:---:|:---:|
| `lifeline.py` | 自救系统：三层保护（快照→回滚→熔断） | 436 | ✅ |
| `sandbox_safety.py` | 沙箱安全推演：修改核心文件前三步推演防火墙 | 237 | ✅ |
| `path_safety.py` | 路径安全校验：输出路径白名单验证 | 73 | ✅ |
| `safe_io.py` | 安全 IO | - | ❌ 未实现 |

## API 接口

```python
from lib.safety.lifeline import Lifeline

lifeline = Lifeline()

# 创建快照
snapshot_id = await lifeline.create_snapshot("before_modification")

# 回滚到快照
await lifeline.rollback(snapshot_id)

# 检查是否需要熔断
if await lifeline.should_circuit_break():
    # 触发熔断
    await lifeline.circuit_break()
```

```python
from lib.safety.sandbox_safety import SandboxSafety
from lib.safety.path_safety import PathSafety

# 沙箱检查
sandbox = SandboxSafety()
if not await sandbox.can_modify(target_file):
    # 拒绝修改
    raise SafetyViolation()

# 路径校验
path_safety = PathSafety()
if not path_safety.is_allowed(output_path):
    raise PathViolation()
```

## 与其他功能域的交互

- 被 `write_file` 工具调用：写文件前创建快照
- 被 `self_edit` 工具调用：修改自身代码前安全检查
- 调用 `backup`: 文件级备份支持
- 调用 `git`: Git 级快照支持

## 特点

- **三层保护**：快照 → 回滚 → 熔断
- **沙箱隔离**：核心文件修改前三步推演
- **路径白名单**：防止越界操作
- **自动熔断**：检测到异常自动停止操作
