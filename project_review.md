# idea-code 项目深度审查报告

> **审查日期**：2026-05-16 → 2026-05-18
> **状态**：历史 23 个问题全部修复 ✅ | 3 个架构缺陷 + Skill 式 Prompt 已设计、待实施 | 4 个小问题待收尾

---

## 一、审查方法论

### 审查维度

| 维度 | 说明 |
|------|------|
| **需求一致性** | 实现是否忠实于需求文档的核心约定 |
| **设计完整性** | 架构设计是否覆盖所有关键路径和边界条件 |
| **安全性** | 是否存在可利用的攻击向量 |
| **可靠性** | 异常场景下的行为是否可预期、可恢复 |
| **效率** | 是否存在浪费（API 调用、token 消耗、时间） |

### 严重程度定义

| 级别 | 符号 | 含义 |
|------|------|------|
| 致命 | 🔴🔴 | 可直接导致安全事故或核心需求彻底失效 |
| 严重 | 🔴 | 破坏核心设计意图，或在特定条件下导致错误收敛/错误结果 |
| 重要 | 🟡 | 影响可靠性、效率或可维护性，存在明确改进空间 |
| 建议 | ⚪ | 代码质量或细微改进 |

---

## 二、设计层面审查

### ✅ 问题 #1：收敛判定不检查意图对齐分 — 已修复

**位置**：`review.py:converge_check()` + `orchestrator.py` 收敛逻辑

**原始问题**：收敛只看总分 ≥95，不检查意图对齐维度得分，可能导致 Builder 已偏离种子方向但系统错误收敛。

**修复内容**：
- `review.py`：新增 `INTENT_DIM_NAME` / `INTENT_MAX_SCORE` / `INTENT_MIN_RATIO` / `extract_dimension_score()`；`converge_check()` 返回 dict `{passed, total, intent, detail}`
- `orchestrator.py`：每轮提取意图对齐分（≥27/30）传入收敛判定；区分"总分不足"和"意图对齐不足"
- 测试：4 个意图对齐门槛测试 + `extract_dimension_score` 测试

**当前判定逻辑**：总分 ≥95 **且** 意图对齐 ≥27/30（90% 门槛）→ 收敛。✅

---

### ✅ 问题 #2：Reviewer 本身无对齐校验 — Level 0 + Level 1 已实现

**位置**：`orchestrator.py:_reviewer_health_check()`

**修复内容**：
- Level 0（日志透明化）：每轮展示完整维度分解，用户可自行判断
- Level 1（异常告警）：`_reviewer_health_check()` 检测全满分 100、`passed` 与 `total_score` 矛盾、意图对齐极端分歧（≥10 分差距），打印 ⚠️ 告警不阻止流程 ✅
- **已调用**：`orchestrator.py:292` `health_warnings = _reviewer_health_check(result_a, result_b)` ✅

Level 2（跨轮一致性）通过 #4 的 review_history_summary 间接解决。✅

---

### ✅ 问题 #3：Reviewer 反馈关键信息截断 — 已修复

**位置**：`review.py:merge_feedback()`

**修复内容**：`merge_feedback()` 输出增加"逐维度评审结果"段，按 Reviewer 分组展示得分 + comment。保留原有 blocking_issues 和 suggestions 段不变。✅

---

### ⚠️ 问题 #4：Reviewer 盲审 — 代码已实现，上下文链路待补全

**位置**：`orchestrator.py:_run_reviewer()` + `review.py:compact_review_history()`

**修复内容**：
- `review.py`：新增 `compact_review_history(records, ctx)` —— LLM 压缩 N 轮评审历史为结构化摘要 ✅
- `orchestrator.py:107-121`：Round 2+ 时读取历史评审 JSON → 调用 `compact_review_history` ✅
- ⚠️ **断链**：`reviewer-*-context.md` 缺少 `{review_history_summary}` 占位符，生成的摘要被静默丢弃（见 #22）

---

### ✅ 问题 #5：reviewer_count=0 零评审绕过 — 已修复

**位置**：`orchestrator.py:311-321`

**修复内容**：收集活跃 Reviewer 列表 → 零 Reviewer 报错退出 → 所有活跃 Reviewer 总分 ≥95 且意图对齐 ≥27 才收敛。单 Reviewer 自然支持。✅

---

## 三、实现层面审查

### ✅ 问题 #6：`_run_reviewer` 重试判定逻辑 — 已修复

**位置**：`orchestrator.py:_run_reviewer()`

**原始问题**：`total_score > 0` 混用两个语义（解析成功 + 分数非零）。

**修复**：改为 `if result.reviewer:`，用 reviewer 名非空作为解析成功标志。✅

---

### ✅ 问题 #7：`parse_review_output` JSON 提取脆弱 — 已修复

**位置**：`review.py:parse_review_output()`

**修复内容**：
1. 优先 ` ```json ... ``` ` 代码块提取 ✅
2. Fallback：从末尾反向搜索最后一个独立 `{...}` 对象（`text.rfind("}")` + `text.rfind("{", 0, brace_end)`）✅

---

### ✅ 问题 #8：Reviewer `passed` 字段 — 已合并到 health_check

**位置**：`review.py:ReviewResult` + `orchestrator.py:_reviewer_health_check()`

**修复**：`passed=true` 但 `total_score < 95` 时在 `_reviewer_health_check()` 中打印矛盾告警。✅

---

### ✅ 问题 #9：`save_state` round_num 间接计算 — 已修复

**位置**：`orchestrator.py:218, 288`

**修复**：三处 `save_state` 调用已改为直接用循环变量 `round_num=round_num`。✅

---

### ✅ 问题 #10：resume 在已达 max_rounds 时无提示 — 已修复

**位置**：`main.py:66-68`

**修复**：
- `resume_round > max_rounds` 时打印提示并 `sys.exit(0)` ✅
- `or` 陷阱修复：`state.get("max_rounds") if state.get("max_rounds") is not None else args.max_rounds` ✅

---

### ✅ 问题 #11：单 Reviewer 故障静默降级 — 已修复

**位置**：`orchestrator.py:197, 296-309`

**修复**：`consecutive_reviewer_failures` 计数器，所有活跃 Reviewer 均为 0 分时递增，≥2 轮时中断流程并明确告警。✅

---

### ✅ 问题 #12：`estimate_tokens` 对中文严重低估 — 已修复

**位置**：`compact.py:estimate_tokens()`

**修复**：
```python
cjk = sum(1 for c in serialized if '\u4e00' <= c <= '\u9fff')
ascii_chars = len(serialized) - cjk
return int(ascii_chars * 0.3 + cjk * 1.5)
```
CJK 字符单独加权 1.5x。✅

---

### ✅ 问题 #13：Builder 不调用 write_file 时静默继续 — 已修复

**位置**：`orchestrator.py:224-228`

**修复**：Round 1 Builder 未生成文件 → 直接报错退出；后续轮保留 continue 但已兼容。✅

---

## 四、安全层面审查

### ✅ 问题 #14：`shell=True` + 黑名单 — 已修复

**位置**：`tools.py:run_bash()`

**修复**：移除 `shell=True`，改用 `shlex.split()` + `subprocess.run(args, shell=False)`，禁止管道和重定向。✅

---

### ✅ 问题 #15：`safe_path` 符号链接攻击 — 已修复

**位置**：`tools.py:safe_path()`

**修复**：路径逃逸检查后，逐组件检测 symlink，存在则拒绝。✅

---

### ✅ 问题 #16：API Key 泄露到 transcript — 已修复

**位置**：`compact.py:auto_compact()`

**修复**：`_SENSITIVE_PATTERNS` 正则匹配 `sk-ant-` / `API_KEY=` 模式，`_redact_sensitive()` 在写入 transcript 前替换为 `***REDACTED***`。✅

---

## 五、需求 vs 实现 Gap Map

