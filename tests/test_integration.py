"""集成测试：Prompt 包加载 + 渲染 + CLI（不调 LLM）。"""

import json
import tempfile
from pathlib import Path

import pytest

from idea_code.prompts.manager import get_registry, PromptRegistry
from idea_code.review import scoring_table_to_markdown


class TestPromptPackageIntegration:
    """验证 prompts/ 目录下真实的两个包能正确加载和渲染。"""

    def test_dev_doc_package_loads(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-dev-doc")
        assert pkg is not None
        assert pkg.id == "requirements-dev-doc"
        assert pkg.label == "研发需求文档生成"
        assert pkg.output_file == "requirements.md"
        assert pkg.reviewer_count == 2
        assert pkg.builder.role == "资深产品架构师"
        assert pkg.reviewer_a is not None
        assert pkg.reviewer_a.name == "技术视角"
        assert len(pkg.reviewer_a.scoring) == 5
        assert pkg.reviewer_b is not None
        assert pkg.reviewer_b.name == "产品视角"

    def test_dev_doc_renders_builder_prompt(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-dev-doc")
        system = pkg.render_builder_prompt(role_name="测试角色")
        assert "测试角色" in system
        assert "write_file" in system
        assert "requirements.md" in system

    def test_dev_doc_renders_builder_context(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-dev-doc")
        user = pkg.render_builder_context(seed="测试种子", feedback="测试反馈")
        assert "测试种子" in user
        assert "测试反馈" in user
        assert "阻塞性问题" in user

    def test_dev_doc_renders_reviewer_prompts(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-dev-doc")

        sys_a = pkg.render_reviewer_prompt("a", role_name="技术视角")
        assert "技术视角" in sys_a
        assert "技术角度" in sys_a or "架构" in sys_a

        sys_b = pkg.render_reviewer_prompt("b", role_name="产品视角")
        assert "产品视角" in sys_b
        assert "产品" in sys_b

    def test_dev_doc_renders_reviewer_contexts(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-dev-doc")

        ctx_a = pkg.render_reviewer_context("a", seed="种子", doc_content="文档",
                                              scoring_table="| 维度 | 分 |",
                                              round_num="1", max_rounds="10")
        assert "种子" in ctx_a
        assert "文档" in ctx_a
        assert "1" in ctx_a

        ctx_b = pkg.render_reviewer_context("b", seed="种子", doc_content="文档",
                                              scoring_table="| 维度 | 分 |",
                                              round_num="1", max_rounds="10")
        assert "种子" in ctx_b

    def test_research_package_loads(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-research")
        assert pkg is not None
        assert pkg.output_file == "report.md"
        assert pkg.builder.role == "资深行业分析师"
        assert pkg.reviewer_a.name == "严谨性视角"
        assert pkg.reviewer_b.name == "价值视角"

    def test_list_packages(self):
        registry = PromptRegistry("prompts")
        pkgs = registry.list_packages()
        assert "requirements-dev-doc" in pkgs
        assert "requirements-research" in pkgs

    def test_list_packages_detail(self):
        registry = PromptRegistry("prompts")
        detail = registry.list_packages_detail()
        assert len(detail) == 2
        assert detail[0]["reviewer_count"] == 2


class TestScoringTableRendering:
    """验证评分维度能正确渲染为 markdown 表格。"""

    def test_scoring_table_format(self):
        from idea_code.prompts.manager import ScoringDim
        dims = [
            ScoringDim("意图对齐", 30, "是否偏离"),
            ScoringDim("技术可行性", 20, "是否可实现"),
        ]
        table = scoring_table_to_markdown(dims)
        assert "| 维度 | 分值 | 评审内容 |" in table
        assert "| 意图对齐 | **30** | 是否偏离 |" in table

    def test_scoring_table_from_config(self):
        registry = PromptRegistry("prompts")
        pkg = registry.get("requirements-dev-doc")
        table = scoring_table_to_markdown(pkg.reviewer_a.scoring)
        assert "意图对齐" in table
        assert "**30**" in table
        assert "**15**" in table  # 实现复杂度


class TestCLIArgParsing:
    """验证 CLI 参数解析逻辑。"""

    def test_list_prompts_flag(self, capsys):
        import sys
        from idea_code.main import main

        sys.argv = ["idea-code", "--list-prompts", "--prompts-dir", "prompts"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "requirements-dev-doc" in captured.out
        assert "requirements-research" in captured.out

    def test_missing_args_error(self, capsys):
        import sys
        sys.argv = ["idea-code"]
        try:
            from idea_code.main import main
            main()
        except SystemExit as e:
            assert e.code != 0

    def test_unknown_package_error(self, capsys):
        import sys
        sys.argv = ["idea-code", "test", "--prompt", "nonexistent"]
        try:
            from idea_code.main import main
            main()
        except SystemExit as e:
            assert e.code == 1
