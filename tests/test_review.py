"""评分解析单元测试。"""

from idea_code.review import (
    parse_review_output,
    converge_check,
    extract_dimension_score,
    INTENT_DIM_NAME,
    merge_feedback,
    ReviewResult,
)


class TestParseReviewOutput:
    def test_parse_json_block(self):
        text = """```json
{
  "reviewer": "技术视角",
  "total_score": 95,
  "passed": true,
  "dimensions": [
    {"name": "意图对齐", "score": 28, "max": 30, "comment": "良好"}
  ],
  "blocking_issues": [],
  "suggestions": ["优化格式"],
  "feedback_for_builder": "整体不错"
}
```"""
        result = parse_review_output(text)
        assert result.reviewer == "技术视角"
        assert result.total_score == 95
        assert result.passed is True
        assert len(result.dimensions) == 1
        assert result.dimensions[0]["name"] == "意图对齐"

    def test_parse_raw_json(self):
        text = '{"reviewer": "产品视角", "total_score": 88, "passed": false, "dimensions": [], "blocking_issues": ["缺失场景"], "suggestions": [], "feedback_for_builder": "需改进"}'
        result = parse_review_output(text)
        assert result.reviewer == "产品视角"
        assert result.total_score == 88
        assert result.passed is False
        assert "缺失场景" in result.blocking_issues

    def test_parse_invalid_json(self):
        result = parse_review_output("这不是 JSON")
        assert result.reviewer == ""
        assert result.total_score == 0


class TestConvergeCheck:
    def test_both_pass(self):
        assert converge_check(95, 96)["passed"] is True
        assert converge_check(100, 95)["passed"] is True

    def test_one_fails(self):
        assert converge_check(95, 94)["passed"] is False
        assert converge_check(90, 100)["passed"] is False

    def test_both_fail(self):
        assert converge_check(80, 85)["passed"] is False

    def test_custom_threshold(self):
        assert converge_check(80, 85, threshold=80)["passed"] is True
        assert converge_check(79, 85, threshold=80)["passed"] is False

    def test_intent_alignment_gate(self):
        # 总分通过但意图对齐不达标 → 不通过
        decision = converge_check(97, 96, intent_a=25, intent_b=26)
        assert decision["passed"] is False
        assert decision["total"] is True
        assert decision["intent"] is False

    def test_intent_alignment_pass(self):
        # 总分和意图对齐都通过
        decision = converge_check(97, 96, intent_a=28, intent_b=29)
        assert decision["passed"] is True
        assert decision["total"] is True
        assert decision["intent"] is True

    def test_intent_one_missing(self):
        # 只有一个 Reviewers 有意图对齐分（向后兼容）
        decision = converge_check(97, 96, intent_a=28)
        assert decision["passed"] is True
        assert decision["intent"] is True

    def test_intent_boundary_exact(self):
        # 精确 27/30 分（90% 门槛）
        decision = converge_check(97, 96, intent_a=27, intent_b=27)
        assert decision["passed"] is True
        assert decision["intent"] is True

    def test_total_fails_but_intent_passes(self):
        # 总分不通过，即使意图对齐好也不通过
        decision = converge_check(94, 94, intent_a=30, intent_b=30)
        assert decision["passed"] is False
        assert decision["total"] is False
        assert decision["intent"] is True


class TestMergeFeedback:
    def test_merge_both_with_issues(self):
        ra = ReviewResult(
            reviewer="技术视角",
            total_score=90,
            blocking_issues=["缺少性能需求"],
            suggestions=["补充异常处理"],
            feedback_for_builder="需完善非功能需求",
        )
        rb = ReviewResult(
            reviewer="产品视角",
            total_score=92,
            blocking_issues=["核心场景缺失"],
            suggestions=["优化优先级排序"],
            feedback_for_builder="补充用户场景",
        )
        merged = merge_feedback(ra, rb)
        assert "阻塞性问题" in merged
        assert "缺少性能需求" in merged
        assert "核心场景缺失" in merged
        assert "改进建议" in merged
        assert "上一轮评分" in merged
        assert "技术视角: 90/100" in merged
        assert "产品视角: 92/100" in merged

    def test_merge_no_issues(self):
        ra = ReviewResult(reviewer="技术视角", total_score=98)
        rb = ReviewResult(reviewer="产品视角", total_score=97)
        merged = merge_feedback(ra, rb)
        assert "阻塞性问题" not in merged