| 需求文档声明 | 实现状态 | 差距 |
|-------------|---------|------|
| Builder 不能偏离种子核心诉求 | 意图对齐分 ≥27/30 强制门槛 + health_check | ✅ |
| 双 Reviewer 不同侧重点 | 两个独立 context 文件 + scoring 文件 | ✅ |
| 双 >=95 通过 | 活跃 Reviewer 动态判定 + 意图对齐 | ✅ |
| 防死循环：关注宏观质量 | Prompt 引导 + health_check + max_rounds | ✅ |
| max_rounds=10 兜底 | 正确实现 | ✅ |
| 状态持久化（轻量） | `state.json` + `reviews/` | ✅ |
| `{prev_output}` 不注入 | Builder 通过 read_file 读取 | ⚠️ 无验证 Builder 是否真的读取了 |
| Code Review → bugfix plan | v4 未开始 | ⬜ state.json.plans 字段为死亡代码 |
| 新增能力 = 加目录不改代码 | PromptRegistry 扫描注册 | ✅ |
| Reviewer 串行（v1） | 当前串行 | ✅ |
| Reviewer 独立 context 文件 | `reviewer-a-context.md` / `reviewer-b-context.md` 独立 | ✅ |

---

## 六、问题汇总（更新后）

| # | 级别 | 类别 | 问题摘要 | 状态 |
|---|------|------|---------|------|
| 1 | 🔴 | 设计 | 收敛判定不检查意图对齐分 | ✅ 已修复 |
| 2 | 🔴 | 设计 | Reviewer 本身无对齐校验 | ✅ 已修复 |
| 3 | 🔴 | 设计 | Reviewer 反馈关键信息截断（维度评语丢失） | ✅ 已修复 |
| 4 | 🔴 | 设计 | Reviewer 盲审——每轮丢失历史上下文 | ✅ 代码已实现（⚠️ 链路断 #22） |
| 5 | 🔴 | 设计 | reviewer_count=0 时零评审通过 | ✅ 已修复 |
| 6 | 🔴 | 实现 | `_run_reviewer` 重试判定逻辑错误 | ✅ 已修复 |
| 7 | 🔴 | 实现 | `parse_review_output` JSON 提取脆弱 | ✅ 已修复 |
| 8 | 🟡 | 实现 | Reviewer `passed` 字段未使用 | ✅ 已修复（合并到 health_check） |
| 9 | 🟡 | 实现 | `save_state` round_num 间接计算 | ✅ 已修复 |
| 10 | 🟡 | 实现 | resume 在已达 max_rounds 时无提示 | ✅ 已修复 |
| 11 | 🟡 | 可靠性 | 单 Reviewer 故障静默降级 | ✅ 已修复 |
| 12 | 🟡 | 效率 | token 估算对中文严重低估 | ✅ 已修复 |
| 13 | 🟡 | 可靠性 | Builder 不写文件时静默继续 | ✅ 已修复 |
| 14 | 🔴🔴 | 安全 | `shell=True` + 黑名单形同虚设 | ✅ 已修复 |
| 15 | 🔴 | 安全 | `safe_path` 不防符号链接攻击 | ✅ 已修复 |
| 16 | 🟡 | 安全 | API Key 泄露到 transcript 文件 | ✅ 已修复 |
| 17 | 🔴 | 覆盖 | orchestrator.py 修改被自动工具覆盖 | ✅ 已修复（代码完整） |
| 18 | 🟡 | 功能 | `logger.py` / `RunLogger` 数据流未完成 | ✅ 已修复（round_start/end 已调用） |
| 19 | 🟡 | 数据流 | `scoring_philosophy` 传递链断裂 | ✅ 已修复（reviewer-*.md 已有占位符） |
| 20 | 🟡 | 可靠性 | `logger.py` `save()` 无异常处理 | ✅ 已修复（try/except 包裹） |
| 21 | ⚪ | 防御 | `validate_env` 与 `create_context` 未形成闭环 | ✅ 已修复（api_key 空值校验） |
| **22** | 🟡 | 数据流 | **`{review_history_summary}` 占位符缺失** | ✅ 已修复（4 个 context 文件追加占位符） |

---

## 七、新问题详情

### 🟡 问题 #22：`{review_history_summary}` 占位符缺失 — 历史摘要静默丢弃

**位置**：`prompts/*/reviewer-*-context.md`（全部 3 个 context 文件）

**现状**：

`orchestrator.py:_run_reviewer()` 已实现完整的 review history 压缩链：
```python
# Line 107-121
review_history_summary = ""
if round_num > 1:
    # 读取历史评审 JSON → compact_review_history(records, ctx)
    ...

# Line 123-131
user = pkg.render_reviewer_context(
    which, seed=..., doc_content=..., scoring_table=...,
    round_num=..., max_rounds=...,
    review_history_summary=review_history_summary,  # ← 传入变量
)
```

`review.py:compact_review_history()` 已实现并正常工作。✅

**但全部 3 个 reviewer context 文件中均无 `{review_history_summary}` 占位符**：

| 文件 | `{review_history_summary}` |
|------|---------------------------|
| `prompts/requirements-dev-doc/reviewer-a-context.md` | ❌ 缺失 |
| `prompts/requirements-dev-doc/reviewer-b-context.md` | ❌ 缺失 |
| `prompts/requirements-research/reviewer-a-context.md` | ❌ 缺失 |

`_render()` 方法对不存在的占位符静默忽略，不会报错。导致**每一轮 LLM 压缩生成的历史摘要被丢弃**，Reviewer 仍然是盲审状态。

**修复**：在 3 个 `reviewer-*-context.md` 末尾追加 `{review_history_summary}` 段，含偏见缓解引导。

---

### 🟡 问题 #20：`logger.py` `save()` 无异常处理（已修复 ✅）

**位置**：`idea_code/logger.py:save()`

已添加 `try/except` 包裹，磁盘满/权限错误时打印警告但不阻断主流程。

---

### ⚪ 问题 #21：`validate_env` 与 `create_context` 未形成闭环（已修复 ✅）

**位置**：`config.py:validate_env()` + `context.py:create_context()`

`create_context` 已增加 `if not api_key: raise ValueError("api_key 不能为空")` 空值校验，与 `validate_env` 形成双重防护。

---

## 八、历史修复验证状态

**v0.1.2 状态**：全部 22 个问题已修复。2026-05-17 逐条源码核实：

