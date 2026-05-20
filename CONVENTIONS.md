# idea-code 开发约定

> 每次代码变更后，AI 助手应自动更新对应的项目文档。

## 文档更新映射

| 变更类型 | 更新文件 |
|---------|---------|
| 修复 Bug / 代码缺陷 | `BUG_LOG.md` 追加条目 |
| 架构 / 设计 / Prompt 改动 | `DESIGN.md` 更新对应章节 |
| 新增待办任务 | `TODO.md` 添加 checkbox |
| 版本发布（打 tag） | `project_review.md` 版本历史表 |

## Git 规范

- 每个逻辑变更一个 commit
- commit message 格式：`类别: 简短描述`
- 每个版本打 `vX.Y.Z` tag

## 审查纪律

- 每次 `edit_file` 后必须验证结果
- Prompt 改动（.md 文件）必须在 next E2E run 中验证效果
