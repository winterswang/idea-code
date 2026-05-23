# idea-code 待办清单

> 更新：2026-05-23

---

## ✅ 已完成

- [x] P0：文档拆分 BUG_LOG / DESIGN / TODO
- [x] P1a：pass_threshold 连线到收敛判定
- [x] P2a：merge_feedback 过滤 dead
- [x] P2b：停滞检测
- [x] 降级收敛标记
- [x] 死亡信号区分（error vs score=0）
- [x] 近收敛检测（A>=88 B>=88 提示增加轮次）
- [x] **三大架构缺陷修复（v0.3.0-v0.3.2）**：Builder-Reviewer 能力输入不对称 → 阻塞分类引擎 + builder.md 修复策略矩阵；Big-bang 单轮修复 → 三阶段工作模式；Reviewer 声明式评分 → 5 步程序化流程
- [x] **Builder Round2+ read_file 指引**（Bug #31）：builder-context.md 区分首轮/后续轮，后续轮携带文件路径指引
- [x] **输出模板 7 章规范化**（Bug #32）：角色/接口/异常/架构/MVP/术语 结构化约束

## ⬜ 待处理

### P0 — 结构问题（影响 Builder/Reviewer 输出质量）

- [ ] **merge_feedback 阻塞问题重复输出**：`review.py:265-272` 以表格输出"阻塞问题追踪"，`review.py:315-321` 又以列表输出"阻塞性问题（必须修复）"，Builder 收到相同信息两次。应删除旧列表格式（第 315-321 行）。
- [ ] **orchestrator.py:319 参数重复**：`tracer.step("output_missing", round_num=round_num, round=round_num)` 往 JSONL 写入冗余的 `round` 字段，应移除多余的 `round=` 参数。
- ~~**Reviewer A/B 评审逻辑对称重复**：虽然 ~70 行镜像，但保留独立块为后续差异化（不同错误处理/追踪/输出格式）预留空间，不改。~~

### P1 — 维护效率（代码重复 + 测试安全）

- [ ] **Builder / Reviewer 历史读取重复代码**：`orchestrator.py:112-128`（`_run_reviewer` 内）与 `:252-273`（`run` 内 Builder）是相同的 reviews_dir → 文件列表 → `compact_review_history` 流程，应提取为共享函数。
- [ ] **删除冗余的 `_e2e_*.py` 脚本**：`_e2e_devdoc.py`、`_e2e_research.py`、`_e2e_complex.py` 功能完全被 `tests/test_e2e.py` 覆盖，应删除。
- [ ] **`test_e2e.py` 缺 pytest skip 保护**：函数名以 `test_` 开头，pytest 自动收集并在常规测试中执行真实 LLM 调用（消耗 API Key 和费用），需加 `@pytest.mark.skipif(not os.getenv(...))` 保护。

### P2 — 测试覆盖 + 配置修复

- [ ] **`tracer.py`(279行) 缺少单元测试**：执行日志模块逻辑复杂（JSONL 写入、报告渲染、轮次分组），当前完全无测试。
- [ ] **`compact.py`(121行) 缺少单元测试**：上下文压缩（token 估算、micro/auto 压缩、脱敏）无覆盖。
- [ ] **`__init__.py` 版本号与 `project_review.md` 不一致**：`__init__.py` 写 `0.1.0`，`project_review.md` 写 `v0.3.2`，需统一。
- [ ] **`compact.py` transcript 路径依赖 WORKDIR**：`TRANSCRIPT_DIR = Path(WORKDIR) / ".transcripts"`，WORKDIR 是运行时的 cwd（可能是根目录），transcript 文件落在非预期位置，应改为项目目录。

## 远期

- [ ] 收敛阈值配置化
- [ ] Reviewer 模型差异化评估
- [ ] E2E：max_rounds=10 跑 dev-doc + research 验证收敛

## 已确认但不修复

- **`.env` API Key 明文存储**：文件未进 git 追踪，本地泄露风险由开发者自负。
- **`logger.py` / `tracer.py` 功能重叠**：`RunLogger`(轮次评分摘要) 和 `ExecutionTracer`(结构化全链路审计) 各有侧重，可共存。
- **`idea_code/prompts/` vs `prompts/` 同名**：前者是 Python 代码目录，后者是 Prompt 包数据目录，设计选择，无需改名。
- **`context.py` 内部 `import os`**：函数内 import 不影响功能，低优先级。
- **`check_per_dimension_threshold` 同时处理 ScoringDim/dict**：dict 分支是死代码（实际只传 ScoringDim），不影响功能。