| # | 验证结果 | 证据 |
|---|---------|------|
| 1 | ✅ 意图对齐门槛 | `orchestrator.py:419-427`，总分≥95 + 意图≥27/30 |
| 2 | ✅ Reviewer 健康检查 | `_reviewer_health_check()` 已被调用 |
| 3 | ✅ 维度评语完整 | `merge_feedback()` 含逐维度评语 |
| 4 | ✅ Reviewer 历史感知 | `{review_history_summary}` 已注入 4 个 context 文件 |
| 5 | ✅ reviewer_count=0 拦截 | `orchestrator.py:412-417` |
| 6 | ✅ 重试判定 | `if result.reviewer:` 替代 `total_score > 0` |
| 7 | ✅ JSON 提取 | 优先 ```json 块，fallback 反向 brace 搜索 |
| 8 | ✅ passed 字段 | 已合并到 health_check |
| 9 | ✅ round_num 直接传递 | `round_num=round_num` |
| 10 | ✅ resume 边界提示 | `main.py:66-68` |
| 11 | ✅ 连续失败中断 | `consecutive_reviewer_failures >= 2` |
| 12 | ✅ CJK 1.5x 加权 | `compact.py:estimate_tokens()` |
| 13 | ✅ Round 1 中断 | 未生成文件直接退出 |
| 14-16 | ✅ 安全基线 | shell=False / symlink 检测 / API key 脱敏 |
| 17-22 | ✅ 数据流完整性 | logger / scoring_philosophy / review_history_summary |

> **所有 22 个历史问题确认保持修复状态**，未发现退化。

---

## 九、2026-05-17 新增审查：生产项目质量审计

> 审查范围：`idea-code/projects/` 下全部 5 个项目
> 审查焦点：收敛有效性、Builder 修复能力、Reviewer 评审一致性
> 方法论：逐项目读取 seed / requirements / report / state.json / 全部评审记录

### 9.1 项目执行概况

| 项目 | 类型 | 轮数 | RevA 终分 | RevB 终分 | 收敛 | 趋势 | 耗时 |
|------|------|:---:|:---:|:---:|:---:|------|------|
| 天气查询 CLI | dev-doc | 2 | 86 | 93 | ❌ | 持平（84→86） | 4.5 min |
| Markdown 笔记 | dev-doc | **1** | 90 | 91 | ❌ | N/A | — |
| Python Web 框架 | research | 5 | **94** | 91 | ❌ | 上升→退化→回升 | 63 min |
| AI 编程助手 | research | 5 | 73 | 91 | ❌ | 持续下降（78→73） | 37 min |
| 在线白板 | dev-doc | 5 | 83 | 91 | ❌ | 徘徊（80-85） | — |

### 9.2 逐项目诊断

#### 天气查询 CLI — 🟡 轮数不足

- max_rounds=2，Builder 仅一次修改机会
- Round 1→2 得分几乎原地踏步，阻塞问题（API 端点未指定、Key 配置流程缺失）未修复
- Reviewers 反馈精准，但轮数不够 Builder 消化

#### Markdown 笔记 — 🔴 单轮无迭代

- max_rounds=1，等于只有初稿+评审，无反馈闭环
- 初稿质量尚可（90/91），但 Reviewer 反馈（索引机制缺失、title 提取规则含糊）完全浪费

#### Python Web 框架调研 — 🟡 最接近收敛但有退化

- 报告质量最高，含决策矩阵、敏感性分析、版本锁定建议、修复记录
- **Round 2 退化**（80→74）：Builder 修复引入了计算错误（决策矩阵加权分）
- Round 4 单边收敛（RevA=96），但 RevB 停留在 90

#### AI 编程助手调研 — 🔴 质量最差，根本问题未解

- RevA 全程 66-78，终轮仅 73，被 Reviewer 标记为「大部分数据无可验证来源」
- 立项对象错位：「DeepSeek TUI」非独立产品，Builder 始终无法有效修复
- RevA/RevB 分差 18 分，评审共识极弱
- **web_search 工具依赖外部 Key**：未配置则搜索失败，Builder 退回到训练数据

#### 在线白板 — 🟡 深层架构矛盾 5 轮未解

- 5 轮完整迭代，RevA 始终在 80-85
- 终轮仍有 blocking issues：Token 有效期矛盾（7天 vs 15分钟）、LWW 物理时间戳与 Yjs CRDT 冲突
- Round 4 退化（85→80），Builder 局部修补引入了新矛盾

### 9.3 全局指标

| 指标 | 数值 |
|------|------|
| 收敛率 | **0/5 (0%)** |
| 平均 RevA 终分 | 85.2 |
| 平均 RevB 终分 | 91.4 |
| RevA/RevB 平均分差 | 6.2 |
| 出现退化的项目 | 3/5 (60%) |
| max_rounds 默认值 | 10（实际使用 1/2/5） |

---

## 十、新发现：5 个根因

> 以下 5 个问题聚焦「为什么 0/5 项目收敛」的系统级根因，与历史 22 个代码/安全 Bug 属不同层级。其中 #23 已修复，其余 4 个待处理。

### 🔴 问题 #23：`compact_review_history` 压缩摘要精度不足 → Builder 修复策略不聚焦

**位置**：`review.py:compact_review_history()` + `prompts/_shared/compact_review_history.md`

**根因**：

Builder 每轮的 user prompt 中已注入 `{review_history_summary}`（orchestrator.py:270，代码链路完整 ✅）。但 `compact_review_history()` 的原始压缩 Prompt 存在两个问题：

1. **嵌入代码而非独立文件**：Prompt 字符串硬编码在 `review.py:332-341`，违反 Prompt 文件分离的开发规范
2. **摘要结构缺乏可操作性**：原始 Prompt 输出「得分趋势」占主导，Builder 最需要的信息——「哪些阻塞问题仍未解决 / 哪些是新引入的」——被稀释在自然语言趋势描述中，Builder 无法快速定位本周必须修复的 1-3 个核心问题

**影响**：Builder 收到「架构得分从 14 降至 11」这样的趋势描述，但收不到「CRDT 与乐观锁矛盾已持续 5 轮仍未解决，你的修补方向可能错误」——缺乏对修复方向的定向反馈。

**已修复** ✅：
- Prompt 提取为独立文件 `prompts/_shared/compact_review_history.md`
- 升级压缩策略：阻塞问题追踪占 70% 预算，含语义匹配 + 原因分析 + 已修复/仍存在/新引入三态分类
- 得分趋势压缩为单行箭头，退化告警量化（≥3 分）
- `review.py` 改为从文件加载模板（代码行 322-333）

---

### 🔴 问题 #24：`merge_feedback()` 信息过载 + 无优先级排序

**位置**：`review.py:merge_feedback()`

**根因**：

反馈的 `merge_feedback()` 输出结构：

```
## 逐维度评审结果         ← RevA 5维 + RevB 5维，含得分+评语
### 技术视角（86/100）
- **意图对齐**: 30/30
  > ...（评语）
- **技术可行性**: 16/20
  > ...（评语）
...（共 10 个维度段落）
## 阻塞性问题              ← 2-5 条
## 改进建议                 ← 3-10 条
## 上一轮评分
... feedback_for_builder
```

- 总长度约 **1500-3000 字**
- 真正必须修复的 blocking issues 仅占 ~30%
- Builder 被要求「对每个阻塞性问题解释修复 + 对每条建议说明采纳/拒绝」→ 解释开销进一步挤压分析 token

**影响**：Builder 倾向于**全量扫读后局部修补**，而非聚焦最关键的 1-2 个深层问题做结构性修复。

**与历史问题 #3 的关系**：#3 修复了维度评语缺失，但修复带来了新问题——信息量从不足变成了过载。

---

### 🟡 问题 #25：Builder Prompt 缺乏深度修复策略指导

**位置**：`prompts/*/builder.md` 和 `prompts/*/builder-context.md`

**根因**：

| 对比维度 | Reviewer Prompt | Builder Prompt |
|---------|:---:|:---:|
| 评分哲学 | ✅ 保守评分 + 校准参考 | ❌ 无 |
| 问题分类指引 | ✅ blocking vs suggestion | ❌ 无 |
| 修复策略 | — | ❌ 无（仅「解释修复+说明采纳/拒绝」） |
| 工具使用指引 | — | ⚠️ research builder 要求搜索但未提供 fallback |
| 防退化规则 | ✅ 「不要在微观细节上纠缠」 | ❌ 无（无「不要修改已通过的章节」等约束） |

Builder Prompt 只有 5 条通用工作原则 + 输出格式，缺少：
- 问题分类指引：事实错误 → 先验证再修改；架构矛盾 → 先理解再统一；评分细节 → 局部修改
- 防退化指引：「如果某个章节在上轮评审中没有扣分，尽量保持不动」
- 深度修复策略：「如果同一个阻塞问题连续出现 2 轮以上，说明修复方向错误，应重新思考方案」

---

### 🟡 问题 #26：Research Builder 的 web_search 依赖不可靠

**位置**：`tools.py:87-97` + `prompts/requirements-research/builder.md`

**根因**：

Builder System Prompt 要求「必须使用搜索工具」并「标注来源 URL」，但 `web_search` 实现依赖 `BIGMODEL_API_KEY` 环境变量：

```python
api_key = os.getenv("BIGMODEL_API_KEY", "")
if not api_key:
    return "Error: 未配置 BIGMODEL_API_KEY。请在 .env 中设置。"
