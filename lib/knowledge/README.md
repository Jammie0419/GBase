# 📚 Knowledge Management (知识管理)

> 知识图谱 + 项目记忆

## ⚠️ 状态：未实现

本功能域的文件已创建但**尚未实现**，仅作为占位符存在。后续版本将实现这些功能。

## 包含文件

| 文件 | 计划功能 | 状态 |
|------|---------|:---:|
| `km_base.py` | 知识管理基础 | ❌ 未实现 |
| `km_graph.py` | 知识图谱 | ❌ 未实现 |
| `km_tools.py` | 知识管理工具 | ❌ 未实现 |
| `project_memory.py` | 项目记忆系统 | ❌ 未实现 |

## 计划功能

### km_base.py - 知识管理基础
- 知识存储抽象层
- 知识条目管理
- 知识关系定义

### km_graph.py - 知识图谱
- 知识关系图构建
- 图遍历和查询
- 知识推理

### km_tools.py - 知识管理工具
- 知识导入/导出工具
- 知识可视化工具
- 知识分析工具

### project_memory.py - 项目记忆系统
- 项目级知识沉淀
- 项目历史追踪
- 项目上下文管理

## 与其他功能域的交互（计划）

- 与 `memory/` 集成：项目记忆作为记忆系统的扩展
- 与 `experience/` 集成：从经验中自动提取知识
- 与 `skills/` 集成：知识库支持技能推荐
- 被 `tools/knowledge.py` 调用：提供知识查询工具

## 当前替代方案

目前 GBase 使用 `storage.py` 中的 knowledge 表进行简单的知识存储，通过 `tools/knowledge.py` 提供知识查询工具。

## 参考

- 在 `editions/` 中，这些文件被标记为 `MOD_KNOWLEDGE_MGMT` 和 `MOD_PROJECT_MEMORY` 模块
- 未来实现时，这些模块将被激活
