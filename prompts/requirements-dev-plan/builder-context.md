## 需求文档

{seed}

## 反馈信息

{feedback}

{review_history_summary}

---

请基于上述需求文档生成执行计划。

**如果是第一轮**：
- 严格按照「第一轮工作模式」执行：阶段一 架构分析 → 阶段二 Task 分解 → 阶段三 自检
- 阶段一必须先 read_file 读取 requirements.md
- 阶段二输出到 {output_file}
- 阶段三必须 read_file 回读自检

**如果是后续轮次**：
- 按修复工作模式执行：阶段一 计划 → 阶段二 逐 Task 修改 → 阶段三 自检
- 确保每个 Task 满足: 接口签名完整、验收可测、20-60 min 粒度、依赖声明确