```

如果用户未配置搜索 Key，Builder 搜索失败后只能退回训练数据——直接触发 Reviewer 的「信息可信度」扣分。

**影响**：AI 编程助手调研项目 Round 1 评分 66，其中「信息可信度」15/25——大量数据被 Reviewer 标记为「未标注来源」「疑似编造」。

---

### 🟡 问题 #27：实际 max_rounds 远低于默认值，未匹配收敛需求

**位置**：`config.py:10` + 各项目 `state.json`

**根因**：

```python
MAX_ROUNDS = int(os.getenv("IDEA_MAX_ROUNDS", "10"))  # 代码默认 10
```

实际执行数据：

| 项目 | 实际 max_rounds | 如果给更多轮次 | 预期 |
|------|:---:|------|:---:|
| 天气 CLI | 2 | +1 轮修复阻塞问题 | 可能收敛 |
| Markdown 笔记 | **1** | +3 轮迭代 | 可能收敛 |
| Web 框架 | 5 | +1-2 轮提升 RevB | **几乎确定收敛**（RevA 已到 96） |
| AI 编程助手 | 5 | +3 轮修复对象错位 | 不确定（基础问题太大） |
| 白板工具 | 5 | +3 轮解决架构矛盾 | 可能收敛 |

Python Web 框架项目在 Round 4 达到 RevA=96，单边已收敛，再多 1-2 轮极大概率双收敛。白板工具和 AI 助手需要更多轮次。

---

---
## 十一、历史 vs 新发现问题交叉对照

| 历史问题 | 新发现 | 关系 |
|---------|--------|------|
| #3 — 反馈关键信息截断 | #24 — 反馈信息过载 | **对立**：补全细节后变得过载 |
| #4 — Reviewer 盲审 | #23 — 压缩摘要精度不足 | **同根因**：历史信息的有效传递 |
| #16 — API Key 泄露 | #26 — web_search 依赖未配置 Key | **同维度**：基础设施依赖脆弱 |

---

## 十二、待处理问题清单（2026-05-18）

### 已完成 ✅

| # | 问题 | 修复时间 |
|---|------|---------|
| 1-22 | 历史 22 个代码/安全/设计问题 | v0.1.0 → v0.1.2 |
| 23 | `compact_review_history` Prompt 提取为独立文件 + 升级阻塞追踪 | 2026-05-17 |

### 架构缺陷 — 方案已设计，待实施 ⬜

| 缺陷 | 方案 | 涉及文件 | 成本 |
|:---:|------|------|:---:|
| **1** — Builder-Reviewer 能力不对称 | 分类引擎 + 修复策略矩阵 + 自检清单 | review.py + builder.md + builder-context.md | 中 |
| **2** — Big-bang 单轮修复 | 三阶段工作模式 | builder.md + builder-context.md + compact_history | 中 |
| **3** — Reviewer 评分矛盾（声明式→程序式） | 5 步流程替代 5 条原则 | 4 个 reviewer-*.md + 4 个 scoring-*.json | 中 |
| **— Skill 式 Builder Prompt** | 思考框架替代规则表 | builder.md + builder-context.md | 中 |

> 以上 4 项全部在 Prompt / review.py 层面，不动 orchestrator / loop / subagent 等核心流程。可独立实施，不冲突。

### 小问题 — 待收尾 ⬜

| # | 问题 | 改动量 |
|---|------|:---:|
| 24 | `merge_feedback()` 无优先级排序（与缺陷 1 部分重叠） | ~30 行 |
| 26 | web_search 依赖外部 API Key | ~10 行 |
| 27 | max_rounds 默认值 vs 实际使用值不匹配 | ~20 行 |

> 注：原 #25 已合并到缺陷 2 的 Builder Prompt 重设计中。

---

## ⚠️ 永久审查纪律 — 文件写入验证（附）

> **每次 `edit_file` 操作后，必须用原生 `exec_shell("grep -n ...")` 验证写入结果，
> 不得依赖 `grep_files` 工具（曾返回虚假匹配）。**
> **写入失败必须立即抛出，不做假设。**

**根因**：
- `edit_file` 的 search 参数涉及多行、含 Unicode 特殊字符时，可能静默匹配失败但工具仍返回成功 diff
- `grep_files` 工具曾对不存在的关键词返回虚假匹配结果
- 两道工具链均存在假阳性，导致写入失败未被发现

**系统性防范**：
| 步骤 | 方法 | 说明 |
|------|------|------|
| 1 | `edit_file` 时 `search` 尽量用单行、短、无特殊 Unicode 的字符串 | 降低匹配失败概率 |
| 2 | 写入后 `exec_shell("grep -n '关键词' 文件")` | 原生 Unix grep，不会虚假匹配 |
| 3 | 关键写入后追加 `exec_shell("python3 -c '读文件输出目标行'")` | 确认写入内容精确 |
| 4 | 禁止用 `grep_files` 工具做写入验证 | 已证实不可靠 |

---

## 十五、核心架构审查：Builder-Reviewer 交互模型缺陷

> 审查日期：2026-05-17
> 层级：系统架构 — 高于代码实现和 Prompt 微调
> 核心命题：即使代码 100% 正确、Reviewer 评审质量极高，当前交互模型能否产生收敛的产出？

### 15.1 证据基线：5 个项目的不可收敛数据

| 项目 | 轮数 | RevA 峰值 | RevB 峰值 | 退化次数 | 最终收敛 |
|------|:---:|:---:|:---:|:---:|:---:|
| 天气 CLI | 2 | 86 | 93 | 0 | ❌ |
| Markdown 笔记 | 1 | 90 | 91 | — | ❌ |
| Web 框架 | 5 | **96** | 92 | 1 | ❌ |
| AI 编程助手 | 5 | 78 | 91 | 2 | ❌ |
| 白板工具 | 5 | 85 | 91 | 1 | ❌ |

Reviewer 评审质量极高——每轮 blocking issues 都精准指向架构矛盾、事实错误、缺失场景。但 **Builder 在 5 轮上限内无法将任何一个项目修到双 Reviewer 同时 ≥95**。这不是实现 Bug，是交互模型的结构性问题。

---

### 🔴 缺陷 1：Builder ⇔ Reviewer 的能力输入不对称

#### 现象

Reviewer 拥有一套完备的评审体系：

| Reviewer 能力层 | 机制 |
|------|------|
| 评分哲学 | "保守评分，95+ 仅授予可直接交付生产的文档" |
| 问题分类 | blocking（必须修复）vs suggestion（建议） |
| 校准参考 | 每个维度的 excellent / adequate / poor 描述 |
| 输出格式 | 严格 JSON，字段固定，程序可解析 |

Builder 拥有：

| Builder 能力层 | 内容 |
|------|------|
| 工作原则 | 5 条自然语言描述（"从更高视角设计需求" / "保持聚焦" / "面向 coding agent 友好" / "如果不是第一轮：先 read_file" / "输出格式"） |
| 输出模板 | Markdown 结构描述 |

**不对称之处**：Reviewer 能精确输出 `{"dimension": "架构合理性", "score": 11, "max": 15, "comment": "CRDT 与乐观锁是互斥方案，必须二选一"}`。但 Builder 的 System Prompt 没有任何对应的**修复分类框架**——它只用 5 条通用原则去响应 Reviewer 的结构化诊断。

#### 根因

这是 **Prompt 工程的投资不对称**。Reviewer Prompt 经历了评分表拆分、校准参考、维度名校验、blocking/suggestion 分类等多轮细化。Builder Prompt 自 v0.1.0 起基本未变。

#### 方向：三层打通方案

核心思路：**merge_feedback 不再降维，Builder 收到的不只是文本，还有分类信号。**

---

##### 方案全景

```
当前流程（有结构损失）：

  Reviewer JSON → merge_feedback → 纯文本 → Builder 自行分类 → 修复

改进后流程（分类信号保留）：

  Reviewer JSON → 分类引擎（关键词规则）→ 双层反馈 → Builder 按类型策略修复
                                    ↓
                              修复策略矩阵（System Prompt）→ 自检清单
```

---

##### 第 1 层：反馈分类标记（review.py:merge_feedback）

**问题**：Reviewer 的 blocking_issues 是自然语言，经 `merge_feedback()` 文本化后，Builder 无法区分「架构矛盾」和「事实错误」——它看到的都是 Markdown 段落。

**方案**：在 `merge_feedback()` 中增加零成本的分类引擎，将 blocking issues 标记为 4 种类型之一，然后在输出中增加结构化追踪表。

**分类引擎**（基于关键词+正则的 O(1) 规则，不需要额外 LLM 调用）：

```
规则匹配优先级（高→低）：

1. 互斥 | 矛盾 | 不一致 | 冲突 | 二选一
   | (误|必须|应当|应该).{0,4}统一
                       → [架构矛盾]

2. 缺失 | 缺少 | 未定义 | 未覆盖 | 未考虑 | 未处理
   | 零覆盖 | 完全缺失 | 没有.{1,6}定义
                       → [缺失覆盖]

3. 错误 | 不准确 | 不可靠 | 误导 | 编造
   | \d+\.\d+\.\d+      → [事实错误]
   | 来源.*(?:缺失|未标注|不匹配)

