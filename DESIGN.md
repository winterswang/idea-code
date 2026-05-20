# idea-code 系统设计文档

> 从 `project_review.md` 提取的架构级发现和方案。

---

## 一、Orchestrator 流程级问题（§13）

### 1.1 质量门槛随 Reviewer 故障降低
双 Reviewer 限 A≥95 AND B≥95。B 故障降级为单 Rev → 仅需存活 Rev ≥95。建议：降级收敛标记为「⚠️ 降级收敛」。

### 1.2 merge_feedback 不考虑 dead 状态
`result_b.total_score=0` 仍被合并进 feedback，Builder 收到噪声。应过滤 score=0 的 Reviewer。

### 1.3 Reviewer 死亡判定信号混淆
`total_score==0` 既可能是 JSON 解析失败（API 问题）也可能是评分 0 分（文档极差）。应区分 `error` 和正常 0 分，仅 error 触发降级。

### 1.4 评分停滞检测缺失
现有退出条件只有 max_rounds 和收敛。3 轮总分方差 <2 时继续迭代无法收敛。建议告警让用户介入。

### 1.5 pass_threshold 死亡配置
`scoring-*.json` 声明 `pass_threshold: 95`，orchestrator 硬编码 95，字段从未被读取。

---

## 二、核心架构缺陷（§15）

### 缺陷 1：Builder-Reviewer 能力输入不对称
Reviewer 有完备评分体系（5 维 + 校准 + 分类）。Builder 只有 5 条通用原则。

**已修复** ✅：阻塞问题分类引擎 + builder.md 修复策略矩阵。

### 缺陷 2：Big-bang 单轮修复
Builder 一次性重写全文，无计划/执行/自检分步。

**已修复** ✅：三阶段工作模式（计划 → 逐章执行 → 自检）。

### 缺陷 3：Reviewer 评分声明式 → 程序式
5 条声明式原则被 LLM 的 recency bias 扭曲。

**已修复** ✅：5 步程序化流程替代 5 条原则。

---

## 三、日志与审计系统（§20）

双层架构：
- `execution.jsonl` — JSONL 机读（step/api/review/decision/summary）
- `execution.txt` — 人类可读报告
- `contexts/` — 完整原始 prompt 审计

控制开关：`IDEA_VERBOSE_LOG=1`

---

## 四、评分体系（§21）

- 维度名校验：`validate_dimensions()` 自动重试
- 逐维度门槛：每维度 ≥75% 满分
- 总分校验：`validate_dimension_total()` 防止算术错误
- pass_threshold：配置化（目标状态）
