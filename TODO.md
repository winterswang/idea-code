# idea-code 待办清单

> 更新：2026-05-20。

---

## ✅ 已完成

- [x] P0：文档拆分 BUG_LOG / DESIGN / TODO
- [x] P1a：pass_threshold 从 scoring-*.json 连线到收敛判定
- [x] P2a：merge_feedback 过滤 score=0 的 dead Reviewer
- [x] P2b：停滞检测（3轮无改善告警）

## ⬜ 待处理

- [ ] P1b：提取 ReviewerHealth 类（dead/revive 逻辑独立）
- [ ] 降级收敛标记：单 Rev 收敛时输出 ⚠️ 提示
- [ ] 死亡信号区分：error（API 故障）vs score=0（文档差），仅前者触发降级

## 远期

- [ ] 收敛阈值配置化：不同 Prompt 包不同 pass_threshold（已支持，待验证）
- [ ] Reviewer 模型差异化评估
