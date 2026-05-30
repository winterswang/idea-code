# PROJECT_LOG.md — idea-code

> 多 Agent 文档生成与代码审查工具 — Builder + 双 Reviewer 迭代闭环

<!-- @@LAST_ANALYZED: b1b337b @@-->
<!-- 最后更新: 2026-05-30 21:00 — v0.4.4 全量更新 -->

---

## 🏗️ 系统架构

### 核心流程

```
种子想法 ──→ Builder (MiniMax-M2.7) ──→ 输出文档
                                         ↓
                              Reviewer A (deepseek-v4-pro) ←─→ Reviewer B (deepseek-v4-pro)
                                         ↓
                                  合并反馈 → 下一轮迭代
                                    ↕
                              收敛判定 (三层检查)
```

### 组件表

| 模块 | 文件 | 职责 | 行数 |
|------|------|------|------|
| 编排器 | `orchestrator.py` | v1 流程编排：Builder + 双 Reviewer 迭代闭环 | 664 |
| 评分系统 | `review.py` | JSON 解析、收敛判定、反馈合并、阻塞分类、历史压缩 | 414 |
| 执行追踪 | `tracer.py` | 结构化 JSONL + 人类可读执行报告 | 279 |
| 上下文压缩 | `compact.py` | 三层管道：micro → auto → (预留 manual) | 91 |
| 工具集 | `tools.py` | bash / read / write / edit / web_search | 292 |
| 子 Agent | `subagent.py` | 独立 context + ThinkingBlock 检测 + max_tokens 自适应重试 | 67 |
| Agent 循环 | `loop.py` | LLM 调用 → 工具执行 → stop_reason 透传 | 60 |
| Prompt 管理器 | `prompts/manager.py` | 目录扫描 + 动态注册 PackageConfig | 218 |
| AgentContext | `context.py` | 封装 Anthropic client + model + max_tokens | 27 |
| 配置 | `config.py` | 环境变量、常量；不含 ProviderConfig | 20 |
| 状态持久化 | `state.py` | state.json (version 2) + reviews/ 每轮 JSON | 68 |
| 运行日志 | `logger.py` | RunLogger 结构化日志 | 60 |
| CLI 入口 | `main.py` | Argparse CLI：运行/恢复/列表 | 135 |
| 工具函数 | `utils.py` | slugify 等 | 15 |

### 测试覆盖

| 测试文件 | 行数 | 覆盖模块 |
|----------|------|----------|
| `test_review.py` | 128 | review.py 核心函数 |
| `test_tracer.py` | 72 | tracer.py 全功能测试 |
| `test_compact.py` | 75 | compact.py 压缩管道 |
| `test_state.py` | 52 | state.py 持久化 |
| `test_tools.py` | 69 | tools.py 安全路径/Bash/读写编辑 |
| `test_prompt_manager.py` | 98 | PromptRegistry 动态注册 |
| `test_e2e.py` | 158 | 端到端（需要 API Key） |
| `test_integration.py` | 151 | 集成测试（不调 LLM） |

### 数据流

```
main.py (CLI)
  ↓ seed + --prompt
orchestrator.run()
  ├─ 1. 加载 PackageConfig → 渲染 Prompt
  ├─ 2. 创建 3 个 AgentContext (Builder, RevA, RevB)
  ├─ 3. 迭代 (max_rounds):
  │    ├─ Builder → run_subagent → 输出文档 (write_file)
  │    ├─ Reviewer A → JSON 解析/校验 → ReviewResult
  │    ├─ Reviewer B → JSON 解析/校验 → ReviewResult
  │    ├─ 收敛判定 (总分/意图/逐维度)
  │    └─ 合并 feedback → 下一轮
  ├─ 4. 保存 state.json + reviews/ + run-log.json
  └─ 5. tracer.close() → execution.txt 报告
```

---

## 🚀 功能特性

