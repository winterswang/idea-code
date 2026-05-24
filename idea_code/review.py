"""评分解析：从 Reviewer 输出的 JSON 中提取评分，判定收敛。

Reviewer 被要求输出严格的 JSON，本模块负责解析、验证、判定。
"""

import json as _json
import re
from dataclasses import dataclass, field


@dataclass
class ReviewResult:
    """一次评审的解析结果。"""
    reviewer: str = ""
    total_score: int = 0
    passed: bool = False
    dimensions: list[dict] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    feedback_for_builder: str = ""
    raw_text: str = ""
    error: str = ""
    # 校验标记
    dimension_names_valid: bool = True
    dimension_count_match: bool = True
    dimension_total_match: bool = True


def _extract_json(text: str) -> str | None:
    """从文本中提取 JSON，优先代码块，fallback 反向搜索。"""
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        return json_match.group(1)

    brace_end = text.rfind("}")
    if brace_end != -1:
        brace_start = text.rfind("{", 0, brace_end)
        if brace_start != -1:
            return text[brace_start:brace_end + 1]
    return None


def validate_dimensions(dimensions: list[dict], expected: list[str]) -> tuple[bool, bool]:
    """校验 Reviewer 输出的维度名是否与预期一致。

    Args:
        dimensions: Reviewer 输出的 dimensions 列表
        expected: 预期的维度名列表（来自 scoring-*.json）

    Returns:
        (names_valid, count_match):
          - names_valid: 所有维度名都在预期列表中
          - count_match: 维度数量与预期一致
    """
    if not expected or not dimensions:
        return True, True  # 无预期则通过

    actual_names = [d.get("name", "") for d in dimensions if isinstance(d, dict)]
    count_match = len(actual_names) == len(expected)

    names_valid = True
    for name in actual_names:
        # 精确匹配或包含匹配（容忍轻微措辞差异如 "完整性/场景覆盖"）
        if name in expected:
            continue
        # 检查是否至少包含某个预期维度名作为子串
        matched = False
        for exp in expected:
            if exp in name or name in exp:
                matched = True
                break
        if not matched:
            names_valid = False
            break

    return names_valid, count_match


def validate_dimension_total(dimensions: list[dict], total_score: int) -> bool:
    """验证 total_score 是否等于维度得分之和。"""
    if not dimensions:
        return True  # 无维度数据则跳过
    actual_sum = sum(int(d.get("score", 0)) for d in dimensions if isinstance(d, dict))
    return actual_sum == total_score


def parse_review_output(text: str, expected_dimensions: list[str] | None = None) -> ReviewResult:
    """从 Reviewer 的文本输出中解析评分 JSON。

    处理两种情况：
    1. 文本中包含 JSON 块（```json ... ```）
    2. Fallback：从末尾反向搜索最后一个独立 { ... } 对象

    如果传入 expected_dimensions，会校验维度名是否匹配。
    """
    result = ReviewResult(raw_text=text)

    json_str = _extract_json(text)
    if json_str is None:
        return result

    try:
        raw = _json.loads(json_str)
    except _json.JSONDecodeError:
        return result

    result.reviewer = raw.get("reviewer", "")
    result.total_score = int(raw.get("total_score", 0))
    result.passed = bool(raw.get("passed", False))
    # or [] 兜底: LLM 可能输出 "dimensions": null, 导致 get(..., []) 返回 None
    result.dimensions = raw.get("dimensions") or []
    result.blocking_issues = raw.get("blocking_issues") or []
    result.suggestions = raw.get("suggestions") or []
    result.feedback_for_builder = raw.get("feedback_for_builder", "")

    # 校验维度名
    if expected_dimensions:
        result.dimension_names_valid, result.dimension_count_match = \
            validate_dimensions(result.dimensions, expected_dimensions)

    # 校验总分是否等于维度之和
    result.dimension_total_match = validate_dimension_total(result.dimensions, result.total_score)

    return result


# 意图对齐维度的固定名称（所有评分包统一）
INTENT_DIM_NAME = "意图对齐"
INTENT_MAX_SCORE = 30
INTENT_MIN_RATIO = 0.90  # 意图对齐必须达到满分的 90%（即 27/30）
PER_DIM_MIN_RATIO = 0.75  # 每个维度必须达到满分的 75%


def extract_dimension_score(dimensions: list[dict], dim_name: str) -> int | None:
    """从 dimensions 列表中提取指定维度的得分。"""
    for dim in dimensions:
        if isinstance(dim, dict) and dim.get("name") == dim_name:
            return int(dim.get("score", 0))
    return None


