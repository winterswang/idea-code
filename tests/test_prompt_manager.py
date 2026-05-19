"""Prompt 管理器测试 — PackageConfig。"""

import json
import tempfile
from pathlib import Path

from idea_code.prompts.manager import PromptRegistry


class TestPromptRegistry:
    def test_scan_registers_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg_dir = root / "test-pkg"
            pkg_dir.mkdir()

            config = {
                "id": "test-pkg",
                "label": "测试包",
                "output_file": "test.md",
                "description": "测试用",
                "reviewer_count": 2,
                "builder": {
                    "role": "测试 Builder",
                    "model": "IDEA",
                    "prompt_file": "builder.md",
                    "context_file": "builder-context.md",
                },
                "reviewer_a": {
                    "name": "Rev A",
                    "model": "REV_A",
                    "prompt_file": "reviewer-a.md",
                    "context_file": "reviewer-a-context.md",
                    "scoring_file": "scoring-a.json",
                },
                "reviewer_b": {
                    "name": "Rev B",
                    "model": "REV_B",
                    "prompt_file": "reviewer-b.md",
                    "context_file": "reviewer-b-context.md",
                    "scoring_file": "scoring-b.json",
                },
            }
            (pkg_dir / "config.json").write_text(json.dumps(config))
            (pkg_dir / "builder.md").write_text("Builder: {role_name}")
            (pkg_dir / "builder-context.md").write_text("seed: {seed}")
            (pkg_dir / "reviewer-a.md").write_text("RevA: {role_name}")
            (pkg_dir / "reviewer-a-context.md").write_text("scoring: {scoring_table}")
            (pkg_dir / "reviewer-b.md").write_text("RevB: {role_name}")
            (pkg_dir / "reviewer-b-context.md").write_text("scoring: {scoring_table}")
            (pkg_dir / "scoring-a.json").write_text(json.dumps({
                "reviewer": "Rev A",
                "dimensions": [{"dimension": "test", "max_score": 30, "description": "test"}],
            }))
            (pkg_dir / "scoring-b.json").write_text(json.dumps({
                "reviewer": "Rev B",
                "dimensions": [{"dimension": "test2", "max_score": 20, "description": "test2"}],
            }))

            registry = PromptRegistry(root)
            assert "test-pkg" in registry.list_packages()

            pkg = registry.get("test-pkg")
            assert pkg is not None
            assert pkg.label == "测试包"
            assert len(pkg.reviewer_a.scoring) == 1
            assert pkg.reviewer_a.scoring[0].dimension == "test"

    def test_render_builder_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg_dir = root / "render-test"
            pkg_dir.mkdir()
            config = {
                "builder": {"role": "架构师", "prompt_file": "builder.md", "context_file": "builder-context.md"},
            }
            (pkg_dir / "config.json").write_text(json.dumps(config))
            (pkg_dir / "builder.md").write_text("你是{role_name}")
            (pkg_dir / "builder-context.md").write_text("种子: {seed}")

            registry = PromptRegistry(root)
            pkg = registry.get("render-test")

            system = pkg.render_builder_prompt(role_name="架构师")
            assert system == "你是架构师"

            user = pkg.render_builder_context(seed="hello")
            assert "hello" in user

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = PromptRegistry(Path(tmp))
            assert registry.list_packages() == []

    def test_get_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = PromptRegistry(Path(tmp))
            assert registry.get("nonexistent") is None