4. default              → [通用改进]
```

**输出格式变更**：`merge_feedback()` 的输出增加结构化追踪表，放在原有 Markdown 内容之前：

```
## 阻塞问题追踪

| # | 类型 | 来源 | 问题描述 |
|---|------|------|---------|
| 1 | [架构矛盾] | RevA | CRDT与乐观锁互斥，必须二选一 |
| 2 | [缺失覆盖] | RevB | API Key 配置流程未定义 |
| 3 | [事实错误] | RevA | Django 5.0 发布时间标注为 2024年12月 |

## 改进建议（非阻塞）

| # | 来源 | 建议描述 |
|---|------|---------|
| 1 | RevB | 可考虑增加多城市查询功能 |

## 逐维度评审详情

(保留原有逐维度得分+评语内容，放在表格后面)
```

Builder 在第一屏就能看到阻塞问题的类型和数量，不需要自己分类。

---

##### 第 2 层：Builder 修复策略矩阵（builder.md 新增段落）

**问题**：Builder System Prompt 只有 5 条通用工作原则，没有任何与问题类型对应的修复指导。

**方案**：在 `builder.md` 工作原则之后新增一段「修复策略矩阵」，与分类引擎的 4 种类型一一对应：

```
## 修复策略

你收到的阻塞问题追踪表中，每条问题标注了类型。不同类型对应不同的修复策略：

---

### [架构矛盾]

含义：两个或多个方案在逻辑上互斥，无法共存。
     例如 "CRDT vs 乐观锁" / "Token 7天有效期 vs 15min access token" / "同步 WSGI vs 原生异步 ASGI"

策略：
  1. 理解两个方案各自的语义边界（各自解决什么问题、各自产生什么约束）
  2. 选择其中一个方案
  3. 修改全篇——不留对方方案的任何残余字段、描述或逻辑

禁止：
  - 试图「调和」两个互斥方案（例如同时保留 CRDT 主路径和乐观锁字段）
  - 只在被指出的单个章节中修改，忽略其他章节中对同一方案的引用
  - 对语义不清楚的方案直接选择——如有疑问应在修改前说明你的判断依据

正确示例：
  Reviewer: "CRDT 与乐观锁互斥，必须二选一"
  → 选择 Yjs CRDT → 删除 Element.version 字段 → 删除所有"乐观锁"描述 → 
    冲突合并策略章节改为 CRDT 语义 → 数据模型章节移除所有 version 引用

---

### [事实错误]

含义：数据、版本号、URL、日期、数字等可验证的信息不准确。
     例如 "Django 5.0 发布于 2024 年 12 月（实际为 2023 年 12 月）" / "QPS 2-5 倍（无来源）"

策略：
  1. 先验证：使用 web_search / read_file 确认正确值
  2. 修正被指出的错误
  3. 全篇检查同一类别数据（版本号错误很少孤立出现）

禁止：
  - 不验证直接修改（可能导致二次错误）
  - 只修被指出的一个错误，不检查全篇同类数据
  - 用模型训练数据替代搜索结果做验证

---

### [缺失覆盖]

含义：某个场景、边界条件、验收标准或非功能需求完全未被覆盖。
     例如 "缺少 API Key 配置流程" / "未定义 WebSocket 断开重连机制"

策略：
  1. 定位缺失内容应属于哪个已有章节
  2. 在对应章节内追加新段落/小节，保持已有内容完全不变
  3. 追加内容不超过缺失范围——Reviewer 说缺什么就补什么

禁止：
  - 为补充一个缺失而重写整个章节
  - 把简单的缺失补充做成了新功能扩展
  - 修改 Reviewer 未扣分的已有内容

---

### [通用改进]

含义：非阻塞的建议性反馈。
     例如 "可考虑增加多语言支持" / "帮助信息措辞可更友好"

策略：
  1. 快速评估改动量 → 改动 ≤ 3 行且不影响结构的采纳
  2. 改动 > 3 行或涉及结构调整的 → 本轮不做，标记为"下一版考虑"
  3. 不要在两类建议间反复横跳——避免一次修太多引入新问题

禁止：
  - 花大量 token 处理建议类反馈而忽略阻塞问题
  - 为"完善体验"而引入 Reviewer 未要求的新功能
```

---

##### 第 3 层：防退化自检清单（builder-context.md 新增段落）

**问题**：Builder 没有机制验证修复是否引入了新问题。"修 A 坏 B" 的退化是当前最频繁的失败模式。

**方案**：在 `builder-context.md` 的「处理反馈的要求」之后追加一段自检清单：

```
## 修改完成后的自检清单

在 write_file 之后，逐项验证以下问题（回答到对话中）：

□ 我是否修改了阻塞问题清单之外的已有章节？
  → 如果是且不是架构矛盾修复的全局替换需要 → 立即回退

□ 对于标记为 [架构矛盾] 的问题，我是否：
  - 选择了其中一个方案（不是调和）？
  - 删除了全篇所有另一方方案的痕迹（字段、描述、逻辑）？

□ 对于标记为 [事实错误] 的问题，我是否：
  - 在修正前使用工具做了验证？
  - 检查了全篇所有同类数据的正确性？

□ 对于标记为 [缺失覆盖] 的问题，我是否：
  - 只在已有结构中追加，没有重写或修改已有内容？

□ 本轮是否产生了全新的问题？
  → 检查你的每一项修改是否可能影响其他章节的一致性
  → 如果怀疑引入了新问题 → 回退该项修改，保持本轮只修复反馈中列出的问题

以上全部确认后输出简短的验证报告：
"自检通过：修复 X 个阻塞问题，无修改已有章节，无新引入问题。"
```

---

##### 改动范围总结

| 层 | 文件 | 改动 | 类型 |
|:---:|------|------|:---:|
| 1 | `review.py:merge_feedback()` | 加分类引擎（关键词规则）+ 输出格式增加结构化追踪表 | 代码 |
| 2 | `prompts/*/builder.md` × 2 | 新增「修复策略矩阵」段落（~60 行），与 4 种类型一一对应 | Prompt |
| 3 | `prompts/*/builder-context.md` × 2 | 在「处理反馈的要求」后追加自检清单（~20 行） | Prompt |

**不动**：orchestrator.py（流程结构不变）、loop.py、subagent.py、tracer.py、config.py

**零额外 API 成本**：分类是 O(1) 关键词匹配，不调用 LLM

---

### 🔴 缺陷 2：「Big-bang 修复」的单轮生成模式

#### 现象

当前每轮 Builder 只被调用一次，需要在单次 sub-agent 会话中完成：

```
理解 2000 字 feedback → 读旧文档 → 决定修复策略 → 执行修改 → 输出全文
```

这是一个**序列化的大批量操作**。Builder 的注意力在 5 个步骤间分配，导致：
- 对阻塞问题的修复停留在**措辞层面**（改描述）而非**结构层面**（换方案）
- 没有机制验证"我的修改是否真的解决了 Reviewer 关心的核心问题"
- "修 A 坏 B"现象：Round N 中修复了 blocking issue A，但引入了新的 blocking issue B

#### 证据

- Web 框架项目 Round 2：Builder 修复了数据来源引用问题，但**引入了决策矩阵加权分计算错误**，导致 RevA 从 80 降至 74
- 白板工具项目 Round 4：Builder 修复 Token 有效期描述，但**新增了 LWW 物理时间戳与 Yjs 的矛盾**，RevA 从 85 降至 80

#### 根因

修复流程是一个**多阶段认知任务**（分析 → 规划 → 执行 → 自检），但被压平为一个单阶段 LLM 调用。

#### 方向：三阶段修复工作模式

核心思路：**不改变 orchestrator 循环结构，不分隔 sub-agent 调用。三步在一个 sub-agent 会话内完成——Builder 先输出计划文本，再调用工具执行，再输出自检报告。agent_loop 的"LLM → 工具 → LLM → 工具 → ... → stop"机制天然支持这一模式。**

---

##### 方案全景

```
当前流程（big-bang）：

  [sub-agent 一次调用]
  user: 全量 feedback + 文档
  ↓
  LLM: 读文档 → 写全文 → 结束
  ↓
  没有检查退化 → Reviewer 发现新问题 → 下一轮