def check_per_dimension_threshold(
    dimensions: list[dict], scoring: list, threshold_ratio: float = PER_DIM_MIN_RATIO
) -> tuple[bool, list[str]]:
    """检查每个维度是否达标。

    scoring 为 ScoringDim 列表，用于获取每个维度的满分值。
    返回 (all_passed, failures)。
    """
    if not scoring:
        return True, []

    # 构建 name → max_score 映射
    score_map = {}
    for s in scoring:
        if hasattr(s, "dimension"):
            score_map[s.dimension] = s.max_score
        elif isinstance(s, dict):
            score_map[s.get("dimension", "")] = s.get("max_score", 0)

    failures = []
    for dim in dimensions:
        if not isinstance(dim, dict):
            continue
        name = dim.get("name", "")
        score = dim.get("score", 0)
        # 尝试匹配维度名（包含匹配）
        matched_max = None
        for dim_name, max_s in score_map.items():
            if dim_name in name or name in dim_name:
                matched_max = max_s
                break
        if matched_max is None:
            continue  # 无法匹配则跳过
        if score < matched_max * threshold_ratio:
            failures.append(f"{name}: {score}/{matched_max} (需>= {int(matched_max * threshold_ratio)})")

    return len(failures) == 0, failures


def converge_check(
    score_a: int,
    score_b: int,
    threshold: int = 95,
    intent_a: int | None = None,
    intent_b: int | None = None,
    intent_min: int | None = None,
    dims_a: list[dict] | None = None,
    dims_b: list[dict] | None = None,
    scoring_a: list | None = None,
    scoring_b: list | None = None,
) -> dict:
    """判定双 Reviewer 是否收敛。

    三层检查：
    1. 总分 >= threshold（必要条件）
    2. 意图对齐 >= intent_min（独立门槛）
    3. 每个维度 >= 75% 满分（逐维度门槛，可选）

    Returns:
        {"passed": bool, "total": bool, "intent": bool | None,
         "per_dim": bool | None, "detail": str}
    """
    if intent_min is None:
        intent_min = int(INTENT_MAX_SCORE * INTENT_MIN_RATIO)

    total_ok = score_a >= threshold and score_b >= threshold
    intent_ok = None

    if intent_a is not None and intent_b is not None:
        intent_ok = intent_a >= intent_min and intent_b >= intent_min
    elif intent_a is not None:
        intent_ok = intent_a >= intent_min
    elif intent_b is not None:
        intent_ok = intent_b >= intent_min

    # 逐维度检查
    per_dim_ok = None
    per_dim_detail = ""
    if dims_a is not None and dims_b is not None:
        ok_a, fail_a = check_per_dimension_threshold(dims_a, scoring_a or [])
        ok_b, fail_b = check_per_dimension_threshold(dims_b, scoring_b or [])
        per_dim_ok = ok_a and ok_b
        if not per_dim_ok:
            parts = []
            if fail_a:
                parts.append(f"RevA: {'; '.join(fail_a)}")
            if fail_b:
                parts.append(f"RevB: {'; '.join(fail_b)}")
            per_dim_detail = " | ".join(parts)

    passed = total_ok and (intent_ok if intent_ok is not None else True)
    if per_dim_ok is not None:
        passed = passed and per_dim_ok

    # 构建人类可读的详情
    parts = []
    if not total_ok:
        parts.append(f"总分未达标 (A={score_a}, B={score_b}, 需>= {threshold})")
    if intent_ok is False:
        parts.append(f"意图对齐未达标 (需>= {intent_min}/{INTENT_MAX_SCORE})")
    if per_dim_ok is False:
        parts.append(f"逐维度未达标: {per_dim_detail}")

    return {
        "passed": passed,
        "total": total_ok,
        "intent": intent_ok,
        "per_dim": per_dim_ok,
        "per_dim_detail": per_dim_detail,
        "detail": "; ".join(parts) if parts else "全部通过",
    }


