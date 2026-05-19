"""idea-code CLI 入口。

用法:
  idea-code "<种子想法>" --prompt <包ID>    运行 v1
  idea-code --list-prompts                   列出所有 Prompt 包
  idea-code --resume <project>               恢复中断会话
"""

import argparse
import sys

from .config import MAX_ROUNDS
from .prompts.manager import get_registry
from .orchestrator import run
from .state import load_state


def main():
    parser = argparse.ArgumentParser(
        prog="idea-code",
        description="多 agent 文档生成与代码审查工具",
    )
    parser.add_argument(
        "seed", nargs="?", default=None,
        help="种子想法（自由文本）",
    )
    parser.add_argument(
        "--prompt", dest="package_id", default=None,
        help="Prompt 包 ID（如 requirements-dev-doc）",
    )
    parser.add_argument(
        "--list-prompts", action="store_true",
        help="列出所有已注册的 Prompt 包",
    )
    parser.add_argument(
        "--resume", dest="resume_project", default=None,
        help="恢复指定项目的会话",
    )
    parser.add_argument(
        "--max-rounds", type=int, default=MAX_ROUNDS,
        help=f"最大迭代轮数（默认: {MAX_ROUNDS}）",
    )
    parser.add_argument(
        "--prompts-dir", default="prompts",
        help="Prompt 配置目录（默认: prompts）",
    )

    args = parser.parse_args()
    registry = get_registry(args.prompts_dir)

    # ── --list-prompts ───────────────────────────────────
    if args.list_prompts:
        packages = registry.list_packages_detail()
        if not packages:
            print("未找到任何 Prompt 包。请在 prompts/ 目录下添加。")
            return

        print(f"已注册 {len(packages)} 个 Prompt 包:\n")
        for p in packages:
            print(f"  {p['id']:30s} → {p['output_file']:20s} {p['label']}")
            print(f"  {'':30s}   {p['description']}")
            if p['reviewer_count']:
                print(f"  {'':30s}   Reviewer × {p['reviewer_count']}")
            print()
        return

    # ── --resume ─────────────────────────────────────────
    if args.resume_project:
        state = load_state(args.resume_project)
        if not state:
            print(f"错误: 未找到项目 '{args.resume_project}'")
            sys.exit(1)

        pkg = registry.get(state["prompt_package"])
        if not pkg:
            print(f"错误: Prompt 包 '{state['prompt_package']}' 不存在（可能已被删除）")
            sys.exit(1)

        resume_round = state["round"] + 1
        max_rounds = state.get("max_rounds") if state.get("max_rounds") is not None else args.max_rounds

        if resume_round > max_rounds:
            print(f"⚠️  项目 '{state['project']}' 已完成 {state['round']} 轮，达到最大轮数 {max_rounds}，无需恢复。")
            sys.exit(0)

        print(f"\n🔄 恢复项目: {state['project']}")
        print(f"📝 Prompt 包: {state['prompt_package']}")
        print(f"📊 已完成 {state['round']} 轮，从第 {resume_round} 轮继续\n")

        success = run(
            seed=state["seed"],
            pkg=pkg,
            max_rounds=max_rounds,
            resume_round=resume_round,
        )
        sys.exit(0 if success else 1)

    # ── 运行 v1 ─────────────────────────────────────────
    if not args.seed:
        parser.error("需要提供种子想法，或使用 --list-prompts / --resume")

    if not args.package_id:
        parser.error("需要指定 --prompt（如 --prompt requirements-dev-doc）")

    pkg = registry.get(args.package_id)
    if not pkg:
        available = registry.list_packages()
        print(f"错误: 未知 Prompt 包 '{args.package_id}'")
        if available:
            print(f"可用包: {', '.join(available)}")
        else:
            print("未找到任何 Prompt 包。请在 prompts/ 目录下添加。")
        sys.exit(1)

    print(f"\n🚀 idea-code v1 — Requirements 生成")
    print(f"📝 种子: {args.seed}")

    success = run(seed=args.seed, pkg=pkg, max_rounds=args.max_rounds)

    if success:
        print("\n✨ 完成！文档已通过双 Reviewer >=95 分评审。")
    else:
        print("\n⚠️  流程结束（未收敛）。可查看输出文件或调整种子想法后重试。")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
