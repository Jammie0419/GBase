# 🛠 Skill System (技能系统)

> 加载 + 路由 + 自动创建 + 模式学习

## 功能定位

Skill System 提供可插拔的技能管理：自动加载、智能路由、从经验自动生成新技能、学习常见任务的工具调用模式。

## 包含文件

| 文件 | 功能 | 行数 | 状态 |
|------|------|:---:|:---:|
| `loader.py` | Skill 加载器：从 skills/ 目录扫描和加载技能 | 167 | ✅ |
| `router.py` | Skill 路由器：根据用户输入自动匹配适用 Skill | 429 | ✅ |
| `crafter.py` | 技能工匠：从重复经验模式自动生成新技能 | 423 | ✅ |
| `loop_cache.py` | LOOP 缓存：工具调用模式学习 + 模板回放 | 155 | ✅ |
| `skillopt.py` | 技能优化 | - | ❌ 未实现 |

## API 接口

```python
from lib.skills.loader import SkillLoader

loader = SkillLoader()

# 加载所有技能
skills = await loader.load_all()

# 加载特定技能
skill = await loader.load("code-review")
```

```python
from lib.skills.router import SkillRouter

router = SkillRouter()

# 自动匹配技能
matched_skill = await router.match("帮我审查这段代码")

# 获取技能使用统计
stats = router.get_usage_stats()
```

```python
from lib.skills.crafter import SkillCrafter

crafter = SkillCrafter()

# 从经验自动生成技能
new_skill = await crafter.craft_from_experience(experience_data)
```

```python
from lib.skills.loop_cache import LoopCache

cache = LoopCache()

# 学习工具调用模式
cache.learn(task_pattern, tool_call_sequence)

# 回放模式
cached_sequence = cache.replay(task_pattern)
```

## 与其他功能域的交互

- 被 `kernel` 调用：任务执行前匹配技能
- 调用 `experience`: 从经验中提取模式生成技能
- 调用 `storage`: 存储技能定义和使用统计
- 被 `evolution` 调用：技能使用效果评估

## 特点

- **自动加载**：扫描 skills/ 目录自动发现技能
- **智能路由**：基于语义匹配自动选择技能
- **自动创建**：从重复经验模式自动生成新技能
- **模式学习**：学习常见任务的工具调用序列，确定性回放
- **使用追踪**：记录技能使用频率和效果
