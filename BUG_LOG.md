# idea-code 历史 Bug 归档

> 全部 30 个问题已修复。详细讨论见 `project_review.md`

## 设计层面 (#1-#5)
- #1 收敛不检查意图对齐 → 总分≥95 + 意图≥27/30 双门槛
- #2 Reviewer 无对齐校验 → `_reviewer_health_check()` 告警
- #3 反馈截断 → `merge_feedback()` 逐维度评分卡
- #4 Reviewer 盲审 → `compact_review_history()` + 占位符
- #5 reviewer_count=0 绕过 → 活跃 Reviewer 动态判定

## 实现层面 (#6-#13)
- #6 重试判定错误 → `result.reviewer!=""`
- #7 JSON 提取脆弱 → 优先代码块 + 反向 brace
- #8 passed 字段未用 → 合并到 health_check
- #9 round_num 间接计算 → 直接用循环变量
- #10 resume 无提示 → 边界检查
- #11 单 Rev 故障 → 连续失败 ≥2 中断
- #12 token 低估 → CJK 1.5x 加权
- #13 Builder 不写文件 → Round 1 直接报错

## 安全层面 (#14-#16)
- #14 shell=True → shlex.split() + shell=False
- #15 symlink 攻击 → 逐组件检测
- #16 API Key 泄露 → 正则脱敏

## 数据流 (#17-#22)
- #17 orchestrator 覆盖 → 代码完整
- #18 logger 未完成 → round_start/end 已调用
- #19 scoring_philosophy 断裂 → 占位符已修复
- #20 logger.save() 无异常 → try/except
- #21 validate_env 未闭环 → api_key 空值校验
- #22 history_summary 丢弃 → 4 个 context 文件追加

## 收敛根因 (#23-#27)
- #23 compact_review_history 精度不足 → 独立文件 + 阻塞追踪优先
- #24 merge_feedback 过载 → 优先级排序
- #25 Builder 缺修复策略 → 合并到缺陷2
- #26 web_search 不可靠 → 退化提示
- #27 max_rounds 不匹配 → 文档注明

## 最新 (#28-#30)
- #28 scoring_table 未渲染 → render_reviewer_prompt 增加参数
- #29 总分≠维度之和 → validate_dimension_total()
- #30 降级永久失效 → 评分恢复自动复活
