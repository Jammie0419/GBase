---
name: 自动知识导入
description: 当知识库检索失败时，自动识别并导入相关项目文档
triggers:
  - 知识库
  - 检索失败
  - knowledge_miss
  - 无命中
auto_generated: true
created_by: skill_crafter
---

# 自动知识导入技能

## 触发条件
当检测到知识检索失败（knowledge_miss）且工具调用次数较多时触发。

## 解决方案
1. 识别用户问题中的关键词
2. 扫描项目文档（rules/*.md, lib/*.py）
3. 将相关文档导入知识库
4. 重新检索并回答

## 执行步骤
```python
from scripts.seed_knowledge import main as seed_knowledge
seed_knowledge()
```

## 预期效果
知识库自动填充，后续同类问题可直接检索命中。



---

## 🔄 进化记录 (2026-08-10 14:58:59)

测试进化：添加了技能使用追踪能力
