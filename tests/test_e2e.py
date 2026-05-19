#!/usr/bin/env python3
"""端到端测试：真实 API 调用，验证完整流程。"""

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idea_code.prompts.manager import get_registry
from idea_code.orchestrator import run
from idea_code.state import load_state
from idea_code.config import PROJECTS_DIR
from idea_code.utils import slugify


def _e2e_slug(seed):
    return slugify(seed)


def green(s): return f"\033[32m{s}\033[0m"
def red(s): return f"\033[31m{s}\033[0m"
def bold(s): return f"\033[1m{s}\033[0m"


def test_dev_doc_e2e():
    seed = "一个命令行待办清单工具，支持添加任务、删除任务、标记完成、查看列表"
    print(bold("\n=== Test 1: dev-doc ===\n"))

    registry = get_registry("prompts")
    pkg = registry.get("requirements-dev-doc")
    slug = _e2e_slug(seed)
    proj_dir = Path(PROJECTS_DIR) / slug

    if proj_dir.exists():
        import shutil; shutil.rmtree(proj_dir)

    start = time.time()
    success = run(seed=seed, pkg=pkg, max_rounds=2)
    elapsed = time.time() - start

    req_path = proj_dir / "requirements.md"
    seed_path = proj_dir / "seed.md"
    state_path = proj_dir / "state.json"
    reviews_dir = proj_dir / "reviews"

    checks = [
        ("requirements.md", req_path.exists()),
        ("seed.md", seed_path.exists()),
        ("state.json", state_path.exists()),
        ("reviews/", reviews_dir.exists() and any(reviews_dir.iterdir())),
    ]
    if req_path.exists():
        size = len(req_path.read_text())
        checks.append((f"文档 > 500B ({size}B)", size > 500))

    for n, p in checks:
        print(f"  {green('OK') if p else red('FAIL')} {n}")
    print(f"  耗时: {elapsed:.0f}s | 收敛: {'是' if success else '否'}")
    return all(v for _, v in checks) and success


def test_research_e2e():
    seed = "调研当前主流 Python Web 框架（Flask、Django、FastAPI）的现状、特点和适用场景"
    print(bold("\n=== Test 2: research ===\n"))

    registry = get_registry("prompts")
    pkg = registry.get("requirements-research")
    slug = _e2e_slug(seed)
    proj_dir = Path(PROJECTS_DIR) / slug

    if proj_dir.exists():
        import shutil; shutil.rmtree(proj_dir)

    start = time.time()
    success = run(seed=seed, pkg=pkg, max_rounds=5)
    elapsed = time.time() - start

    report_path = proj_dir / "report.md"
    checks = [
        ("report.md", report_path.exists()),
        ("seed.md", (proj_dir / "seed.md").exists()),
    ]
    if report_path.exists():
        size = len(report_path.read_text())
        checks.append((f"报告 > 500B ({size}B)", size > 500))

    for n, p in checks:
        print(f"  {green('OK') if p else red('FAIL')} {n}")
    print(f"  耗时: {elapsed:.0f}s | 收敛: {'是' if success else '否'}")
    return all(v for _, v in checks) and success


def test_resume_e2e():
    seed = "一个简单的天气查询 CLI 工具"
    print(bold("\n=== Test 3: resume ===\n"))

    registry = get_registry("prompts")
    pkg = registry.get("requirements-dev-doc")
    slug = _e2e_slug(seed)
    proj_dir = Path(PROJECTS_DIR) / slug

    if proj_dir.exists():
        import shutil; shutil.rmtree(proj_dir)

    print("--- Round 1 ---")
    run(seed=seed, pkg=pkg, max_rounds=1)

    state = load_state(slug)
    checks = [
        ("state.json exists", state is not None),
        ("round == 1", state and state["round"] == 1),
    ]

    if state:
        print("--- Round 2 (resume) ---")
        run(seed=state["seed"], pkg=pkg, max_rounds=2,
            resume_round=state["round"] + 1)
        state2 = load_state(slug)
        checks.append(("resume OK", True))
        checks.append(("round == 2", state2 and state2["round"] == 2))

    for n, p in checks:
        print(f"  {green('OK') if p else red('FAIL')} {n}")
    return all(v for _, v in checks)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", choices=["dev-doc", "research", "resume", "all"], default="all")
    args = parser.parse_args()

    results = {}
    if args.test in ("dev-doc", "all"): results["dev-doc"] = test_dev_doc_e2e()
    if args.test in ("research", "all"): results["research"] = test_research_e2e()
    if args.test in ("resume", "all"): results["resume"] = test_resume_e2e()

    print(bold("\n" + "=" * 40))
    print(bold("  E2E Results"))
    print("=" * 40)
    for n, p in results.items():
        print(f"  {n:12s} {green('PASS') if p else red('FAIL')}")
    print("=" * 40)

    ok = all(results.values())
    print(green("\nAll passed!") if ok else red(f"\n{sum(1 for v in results.values() if not v)} failed"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