### F-001: Builder + 双 Reviewer 迭代闭环 (v0.2.1)
- Builder 生成/更新文档，双 Reviewer 独立评分
- 每轮合并 feedback 传回 Builder，持续迭代改进
- 收敛条件: 双 >=95 且意图 >=27/30 且逐维度 >=75%
- **文件**: `orchestrator.py`, `review.py`

### F-002: 全链路审计日志 (v0.2.1)
- `ExecutionTracer` — JSONL + 人类可读双输出
- `RunLogger` — 每轮耗时/评分/Token 汇总
- `contexts/` — 每一轮 Builder/Reviewer 的 system+user 上下文快照
- **文件**: `tracer.py`, `logger.py`

### F-003: 维名校验 + 总分校验 + 逐维度门槛 (v0.2.1)
- 校验 Reviewer 输出维度名是否与 scoring-*.json 一致
- 校验 declared total_score 是否等于各维度 score 之和
- 校验每个维度 >= 满分 75%
- **文件**: `review.py`

### F-004: 单 Reviewer 降级模式 (v0.2.1)
- 连续 2 轮解析失败自动降级为单 Reviewer 模式
- 复活检测: 评分恢复 >0 自动恢复双模式
- **文件**: `orchestrator.py`

### F-005: Builder 三阶段工作模式 (v0.3.1)
- 阶段一: 阅读历史评审 → 制定修复计划
- 阶段二: 逐章执行 → 每章修改后立即读取验证
- 阶段三: 全文档自检 → 确保无遗漏
- **文件**: `prompts/*/builder.md`

### F-006: Reviewer 程序化评分流程 (v0.3.2)
- 5 步替代 5 条声明式原则
- 更结构化的评审流程，减少 LLM 幻觉
- **文件**: `prompts/*/reviewer-*.md`

### F-007: Builder 阻塞问题分类引擎 (v0.3.0)
- O(1) 关键词规则引擎分类: 架构矛盾 / 缺失覆盖 / 事实错误 / 通用改进
- 修复策略矩阵联动 builder.md 提示
- **文件**: `review.py` (`_classify_issue`)

### F-008: 文档拆分 — BUG_LOG/DESIGN/TODO (v0.4.0)
- 将单一大文档拆分为 BUG_LOG.md + DESIGN.md + TODO.md
- 更精确的边界、更清晰的责任域
- **文件**: 项目根目录文档

### F-009: 收敛参数配置化 (v0.4.0)
- `pass_threshold` 可配置 (per-scoring-file)
- `merge_feedback` 过滤 dead Reviewer
- 评分停滞检测 (最近 3 轮变幅 < 2)
- **文件**: `orchestrator.py`, `prompts/manager.py`

### F-010: Research 信息可信度分层 (v0.4.1)
- 🔍 已验证 — 来自可靠来源且交叉验证
- 📚 有可靠来源 — 单一可追溯来源
- 💡 模型推断 — 无可靠来源，模型基于知识推断
- Reviewer 联动检查标注完整性
- **文件**: `prompts/requirements-research/*.md`

### F-011: Research/DevDoc 三阶段对齐 (v0.4.1→v0.4.2)
- RESEARCH 包采用与 DEV-DOC 一致的三阶段 Builder 模式
- 修复禁止项: Builder 不得直接输出无关内容
- 意图偏离扣分: Reviewer 检查文档是否偏离种子核心意图
- **文件**: `prompts/requirements-research/builder.md`

### F-012: 三层上下文压缩管道 (v0.3.x)
- **micro_compact**: 每轮静默替换旧 tool_result 为占位符
- **auto_compact**: 超 100K token 阈值时 LLM 自动总结
- **compact_review_history**: 跨轮评审历史 LLM 压缩为结构化摘要
- **文件**: `compact.py`, `review.py`

### F-013: idea-code-docs skill (v0.4.0)
- AI 自动更新 CONVENTIONS.md / BUG_LOG.md / DESIGN.md 的节点
- 自动文档映射约定
- **文件**: `CONVENTIONS.md`

### F-014: Builder 独立 max_tokens 配置 (v0.4.3)
- IDEA_BUILDER_MAX_TOKENS > IDEA_MAX_TOKENS > 32000 三级优先级
- Reviewer 保持独立角色配置，不受 Builder 窗口影响
- **文件**: `orchestrator.py`

