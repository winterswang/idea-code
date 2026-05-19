"""状态持久化测试。"""

import json
import tempfile
from pathlib import Path

from idea_code.state import save_state, load_state, save_review_record


class TestStatePersistence:
    def test_save_and_load(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.state.PROJECTS_DIR", tmp)
            monkeypatch.setattr("idea_code.config.PROJECTS_DIR", tmp)

            save_state(
                slug="test-project",
                seed="测试种子",
                package_id="requirements-dev-doc",
                round_num=3,
                scores=[{"round": 1, "reviewer_a_score": 90, "reviewer_b_score": 92}],
            )

            loaded = load_state("test-project")
            assert loaded is not None
            assert loaded["project"] == "test-project"
            assert loaded["seed"] == "测试种子"
            assert loaded["prompt_package"] == "requirements-dev-doc"
            assert loaded["round"] == 3
            assert len(loaded["scores"]) == 1

    def test_load_nonexistent(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.state.PROJECTS_DIR", tmp)
            assert load_state("不存在") is None

    def test_save_review_record(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.state.PROJECTS_DIR", tmp)
            monkeypatch.setattr("idea_code.config.PROJECTS_DIR", tmp)

            save_review_record(
                "test-project", 1,
                {"reviewer": "技术视角", "total_score": 95},
                {"reviewer": "产品视角", "total_score": 96},
            )

            record_path = Path(tmp) / "test-project" / "reviews" / "round-01.json"
            assert record_path.exists()
            record = json.loads(record_path.read_text())
            assert record["round"] == 1
            assert record["reviewer_a"]["total_score"] == 95