def merge_feedback(review_a: ReviewResult, review_b: ReviewResult) -> str:
    """合并两个 Reviewer 的反馈，生成给 Builder 的综合输入。

    包含：阻塞问题分类追踪、修复优先级排序、逐维度评审结果、改进建议。
    """
    parts = []

    # ── 阻塞问题分类追踪（O(1)规则引擎） ──
    all_blocks_with_src = \
        [(review_a.reviewer, b) for b in review_a.blocking_issues] + \
        [(review_b.reviewer, b) for b in review_b.blocking_issues]
    if all_blocks_with_src:
        parts.append("## 阻塞问题追踪\n")
        parts.append("| # | 类型 | 来源 | 问题描述 |")
        parts.append("|---|------|------|---------|")
        for i, (src, issue) in enumerate(all_blocks_with_src, 1):
            cat = _classify_issue(issue)
            parts.append(f"| {i} | [{cat}] | {src} | {issue} |")
        parts.append("")

    # ── 修复优先级（新增） ──
    parts.append("## 修复优先级（按影响排序，请从上到下处理）\n")
    # 1. 阻塞性问题（最高优先级）
    if all_blocks_with_src:
        parts.append("### 🔴 阻塞性问题（必须修复，否则文档不可交付）")
        for src, b in all_blocks_with_src:
            parts.append(f"- [{src}] {b}")
    # 2. 低分维度（得分率 < 70%）
    low_dims = []
    for result, label in [(review_a, review_a.reviewer), (review_b, review_b.reviewer)]:
        for dim in result.dimensions:
            if not isinstance(dim, dict):
                continue
            score = dim.get("score", 0)
            max_s = dim.get("max", 1) or 1
            if score / max_s < 0.7:
                low_dims.append(f"[{label}] {dim.get('name','?')}: {score}/{max_s}")
    if low_dims:
        parts.append("\n### 🟡 需提升维度（得分率 < 70%）")
        for ld in low_dims:
            parts.append(f"- {ld}")
        parts.append("")

    # ── 逐维度评审结果 ──
    parts.append("## 逐维度评审结果\n")
    for reviewer, result in [(review_a.reviewer, review_a), (review_b.reviewer, review_b)]:
        if not reviewer or not result.dimensions:
            continue
        parts.append(f"### {reviewer}（{result.total_score}/100）\n")
        for dim in result.dimensions:
            if not isinstance(dim, dict):
                continue
            name = dim.get("name", "?")
            score = dim.get("score", "?")
            max_s = dim.get("max", "?")
            comment = dim.get("comment", "")
            parts.append(f"- **{name}**: {score}/{max_s}")
            if comment:
                parts.append(f"  > {comment}")
        parts.append("")

    if review_a.suggestions or review_b.suggestions:
        parts.append("## 改进建议")
        for sug in review_a.suggestions:
            parts.append(f"- [{review_a.reviewer}] {sug}")
        for sug in review_b.suggestions:
            parts.append(f"- [{review_b.reviewer}] {sug}")
        parts.append("")

    parts.append("## 上一轮评分")
    parts.append(f"- {review_a.reviewer}: {review_a.total_score}/100")
    parts.append(f"- {review_b.reviewer}: {review_b.total_score}/100")

    if review_a.feedback_for_builder:
        parts.append(f"\n{review_a.reviewer}反馈: {review_a.feedback_for_builder}")
    if review_b.feedback_for_builder:
        parts.append(f"{review_b.reviewer}反馈: {review_b.feedback_for_builder}")

    return "\n".join(parts)


# ── 阻塞问题分类引擎（O(1) 关键词规则，零 LLM 调用） ──
_ARCH_PATTERNS = ["互斥", "矛盾", "不一致", "冲突", "二选一"]
_MISSING_PATTERNS = ["缺失", "缺少", "未定义", "未覆盖", "未考虑", "未处理", "零覆盖", "完全缺失"]
_FACT_PATTERNS = ["错误", "不准确", "不可靠", "编造"]


def _classify_issue(issue: str) -> str:
    """将阻塞问题分类为 架构矛盾 | 缺失覆盖 | 事实错误 | 通用改进。"""
    if any(p in issue for p in _FACT_PATTERNS) or "来源缺失" in issue or "来源未标注" in issue:
        return "事实错误"
    if any(p in issue for p in _ARCH_PATTERNS):
        return "架构矛盾"
    if any(p in issue for p in _MISSING_PATTERNS):
        return "缺失覆盖"
    return "通用改进"


def scoring_table_to_markdown(scoring: list, philosophy: str = "") -> str:
    """Render scoring dimensions as markdown, with philosophy and calibration."""
    lines = []
    if philosophy:
        lines.append(f"**评分哲学**: {philosophy}\n")

    lines.append("| 维度 | 分值 | 评审内容 |")
    lines.append("|------|------|----------|")
    for dim in scoring:
        desc = dim.description
        lines.append(f"| {dim.dimension} | **{dim.max_score}** | {desc} |")

    has_cal = any(hasattr(dim, 'calibration') and dim.calibration for dim in scoring)
    if has_cal:
        lines.append("\n## 评分校准参考")
        lines.append("| 维度 | 高分 (excellent) | 中等 (adequate) | 低分 (poor) |")
        lines.append("|------|-------------------|------------------|--------------|")
        for dim in scoring:
            cal = getattr(dim, 'calibration', {})
            if cal:
                lines.append(
                    f"| {dim.dimension} | {cal.get('excellent', '')} | "
                    f"{cal.get('adequate', '')} | {cal.get('poor', '')} |"
                )

    return "\n".join(lines)


def compact_review_history(records: list[dict], ctx) -> str:
    """LLM 压缩 N 轮评审历史为结构化摘要。

    records: [{"round": 1, "reviewer_a": {...}, "reviewer_b": {...}}, ...]
    ctx: AgentContext (model/client)
    """
    if not records:
        return ""

    records_text = _json.dumps(records, indent=2, ensure_ascii=False)
    prompt = f"""你是评审信息压缩器。将以下 N 轮双 Reviewer 评审记录压缩为"历史评审摘要"。

压缩要求（上限 1000 字）：
1. 逐维度得分趋势：每个维度列出各轮得分变化（↑提升 ↓下降 →持平）
2. 持续性问题：在多轮中反复出现的阻塞问题，首次出现轮次
3. 已解决问题：已修复的历史阻塞问题
4. 需关注维度：始终低于 80% 得分率的维度

评审记录：
{records_text}"""

    try:
        response = ctx.client.messages.create(
            model=ctx.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        summary = next(
            (block.text for block in response.content if hasattr(block, "text")),
            "",
        )
        return summary.strip()
    except Exception:
        return "(历史摘要生成失败)"