### F-015: Builder Round 1 SOP 对齐 (v0.4.3)
- Round 1 从「直接生成」重构为 规划→生成→自检 三阶段
- dev-doc + research 双包同步对齐
- 自检包括: 7 章完整性、章节间矛盾检测、种子意图覆盖
- **文件**: `prompts/*/builder.md`, `prompts/*/builder-context.md`

### F-016: Resume 评分确认 (v0.4.3)
- --resume 时显示上一轮具体评分 (A=xx/100, B=xx/100)
- 用户可确认恢复的是哪个运行状态
- **文件**: `main.py`

### F-017: stderr 诊断输出 (v0.4.3)
- Builder/Reviewer A/B 的 except 块全部输出到 stderr (file=sys.stderr)
- 附带 scores_history 辅助上下文定位
- 避免 tee stdout 时丢失异常信息
- **文件**: `orchestrator.py`

### F-018: ThinkingBlock 检测 + max_tokens 自适应重试 (v0.4.3)
- subagent.py 检测 DeepSeek/其他模型的 ThinkingBlock-only 响应
- 自动以 2x max_tokens 重试（上限 2 次深度）
- agent_loop 透传 stop_reason 供调用方判断
- **文件**: `subagent.py`, `loop.py`

---

## 🐛 Bug 跟踪

### B-001: 缺陷 1 — Builder 缺少修复分类框架 (v0.3.0) ✅ 已修复
- **症状**: Builder 无法区分阻塞问题的严重程度
- **根因**: builder.md 缺少修复策略矩阵
- **修复**: 引入阻塞问题分类引擎 + builder.md 修复策略矩阵
- **关联**: `review.py`, `prompts/*/builder.md`

### B-002: 缺陷 2 — Builder 缺少三阶段工作模式 (v0.3.1) ✅ 已修复
- **症状**: Builder 直接输出最终文档，缺少分步骤迭代
- **根因**: 提示词中未定义工作阶段
- **修复**: 计划→逐章执行→自检，三阶段强制流程
- **关联**: `prompts/*/builder.md`

### B-003: 缺陷 3 — Reviewer 评审流程缺乏程序化 (v0.3.2) ✅ 已修复
- **症状**: Reviewer 输出质量不稳定，5 条声明式原则难执行
- **根因**: 评审流程过于抽象
- **修复**: 5 步程序化评分流程替代声明式原则
- **关联**: `prompts/*/reviewer-*.md`

### B-004: merge_feedback 噪声干扰 (v0.4.0) ✅ 已修复
- **症状**: dead Reviewer 的 score=0 噪声影响 Builder
- **根因**: merge_feedback 未过滤 score=0 的 Reviewer
- **修复**: 合并前过滤总分为 0 的 Reviewer
- **关联**: `orchestrator.py` 第 572 行

### B-005: Reviewer 降级/复活机制缺失 (v0.2.2 → v0.4.0) ✅ 已修复
- **症状**: Reviewer 一旦 dead 无法复活；死亡信号与 score=0 未区分
- **根因**: 降级逻辑未识别 error 与 score=0 的差异
- **修复**: `result.error` 区分 signal; 复活检测 (评分 >0 自动复活)
- **关联**: `orchestrator.py` 第 462 行

### B-006: web_search 退化无提示 (v0.2.3) ✅ 已修复
- **症状**: API Key 缺失时搜索静默失败
- **修复**: 添加退化提示告知 Builder 可降级运行
- **关联**: `tools.py` 第 101 行

### B-007: #24 反馈优先级排序缺失 (v0.2.4) ✅ 已修复
- **症状**: Builder 得到无优先级排序的大量反馈
- **修复**: merge_feedback 按阻塞问题 > 低分维度 > 逐维度评审 > 建议 排序
- **关联**: `review.py` 第 254 行