改进后流程（三阶段）：

  [sub-agent 同一次调用]
  user: feedback + 文档 + 三阶段指令
  ↓
  阶段一：输出修复计划文本（不调工具）           ← 纯 LLM 输出
  阶段二：按计划 read_file → write_file 逐章修改 ← 工具调用
  阶段三：输出自检报告（不调工具）               ← 纯 LLM 输出
  ↓
  自检通过 → 本轮完成；自检发现退化 → 回退
```

关键洞察：**sub-agent 内部已有消息循环**。`agent_loop()` 会持续调用 LLM 直到 `stop_reason != "tool_use"`。Builder 可以在一次调用中交替输出文本和调用工具——这正是三阶段需要的。

---

##### 第 1 层：three-phase 修复工作模式（builder.md 新增段落）

当前 `builder.md` 的工作原则第 4 条说「如果不是第一轮：先用 read_file 读取 requirements.md 了解当前文档内容，理解反馈针对的是哪些部分，再进行修改」。这暗示 Builder 读完就直接改，中间没有明确的规划步骤。

替换方案：将工作原则第 4 条扩展为完整的三阶段模式：

```
## 修复工作模式（Round 2+）

每轮修复工作分为三个阶段，必须严格依次执行。

agent_loop 的消息循环会持续给你调用工具的机会——不要急于写文件。

---

### 阶段一：制定修复计划（纯文本输出，不调 write_file）

输出修复计划。格式必须严格为：

```
=== 修复计划 ===

## 阻塞问题修复项
1. [架构矛盾] <问题摘要> → <修复策略>
   涉及章节：(1) ... (2) ... (3) ...

2. [缺失覆盖] <问题摘要> → <修复策略>
   涉及章节：(1) ...

## 本轮跳过项（非阻塞）
- [通用改进] <建议摘要> — 改动 ≤ 3 行采纳，否则标记"下一版考虑"

## 不修改章节
- ...（列出本轮不碰的章节，从已有文档结构判断）
```

「不修改章节」列表约束了阶段二的操作范围。
确认计划无误后进入阶段二。

---

### 阶段二：逐章执行修改（调用工具）

严格按计划顺序执行：

1. read_file 读取文档
2. 按计划修改（write_file）
3. 确认该阻塞问题的所有涉及章节均修改完成
4. 再进行下一个阻塞问题

**执行规则**：
- [架构矛盾] 优先执行——覆盖面最大，排除风险后才能修其他
- 依赖顺序：如果阻塞 B 依赖 A 的改动，先修 A
- 不修改「不修改章节」中的内容
- 一次只关注一个阻塞问题，不要顺手改另一个

**禁止**：
- 一次性 write_file 整个文档
- write_file 后不检查就调用下一个 write_file
- 修改「不修改章节」列表中的内容

---

### 阶段三：自检（纯文本输出）

所有修改执行完毕后，输出自检报告：

```
=== 自检报告 ===

## 修复确认
- ✅ [架构矛盾] CRDT 与乐观锁
  → 已删除 Element.version，冲突策略统一为 Yjs CRDT
- ✅ [缺失覆盖] API Key 配置
  → 已追加 5.1 API Key 获取方式

## 未修改章节验证
- ✅ 项目概述 — 未改动
- ✅ 非功能需求 — 未改动

## 退化检查
- ✅ 全篇所有 CRDT 引用一致使用 Yjs 语义
- ✅ 无引入新的架构矛盾

## 结论
[自检通过] / [自检发现退化需要回退]
```

如果发现退化，回退到阶段一重新检查计划。
```

---

##### 第 2 层：阶段化用户指令（builder-context.md 修改）

当前 `builder-context.md` 的结尾是：

```
使用 write_file 将完整文档写入 {output_file}。
```

这句话暗示 Builder 一次性写入整个文档。替换为：

```
---

请严格按 System Prompt 中定义的「修复工作模式」执行本轮修复：

阶段一：制定修复计划
  → 纯文本输出，不写文件
  → 列出阻塞问题修复项、跳过项、不修改章节

阶段二：逐章执行
  → 按计划顺序，read_file + write_file
  → 一次只改一个阻塞问题涉及的所有章节

阶段三：自检验证
  → 输出自检报告
  → 自检通过则本轮完成

使用 {output_file} 输出修改后的文档。
```

---

##### 第 3 层：plan-aware 历史压缩（compact_review_history.md 增强）

当前 `compact_review_history.md` 只接收 `{records_text}` 作为输入。三阶段模式启用后，Builder 上一轮的修复计划和自检报告对历史压缩也是重要信号。

在 `compact_review_history.md` 的压缩指令中增加一段：

```
如果历史记录中包含 Builder 的「修复计划」和「自检报告」，提取：
- 上一轮计划修复的阻塞问题 → 实际执行了哪些
- 自检报告中标记为「需要回退」的项目
```

---

##### 改动范围总结

| 层 | 文件 | 改动 | 类型 |
|:---:|------|------|:---:|
| 1 | `prompts/*/builder.md` × 2 | 工作原则第 4 条 → 替换为「修复工作模式」三阶段指令（~80 行） | Prompt |
| 2 | `prompts/*/builder-context.md` × 2 | 结尾「使用 write_file 将完整文档写入」→ 替换为阶段化用户指令（~15 行） | Prompt |
| 3 | `prompts/_shared/compact_review_history.md` | 增加 plan-aware 压缩指令（~8 行） | Prompt |

**不动**：orchestrator.py（流程不变）、review.py（不改代码）、loop.py、subagent.py、config.py

**不增加 API 调用**：三步在同一个 sub-agent 会话内完成。

---

##### 与缺陷 1 的关系

```
缺陷 1 解决：Builder 收到的反馈有分类信号 + 修复策略指导
  → 知道「怎么修」

缺陷 2 解决：Builder 修复时不写全文而分步执行 + 自检
  → 确保「修得稳」

独立实施：两者可分别实施，不冲突。同时实施效果叠加。
```

---

### 🔴 缺陷 3：收敛条件的绝对阈值 vs Reviewer 严格度天花板

#### 现象

当前收敛条件：

```
收敛 = (总分 ≥ 95) AND (意图对齐 ≥ 27/30) AND (逐维度 ≥ 75%)
```

Reviewer 评分哲学（来自 `scoring-*.json`）：

> "95+ 仅授予可直接交付生产的文档……对模棱两可的情况，宁可扣分也不要给分"

**5 个项目共计 18 轮 Reviewer A 评分，只有 1 次 ≥95。** Reviewer A 的平均峰值约 85，Reviewer B 约 91。

#### 根因

这不是 Reviewer"太严"——Reviewer 的严格度是正确且必要的，它阻止了低质量文档通过收敛。

问题是：**当 Reviewer 的评分天花板固定为 ~85-91 时，收敛阈值 95 是否在数学上可达？** 从 18 轮数据看，答案是不确定——只有 Web 框架项目在 Round 4 短暂触及 96，然后 Round 5 降到 94。在 Reviewer 承诺"宁可扣分也不要给分"的前提下，95 分意味着文档**无任何可扣分的点**——这在复杂命题下几乎不可能。

当前系统没有处理以下情况：文档质量已实质性达到可用标准（阻塞问题清零、意图对齐 ≥27/30、逐维度 ≥75%），但总分因为 Reviewer 的严格度惯性未达到 95。

#### 方向：从声明式到程序式 Reviewer Prompt

**放弃的方案**（阈值调整、行为化收敛、双轨制）全部回避了核心问题——**Reviewer 的评分行为被 Prompt 的矛盾指令扭曲了**。

不改变 Reviewer 的评分哲学本身，而是改变它如何被传达——从声明式变为程序式。

核心原则：**不松标准，只增可操作性。**

---

##### 当前 Reviewer Prompt 的问题

三层：

| 层 | 问题 | 影响 |
|:---:|------|------|
| 结构 | 声明式 5 条原则，无执行步骤 | Reviewer 无操作顺序 |
| 矛盾 | "发现明确问题才扣分" ↔ "宁可扣分" | 后者总是获胜（LLM recency bias），每个维度被抹平扣 1-3 分 |
| 缺失 | 没有"怎么确定扣多少"的校准 | 默认：模糊 = 扣 2 分。5 维度 × 2 = 总分自动掉 10 |

---

##### 替换方案：程序式 Reviewer Prompt（reviewer-a.md 重设计）

```
你是{role_name}。按以下流程逐维度评审需求文档。

