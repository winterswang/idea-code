---
name: idea-code-docs
description: After every idea-code development change, code review, or E2E run, update the project documentation files automatically.
---

# idea-code 文档自动更新

每次代码变更、审查或 E2E 验证后，自动更新项目文档。不等待用户提醒。

## 文档矩阵

| 文件 | 何时更新 |
|------|---------|
| `BUG_LOG.md` | 修 Bug 后追加条目 |
| `DESIGN.md` | 架构/设计/Prompt 改动后更新章节 |
| `TODO.md` | 新任务加 checkbox，完成任务打勾 |
| `project_review.md` | 打 version tag 后追加版本行 |

## 更新工作流

### 代码变更后
1. 判断类型：Bug → BUG_LOG，设计 → DESIGN
2. 读取目标文件，追加/更新条目
3. commit 后检查是否需要更新文档

### Code Review 后
1. 新问题 → BUG_LOG（标状态：✅ 已修复 / ⚠️ 待修复 / ⬜ 远期）
2. 架构问题 → DESIGN
3. 紧急项 → TODO

### E2E 后
1. 读 `projects/{slug}/execution.txt`
2. 分析收敛、趋势、异常
3. 新问题 → BUG_LOG
4. 更新 project_review.md 版本历史

## BUG_LOG 条目

```markdown
- #N <问题简述> → <修复方案>
```

## Git 规范
- commit: `类别: 描述`（fix/feat/docs/improve）
- 版本打 `vX.Y.Z` tag

## 验证
- [ ] BUG_LOG 已更新（如有新 Bug）
- [ ] DESIGN 已更新（如有设计变更）
- [ ] TODO 已同步
- [ ] tag 已打（如有可交付版本）