### B-008: Builder Round2+ 重新生成而非修改 (v0.4.0) ✅ 已修复
- **症状**: Builder 每轮重新生成完整文档，丢失已有内容
- **修复**: 提示词明确指引 Builder 使用 read_file 读取现有文档再增量修改
- **关联**: `prompts/*/builder-context.md`

### B-009: 收敛标记 & 死亡信号区分 (v0.4.0) ✅ 已修复
- **症状**: 降级收敛与正常收敛未区分；error vs score=0 混淆
- **修复**: 降级收敛 (converged_degraded) + error/socre=0 分离
- **关联**: `orchestrator.py` 第 521 行

### B-010: 文档文件误删 (2026-05-24) ✅ 已修复
- **症状**: 提交 "chore: 移除项目文档文件" 删除了项目关键文档
- **根因**: 误操作
- **修复**: 后续提交立即恢复 (`fix: 恢复误删的文档文件`)
- **影响**: 无，已及时恢复

### B-011: consecutive_reviewer_failures 死代码 (v0.4.3)
- **症状**: orchestrator.py:257 声明后从未使用
- **根因**: 变量声明后被 reviewer 逐 Reviewer 检测逻辑取代
- **修复**: 移除死代码
- **关联**: `orchestrator.py` 第 257 行

### B-012: Reviewer except 块缺少 traceback.print_exc() (v0.4.3)
- **症状**: Builder except 有 print_exc，Reviewer A/B 没有
- **根因**: 不一致的异常处理
- **修复**: 统一所有 except 块输出方式
- **关联**: `orchestrator.py` 第 364/401 行

### B-013: per_dim_fail 使用 dir() 检查变量 (v0.4.3)
- **症状**: orchestrator.py:557 用 `'fail_a' in dir()` 检查变量存在性
- **根因**: fail_a/fail_b 在条件块内声明，未显式初始化为 None
- **修复**: 在条件块外预初始化为空列表
- **关联**: `orchestrator.py` per_dim_fail 检测逻辑

### B-014: 测试覆盖缺口 — loop.py / subagent.py / orchestrator.py (v0.4.3)
- **症状**: 三个核心模块无直接单元测试
- **根因**: 开发节奏优先修复 Bug 和 SOP 对齐
- **修复**: 待补充 mock-based 测试
- **关联**: `loop.py`, `subagent.py`, `orchestrator.py`

---

## 📐 架构决策记录 (ADR)

### ADR-001: Builder + 双 Reviewer 迭代闭环
- **日期**: 2026-05-20
- **背景**: 需要多轮迭代保证生成文档质量
- **决策**: Builder 每轮生成→双 Reviewer 独立评审→合并反馈→Builder 下一轮修复
- **替代方案**: 单次生成 (质量不可控)、单 Reviewer (偏倚风险)
- **影响**: 核心架构稳定；但需要 3 个独立 API Key 和模型配置
- **状态**: 已落地 (v0.2.1)

### ADR-002: JSON 驱动的评审输出
- **日期**: 2026-05-20
- **背景**: Reviewer 输出需要程序化解析避免自然语言模糊性
- **决策**: Reviewer 输出严格 JSON 格式，含 reviewer/total_score/passed/dimensions/blocking_issues/suggestions/feedback_for_builder 字段
- **替代方案**: 自然语言评审 (解析困难)、结构化 Markdown (不够严格)
- **影响**: 维名校验 + 总分校验可行；但 LLM 偶尔输出非 JSON 需要重试
- **状态**: 已落地 (v0.2.1)

### ADR-003: 三层收敛判定
- **日期**: 2026-05-20
- **背景**: 单靠总分不能保证文档质量
- **决策**: 总分 >=95 + 意图对齐 >=27/30 + 逐维度 >=75%
- **替代方案**: 仅总分判定 (漏检意图偏离)、仅百分比 (维度缺陷无法暴露)
- **影响**: 收敛条件严格；实践中需要 3-8 轮迭代
- **状态**: 已落地 (v0.2.1)，后续优化 (v0.4.0 配置化)