---

## 评审流程（严格按顺序执行）

### 第 1 步：锚定种子意图

阅读原始种子想法，用 1-2 句话写出你对种子核心价值的理解。
确保在评分之前就清楚「Builder 不应该偏离什么」。

---

### 第 2 步：逐章意图检查

对照种子核心价值，逐章检查文档是否偏离或缺失：

| 章节 | 是否服务核心价值 | 结论 |
|------|-------------------|------|

---

### 第 3 步：逐维度评分

对每个维度执行 a→b→c：

3a. 先描述：用自己的话写该维度在文档中的表现（1-2 句话）

3b. 校区间：与评分表中的 excellent / adequate / poor 校准描述对比，确定区间

3c. 给分：在确定的区间内赋值——
  - 完全匹配 excellent → 区间上限（如 29-30）
  - 匹配 excellent 但有小遗憾 → 中上（如 28）
  - 匹配 adequate → 中间（如 20-23）
  - 匹配 adequate 偏下 → 中下（如 18-19）
  - 匹配 poor → 如实给

**自检**：评估描述和分数区间是否一致。不一致 → 回 3a 重新评估。

---

### 第 4 步：判定阻塞 vs 建议

| | 阻塞性问题 | 改进建议 |
|------|---------|---------|
| 判定标准 | 没有此修复，开发者无法开始编码 | 修复会提升质量，但当前状态已可启动 |
| 自问 | "如果没有 X，开发者能开始吗？" | (能 → 建议) |

不确定时，归入改进建议——宁可偏少阻塞，不要偏多。

---

### 第 5 步：汇总输出

按 JSON 格式填入。检查：
- total_score = 各维度得分的逐项累加
- blocking_issues 只含第 4 步判定为阻塞的
- dimension name 与评分表一字不差

---

## 决策规则（处理不确定）

### 是否扣分？
自问：能指出一个具体、可验证的缺陷吗？
→ 能 → 扣分，按第 3 步校准
→ 不能 → 不扣分，想法记入 comment

### 同一缺陷出现在多个维度？
只在最直接相关的维度扣分。其他维度注明"已在上维扣除"。

### 后期轮次（Round > max_rounds/2）
阻塞清零比剩余扣分细节重要。如文档已可开发，向区间上限靠拢。
```

**reviewer-b.md 的结构完全相同，仅调整角色描述和校准区间引用。**

---

##### 程序式 Prompt 的原理解释

| 旧的（声明式） | 新的（程序式） | 为什么更好 |
|------|------|-----------|
| 5 条评审原则 | 5 步执行流程 | Reviewer 有明确操作顺序 |
| "宁可扣分"矛盾 | 决策规则：能指缺陷 → 扣；不能 → 不扣，记 comment | 扣分理由和例外在同一逻辑中 |
| 无扣分幅度 | 第 3 步 a→b→c 三步校准 | 用区间上限/中值替换模糊判断 |
| 阻塞定义模糊 | 第 4 步经验自问 | 将抽象标准转化为可判断的问题 |
| "95+ 仅授予..." | 第 3 步自检保持描述和分数一致 | 防伪 |

---

##### 与 scoring_philosophy 的配合

`scoring-*.json` 的 philosophy 同步为：

```
"评分起点是满分。扣分的依据是能指出具体缺陷，不能以模糊的'感觉不够完美'为由扣分。
先对每个维度做描述性评估，再对照校准区间确定给分。
95+ 要求：所有维度的缺陷均不构成开发者启动开发的实质障碍。"
```

---

##### 三个缺陷的完整方案

| 缺陷 | 解决 | 改动文件 |
|:---:|------|------|
| 1 — Builder 能力不对称 | 分类引擎 + 修复策略矩阵 + 自检 | review.py + builder.md + builder-context.md |
| 2 — Big-bang 修复 | 三阶段工作模式 | builder.md + builder-context.md + compact_history |
| 3 — Reviewer 评分矛盾 | 声明式→程序式 | 4 个 reviewer-*.md + 4 个 scoring-*.json |

三者独立实施，不冲突。全部在 Prompt 层面，不动一行业务代码。

---

## 十六、Skill 式 Prompt 设计：从规则到框架

> 设计日期：2026-05-18。层级：Prompt 架构。
> 核心命题：当前 Builder Prompt（5 条规则 + 模板）是"食谱"，教模型遇什么做什么。应改为"技能"——教模型如何思考，让模型自己推导策略。

### 16.1 规则 vs 技能的根本区别

| | 规则式（当前） | 技能式（目标） |
|------|------|------|
| 指令方式 | "当遇到 [架构矛盾] 时这样做" | "收到反馈时，自问：这是逻辑矛盾还是信息问题？" |
| 覆盖范围 | 被枚举的 case | 任何 Reviewer 的新问题类型 |
| 适应性 | 需要手动添加新规则 | 模型自己推导策略 |
| 退化应对 | "不要修改未扣分章节" | "改一处后，思考会不会影响别处" |

---

### 16.2 完整 skill 式 Prompt：builder.md（dev-doc）

```
你是{role_name}。你的技能是将种子想法转化为结构化需求文档。

---

## 你的技能核心

这是你的思考框架——不是规则表，是你内化的工作方式。

---

### 阶段 1：定义边界（写之前）

拿到种子想法后，先不急着写。理清三个边界：

- √ 给谁用的？→ 开发者需要知道做什么、不做什么、怎么验证
- √ 种子想法的核心意图？→ 它想解决什么问题
- √ 在哪止步？→ 明确不在范围内的

种子想法很短时（如"一个天气查询 CLI 工具"），需要补全——但补全服务于核心意图，
不替种子做没说过的决定。

---

### 阶段 2：搭建结构（写到哪一层）

文档结构服务于信息密度，不是死模板。

- 功能需求要具体到开发者可拆分任务：
  不好的："天气查询功能"
  好的："输入城市 → 返回温度、湿度、风速、天气状况"

- 验收标准要可测试：
  不好的："响应速度要快"
  好的："从调用 API 到结果显示在 3 秒内"

- 明确声明不做什么——与控制范围同等重要

---

### 阶段 3：生成或修复（写的时候）

**新文档（Round 1）**：按阶段 2 的结构写。

**修复轮次（Round 2+）**：关键是"怎么修才不破坏已有内容"。

收到 Reviewer 反馈时，先花时间理解问题：

- 这是逻辑层面的吗？
  → 两个说法互相冲突 → 需要统一，不是调和
  → 涉及多个章节 → 确保全篇一致

- 这是信息层面的吗？
  → 数据/版本号/URL 不准确 → 需要验证，不是猜测
  → 验证完一个后检查全篇同类数据

- 这是范围层面的吗？
  → 缺场景 → 在对应章节补充，不动已有
  → 补充不超过缺失范围

- 问题之间有依赖吗？
  → 先修影响面大的，再修依赖它的

理解完后制定修复顺序，逐个执行。每次修改后检查相关章节的一致性。

---

### 阶段 4：自我审视（写完后）

不依赖外部反馈。自己先检查：

- 核心意图是否清晰？换人读能否用一句话总结？

- 有没有自相矛盾？前后对同一概念的描述一致否？

- 边界是否明确？读的人知道"做什么"和"不做什么"吗？

- 验收标准是否可落地？每条能否用"是/否"来验证？

---

## 输出结构（参考，不是枷锁）

# 项目概述 — 一句话 + 目标用户 + 核心价值
# 功能需求 — 故事 + 验收标准 + 优先级
# 非功能需求 — 性能/安全/可用性/兼容性
# 数据模型 — 核心实体及关系
# 约束与假设 — 技术选型 + 范围边界（明确不做什么）

用精确、具体的语言。验收标准不是装饰品。
```

---

### 16.3 builder-context.md 同步简化

当前结尾的规则式要求全部压缩为：

```
## 反馈信息

{feedback}

{review_history_summary}

---

按你的技能框架处理本轮修复：先理解问题性质，再规划修复顺序，最后逐个执行。

