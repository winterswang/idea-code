"""评分解析单元测试。"""

from idea_code.review import (
    parse_review_output,
    extract_dimension_score,
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

    def test_parse_null_suggestions(self):
        """LLM 输出 'suggestions': null 不 crash"""
        text = '{"reviewer": "技术视角", "total_score": 95, "passed": true, "dimensions": [], "blocking_issues": null, "suggestions": null, "feedback_for_builder": ""}'
        result = parse_review_output(text)
        assert result.blocking_issues == []
        assert result.suggestions == []

    def test_parse_null_dimensions(self):
        """LLM 输出 'dimensions': null 不 crash"""
        text = '{"reviewer": "产品视角", "total_score": 80, "passed": false, "dimensions": null, "blocking_issues": ["缺失场景"], "suggestions": [], "feedback_for_builder": ""}'
        result = parse_review_output(text)
        assert result.dimensions == []
        assert len(result.blocking_issues) == 1


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
