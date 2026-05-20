# idea-code 待办清单

> 更新：2026-05-20。从 DESIGN.md 提取的可执行项。

---

## P1 — 架构硬化

- [ ] **连线 pass_threshold**：orchestrator 收敛判定从 scoring-*.json 读取 `pass_threshold` 替代硬编码 95（DESIGN §1.5）
- [ ] **提取 ReviewerHealth**：dead/revive/连续失败逻辑独立为类（DESIGN §1.1 §1.3）

## P2 — 质量与可靠性

- [ ] **merge_feedback 过滤 dead**：score=0 的 Reviewer 不参与合并（DESIGN §1.2）
- [ ] **停滞检测**：3 轮总分方差 < 2 时告警（DESIGN §1.4）
- [ ] **降级收敛标记**：单 Rev 收敛输出 ⚠️ 降级提示（DESIGN §1.1）
- [ ] **死亡信号区分**：error（API 故障）vs score=0（文档差），仅前者触发降级（DESIGN §1.3）

## 远期

- [ ] 收敛阈值配置化：不同 Prompt 包不同 pass_threshold
- [ ] Reviewer 模型差异化评估：同质化 vs 多视角
