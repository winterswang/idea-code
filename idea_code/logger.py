"""结构化日志：记录每轮耗时、评分、token 用量。"""

import time
import json
from pathlib import Path


class RunLogger:
    """一次 run() 调用的完整日志。"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.start_time = time.time()
        self.rounds: list[dict] = []
        self._round_start = 0.0

    def round_start(self, round_num: int):
        self._round_start = time.time()

    def round_end(self, round_num: int, score_a: int, score_b: int,
                  converged: bool, tokens: dict | None = None):
        elapsed = time.time() - self._round_start
        entry = {
            "round": round_num,
            "elapsed_s": round(elapsed, 1),
            "score_a": score_a,
            "score_b": score_b,
            "converged": converged,
        }
        if tokens:
            entry["tokens"] = tokens
        self.rounds.append(entry)

    def summary(self) -> dict:
        total_elapsed = time.time() - self.start_time
        latest = self.rounds[-1] if self.rounds else {}
        return {
            "total_rounds": len(self.rounds),
            "total_elapsed_s": round(total_elapsed, 1),
            "final_score_a": latest.get("score_a", "N/A"),
            "final_score_b": latest.get("score_b", "N/A"),
            "converged": any(r["converged"] for r in self.rounds),
            "rounds": [{
                "r": r["round"],
                "t": r["elapsed_s"],
                "a": r["score_a"],
                "b": r["score_b"],
                "ok": r["converged"],
            } for r in self.rounds],
        }

    def save(self):
        path = self.project_dir / "run-log.json"
        try:
            path.write_text(json.dumps(self.summary(), indent=2, ensure_ascii=False),
                            encoding="utf-8")
        except (OSError, IOError) as e:
            print(f"[logger] 写入日志失败: {e}")
            return None
        return path