### ADR-004: 独立 AgentContext 隔离
- **日期**: 2026-05-20
- **背景**: Builder 和 Reviewer 使用不同模型和 API Key
- **决策**: 每次运行创建 3 个独立 AgentContext，配置来自不同环境变量
- **替代方案**: 共享 context (无法差异化模型配置)
- **影响**: 配置灵活，但环境变量多 (IDEA_API_KEY, REV_A_API_KEY, REV_B_API_KEY, 各+_MODEL)
- **状态**: 已落地

### ADR-005: MiniMax-M2.7 (Builder) + DeepSeek V4 Pro (Reviewer)
- **日期**: 2026-05-20
- **背景**: 不同角色的模型需求不同
- **决策**: Builder 使用 MiniMax-M2.7 (生成强、成本低)，Reviewer 使用 DeepSeek V4 Pro (评判严格)
- **替代方案**: 统一模型 (成本/质量不均衡)
- **影响**: 成本优化；但模型可配置性保留 (环境变量 `{ROLE}_MODEL`)
- **状态**: 已落地

### ADR-006: 单 Reviewer 降级 + 复活机制
- **日期**: 2026-05-20 → 2026-05-20 (优化)
- **背景**: API 故障或输出异常不应阻塞整个流程
- **决策**: 连续 2 轮解析失败 → 降级单 Reviewer；评分 >0 → 自动复活
- **替代方案**: 崩溃终止 (容错性差)、跳过但不标记 (状态不透明)
- **影响**: 健壮性高；但降级模式收敛质量低于双 Reviewer
- **状态**: 已落地 (v0.2.1 → v0.4.0 优化)

### ADR-007: 三层上下文压缩管道
- **日期**: 2026-05-20
- **背景**: 多轮迭代后上下文膨胀，超过模型窗口
- **决策**: micro_compact (静默替换) + auto_compact (LLM 总结超阈值) + compact_review_history (跨轮评审压缩)
- **替代方案**: 压缩全部历史 (丢失细节)、不压缩 (窗口溢出)
- **影响**: 长循环稳定；但 auto_compact 需一次额外 LLM 调用
- **状态**: 已落地

### ADR-008: 文档拆分 — BUG_LOG / DESIGN / TODO
- **日期**: 2026-05-20 (v0.4.0)
- **背景**: project_review.md 单文档过大，职责不清晰
- **决策**: 拆分为 BUG_LOG.md + DESIGN.md + TODO.md，各自独立维护
- **替代方案**: 保持单一文档 (不便分模块更新)
- **影响**: 更清晰的文档边界；需同步维护的文档数增加
- **状态**: 已落地

### ADR-009: Research 信息可信度分层标注
- **日期**: 2026-05-23 (v0.4.1)
- **背景**: 调研报告中的信息可靠度差异大，Reader 无法判断
- **决策**: 🔍 已验证 / 📚 有可靠来源 / 💡 模型推断 三级标注体系
- **替代方案**: 统一不标注 (所有信息等权重，误导决策)
- **影响**: 报告可信度提升；但 Builder 需要额外标注工作
- **状态**: 已落地

### ADR-010: 近收敛检测 + 建议
- **日期**: 2026-05-21
- **背景**: 流程结束时评分接近但未达阈值，用户不知道可以继续
- **决策**: 最终评分 >= 88 时提示用户增加 max-rounds 继续迭代
- **替代方案**: 静默结束 (用户错过近收敛机会)
- **影响**: 非阻断，仅建议；提升收敛率
- **状态**: 已落地

### ADR-011: Builder 独立 max_tokens 配置化
- **日期**: 2026-05-25 (v0.4.3)
- **背景**: Builder 产文档需大量 token（26KB ≈ 40000 tokens），Reviewer 只需 JSON（<500 tokens），共用默认值不合理
- **决策**: 新增 IDEA_BUILDER_MAX_TOKENS，三级优先级: IDEA_BUILDER_MAX_TOKENS > IDEA_MAX_TOKENS > 32000
- **替代方案**: 统一 max_tokens 16000（Builder 仍不够）、每次重试翻倍（浪费 API 调用）
- **影响**: 用户明确控制 Builder 窗口；向后兼容（未设置时走共享值）
- **状态**: 已落地

