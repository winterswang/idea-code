"""状态持久化：轻量级，不存完整 messages。

state.json 只存评分摘要 + 文档元数据。
reviews/ 存每轮的完整结构化评分 JSON。
"""

import json
import time
from pathlib import Path

from .config import PROJECTS_DIR


def save_state(
    slug: str,
    seed: str,
    package_id: str,
    round_num: int,
    scores: list[dict] | None = None,
    max_rounds: int | None = None,
    feedback: str = "",
) -> Path:
    """Save session state (lightweight)."""
    project_dir = Path(PROJECTS_DIR) / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "project": slug,
        "seed": seed,
        "prompt_package": package_id,
        "version": 2,
        "round": round_num,
        "max_rounds": max_rounds,
        "updated_at": time.time(),
        "scores": scores or [],
        "feedback": feedback,
    }

    state_path = project_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return state_path


def load_state(slug: str) -> dict | None:
    """Load project state."""
    state_path = Path(PROJECTS_DIR) / slug / "state.json"
    if not state_path.exists():
        return None
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_review_record(
    slug: str,
    round_num: int,
    review_a: dict,
    review_b: dict,
) -> None:
    """Save single round review record."""
    reviews_dir = Path(PROJECTS_DIR) / slug / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "round": round_num,
        "timestamp": time.time(),
        "reviewer_a": review_a,
        "reviewer_b": review_b,
    }

    record_path = reviews_dir / f"round-{round_num:02d}.json"
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
