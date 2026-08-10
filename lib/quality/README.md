# 🛑 Quality Gates (质量门)

> 门控工作流管道系统

## 功能定位

Quality Gates 提供轻量级的任务质量检查点，确保每个阶段的输出符合预期标准后才进入下一阶段。

## 包含文件

| 文件 | 功能 | 状态 |
|------|------|:---:|
| `pipeline.py` | 门控工作流管道（minimal stub） | ⚠️ 基础实现 |

## API 接口

```python
from lib.quality.pipeline import GatePipeline

# 创建管道
pipeline = GatePipeline()

# 添加检查点
pipeline.add_gate("syntax_check", check_function)
pipeline.add_gate("test_pass", test_function)

# 执行管道
result = await pipeline.execute(task_data)
```

## 与其他功能域的交互

- 被 `evolution/` 调用：进化修改前进行质量检查
- 被 `experience/` 调用：经验提取后进行验证
- 可扩展：每个功能域可以注册自己的质量门

## 注意事项

⚠️ 当前实现为 minimal stub，仅提供基础框架。完整的门控系统需要进一步开发。