---

## 🔧 技术债务

| ID | 描述 | 优先级 | 状态 |
|----|------|--------|------|
| TD-001 | auto_compact LLM 调用失败时静默回退但丢失上下文 | 低 | 待处理 |
| TD-002 | `_render_round` TUI 输出对非常规 phase 名称缺少处理 | 低 | 待处理 |
| TD-003 | `per_dim_fail` 变量作用域问题 (已记录为 B-013) | 低 | ✅ 已记录 |
| TD-004 | `converge_check()` 在 review.py 定义但 orchestrator.py 有内联逻辑 | 低 | 待统一 |
| TD-005 | Reviewer A/B 串行化 — 可并行（独立 context），~30% 提速 | 中 | 待实现 |
| TD-006 | `_build_review_history` 每轮重新 LLM 压缩历史 — 无缓存 | 低 | 待优化 |
| TD-007 | `compact.py` `micro_compact` 原地修改 messages — 隐式副作用 | 低 | 待重构 |
| TD-008 | LLM 写的文件无路径白名单 — 可覆盖源码 (工具集安全) | 中 | 待加固 |

---

## 🔄 版本记录

### v0.4.4 (当前) — 2026-05-30
- **🔧 F-019: Reviewer A/B 并行化 ($#7)**: ThreadPoolExecutor 替代串行调用，~50% Review 耗时降低
- **🔒 F-020: LLM 写入路径白名单 ($#7)**: write_file/edit_file 仅允许 projects/ 和 .transcripts/ 目录
- **🔧 F-021: 评审历史增量缓存 ($#7)**: round-{N}-summary.txt，O(n)→O(1) LLM 调用
- **🔧 F-023: auto_compact 降级回退 ($#7)**: LLM 摘要失败/太短时保留原始 messages
- **🧹 F-024: 死代码清理 ($#7)**: 删除未被使用的 converge_check (186 行)；移除 consecutive_reviewer_failures 和 dir() hack
- **🧪 测试新增 ($#7)**: loop.py (4 tests) + subagent.py (3 tests) 单元测试
- **🔧 方案 A: 删除 Reviewer 后期倾向 ($#8)**: reviewer-context 中的「后期轮次更倾向接受」整句删除，与评分哲学一致
- **🔧 方案 C: 评分一致性校验 ($#8)**: Reviewer Step 4 新增评分-评语一致性校验，总分<95 时强制自查
- **✅ Bug 闭环**: B-011 (死代码) / B-012 (Reviewer traceback) / B-013 (dir() hack) 均已修复
- **✅ 技术债务闭环**: TD-003 / TD-005 (Reviewer 并行) / TD-008 (路径白名单) 已解决
- **0 open Issues, 0 open PRs**

### v0.4.3 — 2026-05-25
- **🐛 P0 修复: LLM 输出 null 导致进程崩溃 (#1)**: `raw.get("suggestions", [])` 在 JSON 值为 `null` 时返回 `None` → `len(None)` TypeError 崩溃。修复: `or []` 兜底 (review.py)
- **🐛 P0 修复: --resume 忽略前轮反馈 (#1)**: `feedback` 未持久化到 `state.json`，resume 时 Builder 得到"没有反馈信息"。修复: state.json version 1→2, 新增 `feedback` 字段 (state.py, orchestrator.py)
- **🔧 P1 修复: DeepSeek thinking 吃掉全部 max_tokens 预算 (#1)**: Builder 默认 max_tokens 8000→16000；subagent.py 检测 ThinkingBlock-only 响应后自动以 2x 重试；agent_loop 透传 `stop_reason`
- **🔧 Builder+Reviewer SOP 对齐 (#2)**: Round 1 从「直接生成」重构为 规划→生成→自检 三阶段 (dev-doc + research 双包)；Reviewer feedback_for_builder 强制以意图理解开头
- **🔧 stderr 诊断输出 (#2)**: Builder/Reviewer A/B 的 except 块全部 `print(..., file=sys.stderr)`，附带 scores_history，避免 `tee stdout` 时丢失
- **🧪 测试新增**: null JSON 字段反序列化测试 (test_review.py) + feedback 持久化测试 (test_state.py)
- **✅ Issue 闭环**: #1 (null崩溃/resume反馈/max_tokens) + #2 (SOP对齐/诊断输出) 均已修复并关闭

### v0.4.2 — 2026-05-24
- **tracer+compact 单元测试完成**: 16/16 全量测试覆盖
- **全部 TODO 清空**: 累计任务项全部完成
- **清理**: 删除根目录旧脚本、更新 README.md、更新 .gitignore
- **.claude/ 迁移**: 移除到独立 skill 维护
- **文档保护**: 修复误删文档文件
- **📚 README 重写 (`1fa7e24`)**: 全量重写 251→301 行，新增完整的体系结构、Prompt 包开发文档、模板变量说明、CLI 用法、开发指南
- **🔨 工程维护 (`1fa7e24`)**: pyproject.toml 版本号修复 (0.1.0→0.4.1)、添加 dev 可选依赖 (pytest+ruff)

### v0.4.1 — 2026-05-23
- **Research 可信度分层**: 🔍/📚/💡 标注体系 + Reviewer 联动
- **RESEARCH 框架对齐**: 三阶段 Builder 模板、修复禁止项、意图偏离扣分
- **清除误提交 E2E 输出文件**

### v0.4.0 — 2026-05-20
- **文档拆分**: BUG_LOG.md + DESIGN.md + TODO.md
- **pass_threshold 配置化**: scoring-*.json 可配置通过阈值
- **merge_feedback 过滤**: 过滤 score=0 的 dead Reviewer
- **停滞检测**: 最近 3 轮评分变幅 < 2 告警
- **Builder Round2+ 修复**: 引导 Builder 增量修改而非重新生成
- **降级/死亡信号区分**: error vs score=0 分离
- **idea-code-docs skill**: 自动文档映射约定

### v0.3.0 / v0.3.1 / v0.3.2 — 2026-05-20
- **缺陷 1**: Builder 阻塞问题分类框架 + 修复策略矩阵
- **缺陷 2**: Builder 三阶段工作模式 (计划→逐章→自检)
- **缺陷 3**: Reviewer 5 步程序化评分流程

### v0.2.0 — 2026-05-20
- **初始闭环**: Builder + 双 Reviewer 迭代
- **工具集**: bash/read/write/edit/web_search
- **审计日志**: JSONL + 人类可读 + 上下文快照
- **评审校验**: 维度名/总分/逐维度三次校验
- **降级模式**: 单 Reviewer 容错
- **43 测试用例通过**
- BUG 修复系列: #24 优先级排序 / #26 搜索退化提示 / #30 降级复活

---

## 📋 项目状态快照

| 指标 | 值 |
|------|-----|
| 当前版本 | v0.4.4 |
| 代码模块 | 14 个源文件 (idea_code/) |
| 测试文件 | 9 个 (单元 + 集成 + E2E) — ~70 用例 |
| 内置 Prompt 包 | 2 个 (requirements-dev-doc, requirements-research) |
| 核心模型 | 可配置 (Anthropic / MiniMax / DeepSeek / GLM / Kimi) |
| 活跃 Feature | 23 个 (F-001 ~ F-023) |
| 已修复 Bug | 14 个 (B-001 ~ B-014) |
| ADR 记录 | 11 个 (ADR-001 ~ ADR-011) |
| 技术债务 | 5 项 (TD-001~TD-002, TD-004, TD-006~TD-007) |
| 最新提交 | `b1b337b` (安全加固 + Reviewer 并行 + 死代码清理) |
| Git 钩子 | ✅ post-commit 已安装 |
| 已关闭 Issue | 5 个 (#1 #2 #4 #7 #8) |
| 开放 Issue / PR | 0 |
| Code Review 评分 | 7.6/10 (安全 +0.5, 性能 +0.2) |
