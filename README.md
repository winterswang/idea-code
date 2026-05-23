# idea-code

> 多 Agent 文档生成与代码审查工具 — Builder + 双 Reviewer 迭代闭环

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`idea-code` 是一个基于 LLM 的多 Agent 协作框架，通过 Builder 生成 + 双 Reviewer 交叉评审的迭代闭环，自动产出高质量需求文档或技术调研报告。

---

## 目录

- [快速开始](#快速开始)
- [工作原理](#工作原理)
- [体系结构](#体系结构)
- [配置](#配置)
- [内置 Prompt 包](#内置-prompt-包)
- [自定义 Prompt 包](#自定义-prompt-包)
- [CLI 用法](#cli-用法)
- [输出文件](#输出文件)
- [开发](#开发)
- [License](#license)

---

## 快速开始

```bash
# 1. 安装
pip install -e .

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入至少 3 个 API Key（Builder + 2×Reviewer）

# 3. 运行
idea-code "一个命令行待办清单工具" --prompt requirements-dev-doc
idea-code "调研主流 Python Web 框架" --prompt requirements-research

# 4. 查看可用的 Prompt 包
idea-code --list-prompts

# 5. 恢复中断的会话
idea-code --resume <project-slug>
```

---

## 工作原理

```
种子想法 → Builder 生成文档 → RevA 评分 → RevB 评分
                ↑                                    |
                └── 合并反馈，下一轮迭代 ──────────────┘
    双 Reviewer 总分 >= 95 且 意图对齐 >= 27/30 且 每维度 >= 75% → 收敛
```

### 收敛判定（三层门控）

| 层级 | 条件 | 说明 |
|------|------|------|
| 总分门控 | 双 Reviewer 均 ≥ 95 | 必要条件 |
| 意图对齐门控 | 双 Reviewer 意图维度均 ≥ 27/30 (90%) | 防止偏题 |
| 逐维度门控 | 双 Reviewer 每个维度得分 ≥ 75% 满分 | 防止短板 |

### 容错机制

- **Reviewer 重试**: JSON 解析失败或维名校验不匹配时，自动重试最多 2 次
- **单 Reviewer 降级**: 某个 Reviewer 连续 2 轮异常时自动标记为 dead，切换为单 Reviewer 模式
- **Reviewer 复活**: dead 标记后的 Reviewer 若后续轮次评分恢复 >0，自动重启
- **停滞检测**: 最近 3 轮评分波动 <2 分时告警
- **近收敛建议**: 未收敛但评分 ≥88 时，提示增加 `--max-rounds`
- **中间态保存**: 每轮结束后自动保存 `state.json`，支持 `--resume` 恢复

---

## 体系结构

```
idea_code/
├── main.py          # CLI 入口（argparse）
├── orchestrator.py  # 核心编排器（Builder + 双 Reviewer 迭代）
├── loop.py          # Agent 核心循环（LLM 调用 → 工具执行 → 循环）
├── subagent.py      # 子 Agent 启动器（context 隔离）
├── review.py        # 评分解析 + 收敛判定 + 反馈合并
├── compact.py       # 上下文压缩（三层管道：micro / auto / manual）
├── context.py       # AgentContext 封装（Anthropic client + model + tokens）
├── tools.py         # 工具集（bash / read / write / edit / web_search）
├── config.py        # 全局配置常量 + 环境变量校验
├── state.py         # 状态持久化（state.json + reviews/）
├── logger.py        # 结构化日志（RunLogger）
├── tracer.py        # 执行追踪器（JSONL + 人类可读报告）
├── utils.py         # 工具函数（slugify）
└── prompts/
    └── manager.py   # Prompt 包注册表（目录扫描 + 动态加载）

prompts/             # Prompt 包目录（每个子目录 = 一个包）
├── _shared/         # 共享 Prompt 片段
├── requirements-dev-doc/    # 需求文档生成包
└── requirements-research/   # 技术调研报告包

tests/
├── test_review.py    # 评分解析单元测试
├── test_e2e.py       # 端到端集成测试（需 API Key）
├── test_integration.py
├── test_state.py
├── test_tools.py
├── test_compact.py
├── test_tracer.py
└── test_prompt_manager.py
```

### 数据流

```
CLI (main.py)
  └─→ orchestrator.run()
        ├─→ PromptRegistry 加载 Prompt 包
        ├─→ 创建 3 个 AgentContext (Builder / RevA / RevB)
        └─→ for round in 1..max_rounds:
              ├─→ run_subagent(builder)        → 生成/更新文档
              ├─→ _run_reviewer("a")           → RevA 评分 + JSON 解析
              ├─→ _run_reviewer("b")           → RevB 评分 + JSON 解析
              ├─→ converge_check()              → 三层门控判定
              ├─→ merge_feedback()              → 合并反馈传给 Builder
              └─→ save_state() + save_review_record()
```

---

## 配置

### 环境变量（`.env`）

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `IDEA_API_KEY` | ✅ | — | Builder 的 API Key |
| `IDEA_MODEL` | — | `claude-sonnet-4-6` | Builder 模型 |
| `IDEA_BASE_URL` | — | Anthropic 默认 | Builder API 端点 |
| `IDEA_MAX_TOKENS` | — | `8000` | Builder 最大输出 token |
| `REV_A_API_KEY` | ✅ | — | Reviewer A 的 API Key |
| `REV_A_MODEL` | — | `claude-sonnet-4-6` | Reviewer A 模型 |
| `REV_A_BASE_URL` | — | Anthropic 默认 | Reviewer A API 端点 |
| `REV_B_API_KEY` | ✅ | — | Reviewer B 的 API Key |
| `REV_B_MODEL` | — | `claude-sonnet-4-6` | Reviewer B 模型 |
| `REV_B_BASE_URL` | — | Anthropic 默认 | Reviewer B API 端点 |
| `IDEA_MAX_ROUNDS` | — | `10` | 最大迭代轮数 |
| `IDEA_VERBOSE_LOG` | — | `0` | 设为 `1` 启用详细日志 |
| `SEARCH_PROVIDER` | — | `bigmodel` | 搜索后端: `bigmodel` 或 `minimax` |
| `BIGMODEL_API_KEY` | — | — | BigModel 搜索 API Key |
| `MINIMAX_API_KEY` | — | — | MiniMax 搜索 API Key |
| `IDEA_API_TIMEOUT` | — | `300` | API 超时（秒） |

### 支持的 API 后端

所有后端均兼容 Anthropic Messages API 协议：

| Provider | Base URL |
|----------|----------|
| Anthropic | `https://api.anthropic.com` |
| MiniMax | `https://api.minimaxi.com/anthropic` |
| GLM | `https://open.bigmodel.cn/api/anthropic` |
| Kimi | `https://api.moonshot.cn/anthropic` |
| DeepSeek | `https://api.deepseek.com/anthropic` |

---

## 内置 Prompt 包

| 包 ID | 标签 | 输出文件 | 说明 |
|-------|------|---------|------|
| `requirements-dev-doc` | 需求文档 | `requirements.md` | 从种子想法生成结构化需求文档 |
| `requirements-research` | 技术调研 | `report.md` | 调研技术方案，含可信度分层（🔍/📚/💡） |

---

## 自定义 Prompt 包

在 `prompts/` 下创建子目录，包含以下文件：

```
prompts/my-package/
├── config.json          # 包配置（见下）
├── scoring-a.json       # Reviewer A 评分维度
├── scoring-b.json       # Reviewer B 评分维度
├── builder.md           # Builder 的 system prompt
├── builder-context.md   # Builder 的用户上下文模板
├── reviewer-a.md        # Reviewer A 的 system prompt
├── reviewer-a-context.md
├── reviewer-b.md
└── reviewer-b-context.md
```

### `config.json` 示例

```json
{
  "label": "我的文档包",
  "description": "描述这个包做什么",
  "output_file": "output.md",
  "reviewer_count": 2,
  "builder": {
    "role": "高级技术文档工程师",
    "model": "IDEA",
    "prompt_file": "builder.md",
    "context_file": "builder-context.md"
  },
  "reviewer_a": {
    "name": "技术视角评审",
    "scoring_file": "scoring-a.json",
    "prompt_file": "reviewer-a.md",
    "context_file": "reviewer-a-context.md"
  },
  "reviewer_b": {
    "name": "产品视角评审",
    "scoring_file": "scoring-b.json",
    "prompt_file": "reviewer-b.md",
    "context_file": "reviewer-b-context.md"
  }
}
```

### 模板变量

Prompt 模板支持 `{variable}` 替换，可用变量取决于上下文类型：

**Builder 上下文**: `{seed}`, `{feedback}`, `{output_file}`, `{review_history_summary}`

**Reviewer 上下文**: `{seed}`, `{doc_content}`, `{scoring_table}`, `{round_num}`, `{max_rounds}`, `{review_history_summary}`

**Reviewer system prompt**: `{role_name}`, `{scoring_philosophy}`, `{scoring_table}`

---

## CLI 用法

```
usage: idea-code [-h] [--prompt PACKAGE_ID] [--list-prompts]
                 [--resume RESUME_PROJECT] [--max-rounds MAX_ROUNDS]
                 [--prompts-dir PROMPTS_DIR]
                 [seed]

多 agent 文档生成与代码审查工具

位置参数:
  seed                种子想法（自由文本）

可选参数:
  --prompt PACKAGE_ID  Prompt 包 ID（如 requirements-dev-doc）
  --list-prompts       列出所有已注册的 Prompt 包
  --resume PROJECT     恢复指定项目的会话
  --max-rounds N       最大迭代轮数（默认: 10）
  --prompts-dir DIR    Prompt 配置目录（默认: prompts）
```

---

## 输出文件

每次运行在 `projects/<slug>/` 下生成：

```
projects/<slug>/
├── seed.md              # 种子想法
├── state.json           # 会话状态（支持 resume）
├── run-log.json         # 运行摘要
├── requirements.md      # 生成的文档（或 report.md）
├── reviews/
│   ├── round-01.json    # 第 1 轮双 Reviewer 评审记录
│   ├── round-02.json
│   └── ...
├── execution.jsonl      # 机器可读 JSONL 日志（IDEA_VERBOSE_LOG=1）
├── execution.txt        # 人类可读执行报告（IDEA_VERBOSE_LOG=1）
└── contexts/            # 每轮完整的 system/user prompt（IDEA_VERBOSE_LOG=1）
```

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行单元测试
pytest tests/ -v --ignore=tests/test_e2e.py

# 运行端到端测试（需要 API Key）
IDEA_API_KEY=xxx REV_A_API_KEY=xxx REV_B_API_KEY=xxx pytest tests/test_e2e.py -v

# 代码风格
pip install ruff
ruff check idea_code/
```

---

## License

MIT