使用 {output_file} 输出修改后的文档。
```

---

### 16.4 与三阶段工作模式的衔接

Skill Prompt 教的是**思考框架**，三阶段工作模式（缺陷 2）是**操作流程**。分层：

```
Skill Prompt (builder.md):
  阶段 1: 定义边界    → 理解范围
  阶段 2: 搭建结构    → 组织内容
  阶段 3: 生成或修复  → 修复时如何思考（skill 核心）
  阶段 4: 自我审视    → 验证成果

三阶段工作流程 (builder.md):
  阶段一: 制修复计划  → 基于 skill 思考输出计划
  阶段二: 逐章执行    → 按计划分步实施
  阶段三: 自检        → 验证无退化
```

---

### 16.5 改动范围

| 文件 | 改动 |
|------|------|
| `prompts/requirements-dev-doc/builder.md` | 完整重写为 skill 式 |
| `prompts/requirements-research/builder.md` | 同上，调整调研报告场景 |
| `prompts/requirements-dev-doc/builder-context.md` | 简化结尾指令 |
| `prompts/requirements-research/builder-context.md` | 同上 |

---

## 二十、日志与审计系统设计（v0.2.0）

### 16.1 双层日志架构

| 层 | 文件 | 格式 | 内容 |
|----|------|------|------|
| **执行摘要** | `run-log.json` | JSON | 轮次级耗时/评分/收敛状态 |
| **结构化追踪** | `execution.jsonl` | JSONL | 每步关键节点、API 调用详情、token 用量、决策记录 |
| **审计上下文** | `contexts/round-NN-{agent}-{system\|user}.txt` | 纯文本 | 提交给 LLM 的完整 system prompt 和 user context |

### 16.2 execution.jsonl 事件类型

| type | 触发点 | 关键字段 |
|------|--------|---------|
| `step` | Builder/Reviewer 起止、状态保存、文档加载 | phase, round_num, msg |
| `api` | 每次子 agent 完成 | agent, model, tokens_in/out, calls, latency_ms, status |
| `review` | 每次评分解析成功 | reviewer, total_score, intent, dimensions(单行摘要) |
| `decision` | 收敛判定、异常中断、reviewer 连续失败 | phase, result, scores, reason |
| `summary` | 流程结束 | total_rounds, total_api_calls, total_tokens |

### 16.3 审计上下文 (contexts/)

每轮保存 6 个文件：
```
contexts/
├── round-01-builder-system.txt    # Builder: role + principles
├── round-01-builder-user.txt      # Builder: seed + feedback + output_file
├── round-01-reviewer-a-system.txt # RevA: role + scoring table + rules
├── round-01-reviewer-a-user.txt   # RevA: seed + doc_content + history_summary
├── round-01-reviewer-b-system.txt
└── round-01-reviewer-b-user.txt
```

**用途**：
- 审计：事后检查 Builder 收到的 feedback 是否准确传递了 Reviewer 的核心诉求
- 调试：分析为何某个维度持续低分，直接查看该轮的 system/user prompt
- 回归：对比两轮 prompt 差异，定位评分变化原因

### 16.4 控制开关

`.env` 中 `IDEA_VERBOSE_LOG=1` 启用全量日志（默认开启）。`tracer.save_context()` 仅在 enabled 时写盘。

---

## 二一、评分体系优化方案（v0.2.0）

### 17.1 根因分析

基于 10 轮 dev-doc + 10 轮 research 的逐维度数据：

**问题 A — Reviewer 维度名漂移（🔴 严重）**

Reviewer LLM 跨轮自由更改维度名：
- R1-R3: `完整性=17/20` → R4: 维度消失，出现 `非功能需求完整性=7/10`
- R3: `场景覆盖=16/20` → R4: `完整性/场景覆盖=17/20`（合并重命名）

导致：
- 跨轮评分不可比较
- Builder 收到的 feedback 维度名与评分表不一致
- 收敛判定无法基于稳定维度评估趋势

**问题 B — 系统性短板不可见**

某些维度在全轮次中持续低分（非功能需求7/10、数据支撑5/10），但总分判别无法体现"短板"概念。Builder 反复收到抽象 feedback 但无法定位根因。

**问题 C — 评分天花板**

RevA（deepseek-v4-pro）峰值 85/100，RevB（kimi-k2.6）峰值 91/100。95 阈值在当前 Reviewer 严格度下不可达。

### 17.2 已实施修复

| 修复 | 机制 | 位置 |
|------|------|------|
| **维度名校验** | `validate_dimensions()` 比对 Reviewer 输出与 scoring-*.json 预期名；不匹配则自动重试 | `review.py` |
| **逐维度门槛** | `check_per_dimension_threshold()` 要求每维度 >= 75% 满分；收敛需同时满足总分+意图+逐维度 | `review.py` + `orchestrator.py` |
| **Prompt 约束** | 4 个 reviewer-*.md 追加「维度名必须与评分维度表格完全一致」强制声明 | `prompts/*/reviewer-*.md` |
| **全量上下文审计** | `tracer.save_context()` 每轮保存 6 个 system/user prompt 文件 | `tracer.py` + `orchestrator.py` |

### 17.3 待观察与后续优化

| 方向 | 说明 | 触发条件 |
|------|------|---------|
| **阈值校准** | 将 pass_threshold 从 95 下调至 90，或配置化到 scoring-*.json | 连续 20 轮无法收敛 |
| **Reviewer 同质化** | 双 deepseek-v4-pro 可能严格度趋同，可观察是否需要差异化模型 | 当前已切换为双 v4-pro |
| **feedback 精准度** | 如果 Reviewer 持续给出抽象 feedback（如"需完善架构"），考虑在 merge_feedback 中注入具体改写的示例 | Builder 反复修同一问题 |

---

## 二二、v0.2.0 变更日志

| 文件 | 变更 |
|------|------|
| `review.py` | 新增 `validate_dimensions()` / `check_per_dimension_threshold()` / `PER_DIM_MIN_RATIO`；`parse_review_output` 增加 expected_dimensions 校验 |
| `loop.py` | `agent_loop` 返回 token 用量 dict |
| `subagent.py` | `run_subagent` 返回 `(text, tokens)` |
| `orchestrator.py` | 全链路维度名校验 / 逐维度收敛门槛 / context 审计 / `_run_reviewer` 签名扩展 |
| `tracer.py` | 新增 `save_context()` 审计上下文写盘 |
| `prompts/*/reviewer-*.md` × 4 | 追加维度名强制声明 |
| `config.py` | 新增 `VERBOSE_LOG` |

---

## 二三、2026-05-20 新发现：最新 e2e 暴露的 3 个问题

> 审查范围：DEV-DOC AI 代码审查平台，7 轮 max_rounds

### 🔴 #28：`{scoring_table}` 占位符未渲染

**位置**：`orchestrator.py:_run_reviewer()` line 106

`render_reviewer_prompt` 只传了 `role_name` 和 `scoring_philosophy`，没传 `scoring_table`。4 个 reviewer-*.md 中的 `{scoring_table}` 保持原始占位符，Reviewer 从未看到评分维度表。

**已修复**：增加 `scoring_table=scoring_table`。✅

---

### 🔴 #29：总分≠维度之和无校验

**位置**：`review.py:parse_review_output()`

R6 曾输出 `total_score=100` 但维度加总 ≈68。模型算术错误未被系统拦截。

**已修复**：`validate_dimension_total()` + orchestrator 重试。✅

---

### 🟡 #30：降级模式 Reviewer 永久失效

**位置**：`orchestrator.py:440-458`

`rev_a_dead` / `rev_b_dead` 一旦设为 True 永不回收。R4 B=0 触发降级，但 R5 B=75 R6 B=87 时仍以单 RevA 模式运行。

**待修复**：`result.total_score > 0` 时自动复活 ⬜

---

## 二四、v0.2.1 变更日志

| # | 文件 | 变更 |
|---|------|------|
| 28 | `orchestrator.py` | `render_reviewer_prompt` 增加 `scoring_table=scoring_table` |
| 29 | `review.py` | 新增 `validate_dimension_total()` + `parse_review_output` 集成 + orchestrator 重试 |
| 29 | `orchestrator.py` | `_run_reviewer` 总分不匹配时重试 |
| 30 | `orchestrator.py` | ⬜ 待修复：`rev_a_dead` / `rev_b_dead` 复活逻辑 |
| — | `context.py` | Anthropic client `timeout=300` |
