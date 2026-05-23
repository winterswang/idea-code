# idea-code 项目审查报告

> **状态**：v0.3.2 | 32 个 Bug 已修复 | 3 架构缺陷已落地 | 测试 43/43 通过
> **最后更新**：2026-05-20

---

## 文档导航

| 文件 | 内容 |
|------|------|
| `BUG_LOG.md` | 30 个已修复问题清单（#1-#30） |
| `DESIGN.md` | 架构缺陷 + orchestrator 流程级问题 + 日志/评分体系设计 |
| `TODO.md` | 当前待办清单 |

## 项目结构

```
idea-code/
├── idea_code/           # 核心代码
│   ├── orchestrator.py  # Builder + 双 Reviewer 迭代闭环
│   ├── review.py        # 评分解析 / 收敛判定 / 分类引擎
│   ├── loop.py          # agent 核心循环（LLM ↔ 工具）
│   ├── subagent.py      # 子 agent 隔离运行
│   ├── tracer.py        # 结构化执行日志（JSONL + TXT + contexts）
│   ├── tools.py         # bash / read / write / edit / web_search
│   ├── compact.py       # 上下文压缩（三层管道）
│   ├── logger.py        # 轮次级计时 + 评分日志
│   ├── state.py         # 轻量持久化（state.json + reviews/）
│   ├── context.py       # AgentContext 封装
│   ├── config.py        # 环境变量 + 常量
│   ├── main.py          # CLI 入口（--prompt / --resume / --list-prompts）
│   └── prompts/         # Prompt 包注册表 + 管理器
├── prompts/             # Prompt 包（能力单元，不改代码扩展）
│   ├── _shared/         # 共享 Prompt 模板
│   ├── requirements-dev-doc/   # 研发需求文档生成
│   └── requirements-research/  # 调研报告生成
├── tests/               # 43 个测试（单元 + 集成）
├── BUG_LOG.md
├── DESIGN.md
├── TODO.md
└── project_review.md
```

## 收敛条件（当前）

```
总分 ≥ 95  AND  意图对齐 ≥ 27/30  AND  每维度 ≥ 75% 满分  → 收敛
```

## 版本历史

```
v0.3.2  Reviewer 程序化评分流程（5 步替代声明式）
v0.3.1  Builder 三阶段工作模式（计划→执行→自检）
v0.3.0  Builder 修复分类框架（阻塞问题分类引擎）
v0.2.4  merge_feedback 优先级排序
v0.2.3  web_search 退化提示
v0.2.2  Reviewer 降级复活
v0.2.1  初始提交（全链路审计 + 评分校验 + 降级模式）
```

## 运行

```bash
cd idea-code
python -m pytest tests/ -q          # 43/43 通过

# E2E 测试（需要 .env 配置 API keys）
python _e2e_devdoc.py               # DEV-DOC
python _e2e_research.py             # RESEARCH
```
