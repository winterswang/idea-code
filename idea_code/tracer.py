"""执行追踪器：结构化 JSONL 日志 + 人类可读执行报告。

输出文件:
  projects/{slug}/execution.jsonl  — 机器可读 JSONL
  projects/{slug}/execution.txt   — 人类可读报告
控制开关: IDEA_VERBOSE_LOG=1
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


def _fmt_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    m, s = divmod(ms / 1000, 60)
    return f"{int(m)}m{int(s)}s"


def _fmt_tokens(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


class ExecutionTracer:
    """结构化执行日志，JSONL + 人类可读双输出。"""

    def __init__(self, project_dir: Path, enabled: bool = True):
        self.path = project_dir / "execution.jsonl"
        self.report_path = project_dir / "execution.txt"
        self.enabled = enabled
        self._events: list[dict] = []
        self._total_tokens_in = 0
        self._total_tokens_out = 0
        self._total_calls = 0
        self._total_rounds = 0
        self._start_time = time.time()
        self._package = ""
        self._seed = ""
        self._max_rounds = 0
        self._resume_round = 1

    def _write(self, entry: dict):
        if not self.enabled:
            return
        entry["ts"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self._events.append(entry)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def step(self, phase: str, round_num: int = 0, **meta):
        entry = {"type": "step", "phase": phase}
        if round_num:
            entry["round"] = round_num
        entry.update(meta)
        # 捕获会话元数据
        if phase == "session_start":
            self._package = meta.get("package", "")
            self._seed = meta.get("msg", "").replace("包=", "").split("种子=", 1)[-1].split(" max_rounds")[0] if "种子=" in str(meta.get("msg", "")) else ""
            self._max_rounds = meta.get("max_rounds", 0)
            self._resume_round = meta.get("resume_round", 1)
        self._write(entry)

    def decision(self, phase: str, result: str, round_num: int = 0, **meta):
        entry = {"type": "decision", "phase": phase, "result": result}
        if round_num:
            entry["round"] = round_num
        entry.update(meta)
        self._write(entry)

    def api_call(self, agent: str, model: str, round_num: int,
                 tokens_in: int, tokens_out: int, calls: int,
                 latency_ms: int, status: str = "ok", **meta):
        self._total_tokens_in += tokens_in
        self._total_tokens_out += tokens_out
        self._total_calls += calls
        entry = {
            "type": "api", "round": round_num,
            "agent": agent, "model": model,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "calls": calls, "latency_ms": latency_ms, "status": status,
        }
        entry.update(meta)
        self._write(entry)

    def review(self, reviewer: str, name: str, round_num: int,
               total_score: int, intent: int | None, dimensions: str, **meta):
        entry = {
            "type": "review", "round": round_num,
            "reviewer": reviewer, "name": name,
            "total_score": total_score, "intent": intent,
            "dimensions": dimensions,
        }
        entry.update(meta)
        self._write(entry)

    def set_rounds(self, n: int):
        self._total_rounds = n

    def summary(self) -> dict:
        return {
            "total_rounds": self._total_rounds,
            "total_calls": self._total_calls,
            "total_tokens_in": self._total_tokens_in,
            "total_tokens_out": self._total_tokens_out,
        }

    def close(self):
        self._write({
            "type": "summary",
            "total_rounds": self._total_rounds,
            "total_api_calls": self._total_calls,
            "total_tokens_in": self._total_tokens_in,
            "total_tokens_out": self._total_tokens_out,
        })
        self._render_report()

    def save_context(self, round_num: int, agent: str, system: str, user: str):
        if not self.enabled:
            return
        ctx_dir = self.path.parent / "contexts"
        ctx_dir.mkdir(exist_ok=True)
        prefix = f"round-{round_num:02d}-{agent}"
        (ctx_dir / f"{prefix}-system.txt").write_text(system, encoding="utf-8")
        (ctx_dir / f"{prefix}-user.txt").write_text(user, encoding="utf-8")
        self._write({"type": "step", "phase": "context_saved", "round": round_num,
                     "agent": agent, "system_chars": len(system), "user_chars": len(user)})

    # ── 人类可读报告 ────────────────────────────
    def _render_report(self):
        if not self.enabled or not self._events:
            return
        elapsed = int(time.time() - self._start_time)
        lines = []
        w = 64

        lines.append("═" * w)
        lines.append("  IDEA-CODE 执行报告")
        if self._package:
            lines.append(f"  包: {self._package}")
        if self._seed:
            seed_short = self._seed[:72] + ("…" if len(self._seed) > 72 else "")
            lines.append(f"  种子: {seed_short}")
        lines.append(f"  最大轮数: {self._max_rounds}  ·  从第 {self._resume_round} 轮开始")
        lines.append("═" * w)
        lines.append("")

        # 按轮分组
        rounds: dict[int, list[dict]] = {}
        for ev in self._events:
            r = ev.get("round", 0)
            if r:
                rounds.setdefault(r, []).append(ev)

        for rn in sorted(rounds):
            rlines = self._render_round(rn, rounds[rn], w)
            lines.extend(rlines)
            lines.append("")

        # 汇总
        lines.append("─" * 28 + "  Summary  " + "─" * 26)
        lines.append(f"  总轮数: {self._total_rounds}    总 API 调用: {self._total_calls}")
        lines.append(f"  Token 入: {_fmt_tokens(self._total_tokens_in):>6s}  "
                     f"Token 出: {_fmt_tokens(self._total_tokens_out):>6s}")
        lines.append(f"  总耗时: {_fmt_ms(elapsed * 1000)}")
        converged = any(
            ev.get("type") == "decision" and ev.get("result") == "converged"
            for ev in self._events
        )
        lines.append(f"  收敛: {'YES' if converged else 'NO'}")
        lines.append("═" * w)

        self.report_path.write_text("\n".join(lines), encoding="utf-8")

    def _render_round(self, rn: int, events: list[dict], w: int) -> list[str]:
        lines = []
        lines.append(f"── Round {rn}/{self._max_rounds} " + "─" * (w - 14))

        apis = [e for e in events if e["type"] == "api"]
        reviews = {e["reviewer"]: e for e in events if e["type"] == "review"}
        dim_retries = [e for e in events if e.get("phase") == "dim_validation_retry"]
        dim_oks = [e for e in events if e.get("phase") == "dim_validation_ok"]
        contexts = [e for e in events if e.get("phase") == "context_saved"]
        docs = [e for e in events if e.get("phase") == "doc_loaded"]
        decisions = [e for e in events if e["type"] == "decision"]

        # 上下文
        for ctx in sorted(contexts, key=lambda x: x.get("ts", "")):
            ag = ctx.get("agent", "?")
            sc = ctx.get("system_chars", 0)
            uc = ctx.get("user_chars", 0)
            lines.append(f"  [上下文: {ag}] system={sc}B user={uc}B")

        # Builder
        for api in apis:
            if api["agent"] == "builder":
                m = api.get("model", "?")
                ti = api.get("tokens_in", 0)
                to = api.get("tokens_out", 0)
                c = api.get("calls", 0)
                lat = api.get("latency_ms", 0)
                st = api.get("status", "ok")
                err = api.get("error", "")
                icon = "+" if st == "ok" else "!"
                lines.append(f"\n  [Builder] {m}")
                lines.append(f"    IO: {c}calls {_fmt_tokens(ti)}→{_fmt_tokens(to)} tokens {_fmt_ms(lat)} [{icon}]")
                if err:
                    lines.append(f"    ERR: {err}")

        for doc in docs:
            lines.append(f"  [文档] {doc.get('doc_chars', 0)} chars")

        # Reviewers
        for which in ["a", "b"]:
            api = next((a for a in apis if a["agent"] == f"reviewer_{which}"), None)
            rev = reviews.get(which, {})
            if not api and not rev:
                continue
            m = api.get("model", "?") if api else "?"
            n = rev.get("name", f"Rev{which.upper()}")
            ti = api.get("tokens_in", 0) if api else 0
            to = api.get("tokens_out", 0) if api else 0
            c = api.get("calls", 0) if api else 0
            lat = api.get("latency_ms", 0) if api else 0
            st = api.get("status", "ok") if api else "?"
            icon = "+" if st == "ok" else "!"
            rt = [r for r in dim_retries if r.get("reviewer") == which]
            ok = [o for o in dim_oks if o.get("reviewer") == which]

            lines.append(f"\n  [Reviewer {which.upper()} · {n}] {m}")
            lines.append(f"    IO: {c}calls {_fmt_tokens(ti)}→{_fmt_tokens(to)} tokens {_fmt_ms(lat)} [{icon}]")

            for r in rt:
                lines.append(f"    DIM: 第{r.get('attempt','?')}次维名校验不匹配 → 重试")
            for o in ok:
                nok = o.get("names_ok", True)
                cok = o.get("count_ok", True)
                if not nok or not cok:
                    lines.append(f"    DIM: 最终接受 (names={nok} count={cok})")

            if rev:
                sc = rev.get("total_score", 0)
                it = rev.get("intent")
                dims = rev.get("dimensions", "")
                passed = sc >= 95
                pfx = "PASS" if passed else "FAIL"
                lines.append(f"    SCORE: {sc}/100 [{pfx}] intent={it}/30")
                if dims:
                    for dp in dims.split(" | "):
                        lines.append(f"      · {dp.strip()}")

        # 判定
        for dec in decisions:
            p = dec.get("phase", "")
            r = dec.get("result", "")
            if p == "convergence":
                if r == "converged":
                    lines.append(f"\n  >> CONVERGED")
                elif r == "total_fail":
                    lines.append(f"\n  >> NOT CONVERGED: 总分未达标 ({dec.get('scores', '?')})")
                elif r == "intent_fail":
                    lines.append(f"\n  >> NOT CONVERGED: 意图对齐不足")
                elif r == "per_dim_fail":
                    lines.append(f"\n  >> NOT CONVERGED: 逐维度未达标")
                    if dec.get("detail"):
                        lines.append(f"     {dec['detail']}")
                elif r == "max_rounds":
                    lines.append(f"\n  >> MAX ROUNDS: 达到上限 {self._max_rounds}，流程结束")
            elif p == "reviewer_failure":
                if r == "abort":
                    lines.append(f"\n  >> ABORT: Reviewer 连续失败")

        lines.append("")
        return lines
