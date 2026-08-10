# SPDX-License-Identifier: MIT
"""
scripts/seed_knowledge.py

将项目文档导入知识库，使 RAG 检索能命中项目信息。
用法: python scripts/seed_knowledge.py
"""

import json
import os
import sqlite3
import sys
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.storage import Storage


def main():
    storage = Storage()
    storage.setup()

    # 要导入的文件列表：(路径, 标题, 摘要)
    docs_to_import = [
        # 核心规则文档
        ("rules/CONSTITUTION.md", "宪法 - 核心约束", "GBase 的核心约束和不可变原则，定义了 AI 的行为边界"),
        ("rules/EVOLUTION.md", "自动进化规则", "描述了自进化的触发条件（对话结束、新信息吸收、工具调用后）和进化流程（refraction → self-improving → skill-crafter）"),
        ("rules/THINKING.md", "思维杠杆规则", "描述了任务分析、思维方法选择和元工具约束"),
        ("rules/WORKFLOW.md", "工作流规则", "描述了任务执行的标准流程和阶段"),
        ("rules/AGENCY.md", "代理权限规则", "描述了 AI 的自主权限和决策边界"),
        ("rules/FINISH.md", "完成规则", "描述了任务完成的标准和检查清单"),
        ("rules/INVESTIGATE.md", "调查规则", "描述了问题调查和调试的方法论"),

        # 核心模块文档
        ("lib/evolution_engine.py", "进化引擎源码", "实现了 4 阶段进化周期：触发判断 → 多角度评估 → 回滚决策 → 恢复诊断。包含 EvolutionEngine 类和 full_evolution_cycle 函数"),
        ("lib/experience.py", "经验引擎源码", "实现了经验提取（5 条优先规则：工具过多/超时/用户反馈/回滚/无进展）、经验存储和进化日志管理"),
        ("lib/identity.py", "身份系统源码", "实现了 AI 的自我认知、反思机制和身份约束"),
        ("lib/mirror.py", "镜像引擎源码", "实现了风格适配和用户偏好学习机制"),
        ("lib/kernel.py", "主内核源码", "GBase 的核心调度器，协调身份注入、经验检索、知识检索、LLM 路由和经验提取"),
    ]

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    imported = 0

    # 直接操作数据库（因为 Storage 没有 search 方法，我们需要检查是否已存在）
    conn = sqlite3.connect(storage._db_path)

    for filepath, title, summary in docs_to_import:
        full_path = os.path.join(project_root, filepath)
        if not os.path.exists(full_path):
            print(f"⚠️  跳过（不存在）: {filepath}")
            continue

        # 检查是否已存在（通过 summary 去重）
        cursor = conn.execute(
            "SELECT id FROM entries WHERE summary = ?",
            (summary,)
        )
        if cursor.fetchone():
            print(f"⏭️  已存在，跳过: {title}")
            continue

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 使用 Storage.write() 写入
        entry_data = {
            "title": title,
            "source": filepath,
            "content": content,
            "auto_imported": True,
        }

        row_id = storage.write(
            type_="knowledge",
            entry=entry_data,
            summary=summary,
            confidence="high",  # 项目文档是高置信度知识
        )

        if row_id > 0:
            imported += 1
            print(f"✅ 导入: {title} (id={row_id}, {len(content)} 字符)")
        else:
            print(f"❌ 写入失败: {title}")

    conn.close()
    storage.close()

    print(f"\n完成！共导入 {imported} 条知识。")
    print(f"现在可以测试: 问 '有哪些自进化功能' 应该能检索到了。")


if __name__ == "__main__":
    main()
