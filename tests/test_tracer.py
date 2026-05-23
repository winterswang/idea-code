"""tracer.py 单元测试。"""

import json, tempfile
from pathlib import Path
from idea_code.tracer import ExecutionTracer, _fmt_ms, _fmt_tokens


class TestUtil:
    def test_fmt_ms(self):
        assert _fmt_ms(500) == "500ms"
        assert _fmt_ms(5000) == "5.0s"
        assert _fmt_ms(125000) == "2m5s"

    def test_fmt_tokens(self):
        assert _fmt_tokens(500) == "500"
        assert _fmt_tokens(1500) == "1.5k"


class TestExecutionTracer:
    def test_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = ExecutionTracer(Path(tmp), enabled=False)
            t.step("test"); t.close()
            assert not (Path(tmp) / "execution.jsonl").exists()

    def test_step_and_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = ExecutionTracer(Path(tmp))
            t.step("builder_start", round_num=1)
            t.decision("convergence", "total_fail", round_num=1, scores="A=90")
            t.close()
            entries = [json.loads(l) for l in (Path(tmp) / "execution.jsonl").read_text().strip().split("\n")]
            assert any(e["type"] == "step" and e["phase"] == "builder_start" for e in entries)
            assert any(e["type"] == "decision" and e["result"] == "total_fail" for e in entries)

    def test_api_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = ExecutionTracer(Path(tmp))
            t.api_call("b", "m", 1, 100, 200, 1, 1000)
            t.api_call("r", "m2", 1, 300, 400, 2, 2000)
            s = t.summary()
            assert s["total_tokens_in"] == 400
            assert s["total_tokens_out"] == 600

    def test_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = ExecutionTracer(Path(tmp))
            t.review("a", "RevA", 1, 95, 28, "意图 28/30 | 架构 20/20")
            t.close()
            entries = [json.loads(l) for l in (Path(tmp) / "execution.jsonl").read_text().strip().split("\n")]
            r = next(e for e in entries if e["type"] == "review")
            assert r["total_score"] == 95 and r["intent"] == 28

    def test_save_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = ExecutionTracer(Path(tmp))
            t.save_context(1, "builder", "sys", "usr")
            d = Path(tmp) / "contexts"
            assert (d / "round-01-builder-system.txt").read_text() == "sys"
            assert (d / "round-01-builder-user.txt").read_text() == "usr"

    def test_report_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = ExecutionTracer(Path(tmp))
            t.step("session_start", package="p", max_rounds=2, resume_round=1, msg="包=p 种子=s max_rounds=2")
            t.api_call("builder", "m", 1, 100, 200, 1, 1000)
            t.review("a", "RevA", 1, 95, 28, "意图 28/30")
            t.decision("convergence", "converged", round_num=1, scores="A=95")
            t.set_rounds(1); t.close()
            report = (Path(tmp) / "execution.txt").read_text()
            assert "IDEA-CODE" in report
            assert "CONVERGED" in report or "YES" in report
