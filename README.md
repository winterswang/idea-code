# idea-code

> 多 Agent 文档生成与代码审查工具 — Builder + 双 Reviewer 迭代闭环

## 快速开始

```bash
pip install -e .
cp .env.example .env  # 填入 API Keys
idea-code "一个命令行待办清单工具" --prompt requirements-dev-doc
idea-code "调研主流 Python Web 框架" --prompt requirements-research
idea-code --list-prompts
```

## 架构

```
种子 → Builder 生成文档 → RevA 评分 → RevB 评分
         ↑                                    |
         └── 合并反馈，下一轮迭代 ─────────────┘
    双>=95 且意图>=27/30 且逐维度>=75% → 收敛
```

- **Builder**: MiniMax-M2.7，三阶段工作模式
- **Reviewer**: deepseek-v4-pro × 2，5 步程序化评分
- **日志**: `execution.jsonl` + `execution.txt` + `contexts/`

## 内置包

| 包 | 产出 |
|------|------|
| `requirements-dev-doc` | `requirements.md` |
| `requirements-research` | `report.md` |

## 文档

`BUG_LOG.md` / `DESIGN.md` / `TODO.md` / `CONVENTIONS.md`

## 版本

v0.4.1 — Research 信息可信度分层（🔍/📚/💡）+ 三阶段对齐
