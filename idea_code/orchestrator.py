"""v1 编排器：Builder + 双 Reviewer 迭代闭环。

核心流程:
  1. 加载 PackageConfig → 渲染 Prompt
  2. 进入迭代循环 (max_rounds):
     a. Builder 生成/更新文档
     b. Reviewer A 评审 → 解析 JSON（最多重试 2 次）
     c. Reviewer B 评审 → 解析 JSON（最多重试 2 次）
     d. 活跃 Reviewer 全部 >=95 且意图对齐 >=27 → 通过
     e. 合并 feedback → 下一轮
  3. 保存 state.json + 评审记录
"""

import concurrent.futures
import json
import os
import sys
import time as _time
import traceback
from pathlib import Path

from .config import MAX_ROUNDS, PROJECTS_DIR, VERBOSE_LOG, validate_env
from .context import create_context, AgentContext
from .prompts.manager import PackageConfig
from .subagent import run_subagent
from .review import (
    parse_review_output,
    extract_dimension_score,
    check_per_dimension_threshold,
    INTENT_DIM_NAME,
    INTENT_MAX_SCORE,
    PER_DIM_MIN_RATIO,
    merge_feedback,
    scoring_table_to_markdown,
    ReviewResult,
    compact_review_history,
)
from .state import save_state, save_review_record, load_state
from .logger import RunLogger
from .tracer import ExecutionTracer
from .utils import slugify


def _build_review_history(project_dir: Path, round_num: int, ctx) -> str:
    """从 reviews/ 目录读取前 round_num-1 轮记录并 LLM 压缩。

    缓存策略：压缩结果保存到 reviews/round-{N:02d}-summary.txt，
    后续轮次只增量压缩最新轮次，避免 O(n) 重复 LLM 调用。
    """
    if round_num <= 1:
        return ""
    reviews_dir = project_dir / "reviews"
    if not reviews_dir.exists():
        return ""

    # 已有缓存的摘要 → 只压缩最新一轮增量
    prev_summary_path = reviews_dir / f"round-{round_num - 1:02d}-summary.txt"
    if prev_summary_path.exists():
        prev_summary = prev_summary_path.read_text(encoding="utf-8").strip()
    else:
        prev_summary = ""

    # 读取最新一轮的评审记录
    latest_record_path = reviews_dir / f"round-{round_num - 1:02d}.json"
    if not latest_record_path.exists():
        return prev_summary or ""

    try:
        latest_record = json.loads(latest_record_path.read_text(encoding="utf-8"))
    except Exception:
        return prev_summary or ""

    # 增量压缩：历史摘要 + 最新一轮
    if prev_summary:
        combined = f"## 历史评审摘要\n{prev_summary}\n\n## 第 {round_num - 1} 轮评审\n{json.dumps(latest_record, indent=2, ensure_ascii=False)}"
    else:
        combined = json.dumps([latest_record], indent=2, ensure_ascii=False)

    summary = compact_review_history(combined, ctx)
    if summary:
        (reviews_dir / f"round-{round_num - 1:02d}-summary.txt").write_text(
            summary, encoding="utf-8"
        )
    return summary or prev_summary or ""


def _format_scoring_table(scoring: list, philosophy: str = "") -> str:
    return scoring_table_to_markdown(scoring, philosophy)


def _format_dimensions_summary(dimensions: list[dict]) -> str:
    """将维度得分列表格式化为单行摘要。"""
    parts = []
    for dim in dimensions:
        if isinstance(dim, dict):
            name = dim.get("name", "?")
            score = dim.get("score", "?")
            max_s = dim.get("max", "?")
            parts.append(f"{name} {score}/{max_s}")
    return " | ".join(parts) if parts else "(维度数据缺失)"


def _reviewer_health_check(result_a: ReviewResult, result_b: ReviewResult) -> list[str]:
    """检测异常评审信号，返回告警列表。不阻止流程。"""
    warnings = []

    for label, result in [("A", result_a), ("B", result_b)]:
        if not result.reviewer:
            continue
        if result.total_score == 100:
            warnings.append(f"⚠️ Reviewer {label} 给了满分 100——可能未认真评审")
        if result.passed and result.total_score < 95:
            warnings.append(
                f"⚠️ Reviewer {label}: passed=true 但 total_score={result.total_score}（矛盾）"
            )

    intent_a = extract_dimension_score(result_a.dimensions, INTENT_DIM_NAME)
    intent_b = extract_dimension_score(result_b.dimensions, INTENT_DIM_NAME)
    if intent_a is not None and intent_b is not None and abs(intent_a - intent_b) >= 10:
        warnings.append(
            f"⚠️ 意图对齐分歧过大 (A={intent_a}/30 vs B={intent_b}/30)"
        )

    return warnings


def _run_reviewer(
    doc_content: str,
    seed: str,
    pkg: PackageConfig,
    which: str,
    ctx: AgentContext,
    round_num: int = 1,
    max_rounds: int = 10,
    max_retries: int = 2,
    tracer: ExecutionTracer | None = None,
) -> tuple[ReviewResult, dict]:
    """运行单个 Reviewer，返回 (ReviewResult, token_info)。"""
    reviewer = pkg.reviewer_a if which == "a" else pkg.reviewer_b
    if not reviewer:
        return ReviewResult(total_score=0), {"calls": 0, "tokens_in": 0, "tokens_out": 0}

    scoring_table = _format_scoring_table(reviewer.scoring, reviewer.scoring_philosophy)
    total_tokens = {"calls": 0, "tokens_in": 0, "tokens_out": 0}

    # 提取预期维度名（用于校验 Reviewer 输出）
    expected_dims = [s.dimension for s in reviewer.scoring] if reviewer.scoring else []

    for attempt in range(max_retries):
        system = pkg.render_reviewer_prompt(
            which, role_name=reviewer.name, scoring_philosophy=reviewer.scoring_philosophy, scoring_table=scoring_table
        )

        # 构建历史评审摘要
        project_dir = Path(PROJECTS_DIR) / slugify(seed)
        review_history_summary = _build_review_history(project_dir, round_num, ctx)
        if review_history_summary and tracer:
            tracer.step("history_built", round_num=round_num, agent=f"reviewer-{which}",
                        prior_rounds=round_num - 1)

        user = pkg.render_reviewer_context(
            which,
            seed=seed,
            doc_content=doc_content,
            scoring_table=scoring_table,
            round_num=str(round_num),
            max_rounds=str(max_rounds),
            review_history_summary=review_history_summary,
        )
        if tracer:
            tracer.save_context(round_num, f"reviewer-{which}", system, user)
        text, usage = run_subagent(user, system, ctx)
        for k in ("calls", "tokens_in", "tokens_out"):
            total_tokens[k] += usage.get(k, 0)

        result = parse_review_output(text, expected_dimensions=expected_dims)
        if result.reviewer:
            # 维名校验：不匹配则在下次尝试中重试
            if not result.dimension_names_valid and attempt < max_retries - 1:
                if tracer:
                    tracer.step("dim_validation_retry", round_num=round_num,
                                reviewer=which, attempt=attempt + 1)
                continue
            # 总分校验：不等于维度之和则在下次尝试中重试
            if not result.dimension_total_match and attempt < max_retries - 1:
                if tracer:
                    actual_sum = sum(int(d.get("score", 0)) for d in result.dimensions if isinstance(d, dict))
                    tracer.step("total_score_mismatch", round_num=round_num,
                                reviewer=which, declared=result.total_score, actual=actual_sum)
                continue
            if tracer and expected_dims:
                tracer.step("dim_validation_ok", round_num=round_num, reviewer=which,
                            names_ok=result.dimension_names_valid, count_ok=result.dimension_count_match)
            return result, total_tokens

    return ReviewResult(total_score=0, error=f"JSON 解析失败 (已重试 {max_retries} 次)"), total_tokens


def run(
    seed: str,
    pkg: PackageConfig,
    max_rounds: int = MAX_ROUNDS,
    resume_round: int = 1,
) -> bool:
    """运行 v1 流程。

    Returns: 是否收敛成功
    """
    # input_type == "existing_file" 时, seed 为文件路径 → 读取为输入文档
    if pkg.input_type == "existing_file":
        input_path = Path(seed)
        if input_path.exists():
            seed = input_path.read_text(encoding="utf-8")
        else:
            print(f"错误: 输入文件不存在: {seed}")
            return False
        slug = slugify(seed[:80])
    else:
        slug = slugify(seed)

    project_dir = Path(PROJECTS_DIR) / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    output_file = project_dir / pkg.output_file
    seed_file = project_dir / "seed.md"
    logger = RunLogger(project_dir)
    tracer = ExecutionTracer(project_dir, enabled=VERBOSE_LOG)

    # ── 初始化日志 ──
    tracer.step("session_start", msg=f"包={pkg.id} 种子={seed[:80]} max_rounds={max_rounds} resume={resume_round}",
                 package=pkg.id, max_rounds=max_rounds, resume_round=resume_round)

    if resume_round == 1:
        seed_file.write_text(f"# 种子想法\n\n{seed}", encoding="utf-8")
        tracer.step("seed_saved")

    missing = validate_env()
    if missing:
        tracer.step("env_missing", msg=f"缺少: {missing}")
        print(f"错误: 缺少环境变量 {missing}，请在 .env 中配置")
        tracer.close()
        return False

    # 创建 3 个 AgentContext
    tracer.step("context_init")
    # Builder 独立 max_tokens: IDEA_BUILDER_MAX_TOKENS > IDEA_MAX_TOKENS > 32000
    builder_max_tokens = int(
        os.environ.get("IDEA_BUILDER_MAX_TOKENS")
        or os.environ.get("IDEA_MAX_TOKENS", "32000")
    )
    builder_ctx = create_context(
        api_key=os.environ["IDEA_API_KEY"],
        model=os.environ.get("IDEA_MODEL", "claude-sonnet-4-6"),
        base_url=os.environ.get("IDEA_BASE_URL"),
        max_tokens=builder_max_tokens,
    )
    rev_a_ctx = create_context(
        api_key=os.environ["REV_A_API_KEY"],
        model=os.environ.get("REV_A_MODEL", "claude-sonnet-4-6"),
        base_url=os.environ.get("REV_A_BASE_URL"),
        max_tokens=int(os.environ.get("REV_A_MAX_TOKENS", "8000")),
    )
    rev_b_ctx = create_context(
        api_key=os.environ["REV_B_API_KEY"],
        model=os.environ.get("REV_B_MODEL", "claude-sonnet-4-6"),
        base_url=os.environ.get("REV_B_BASE_URL"),
        max_tokens=int(os.environ.get("REV_B_MAX_TOKENS", "8000")),
    )

    print(f"\n📁 项目目录: {project_dir}")
    print(f"📝 Prompt 包: {pkg.label}")
    print(f"📄 输出文件: {output_file}")
    if pkg.reviewer_a:
        print(f"🔍 Reviewer A: {pkg.reviewer_a.name}")
    if pkg.reviewer_b:
        print(f"🔍 Reviewer B: {pkg.reviewer_b.name}")
    print(f"🔄 最大轮数: {max_rounds} (从第 {resume_round} 轮开始)\n")
    if VERBOSE_LOG:
        print(f"📊 详细日志: {tracer.path}")

    # resume 时从 state 恢复上一轮 feedback（向后兼容旧 state 无 feedback 字段）
    if resume_round > 1:
        prev_state = load_state(slug)
        feedback = prev_state.get("feedback", "") if prev_state else ""
    else:
        feedback = ""

    if not feedback:
        feedback = "没有反馈信息，请按照相关要求设计需求文档"
    scores_history = []
    rev_a_dead = False
    rev_b_dead = False
    converged = False

    for round_num in range(resume_round, max_rounds + 1):
        tracer.step("round_start", round_num=round_num, max_rounds=max_rounds)
        print(f"═══ Round {round_num}/{max_rounds} ═══")
        logger.round_start(round_num)

        # ── Builder ──────────────────────────────────────
        tracer.step("builder_start", round_num=round_num)
        print("  🏗️  Builder 生成中...")
        builder_system = pkg.render_builder_prompt(role_name=pkg.builder.role)

        # 构建历史评审摘要传递给 Builder
        builder_history = _build_review_history(project_dir, round_num, builder_ctx)
        if builder_history:
            tracer.step("history_built", round_num=round_num, agent="builder",
                        prior_rounds=round_num - 1)

        builder_user = pkg.render_builder_context(
            seed=seed,
            feedback=feedback,
            output_file=str(output_file),
            review_history_summary=builder_history,
        )
        t0 = _time.time()
        try:
            tracer.save_context(round_num, "builder", builder_system, builder_user)
            builder_text, builder_tokens = run_subagent(builder_user, builder_system, builder_ctx)
            latency_ms = int((_time.time() - t0) * 1000)
            tracer.api_call(
                agent="builder", model=builder_ctx.model, round_num=round_num,
                tokens_in=builder_tokens.get("tokens_in", 0),
                tokens_out=builder_tokens.get("tokens_out", 0),
                calls=builder_tokens.get("calls", 0),
                latency_ms=latency_ms, status="ok",
            )
            tracer.step("builder_done", round_num=round_num,
                        output_chars=len(builder_text),
                        tokens_in=builder_tokens.get("tokens_in", 0),
                        tokens_out=builder_tokens.get("tokens_out", 0),
                        calls=builder_tokens.get("calls", 0),
                        latency_ms=latency_ms)
            print(f"     Builder 输出: {builder_text[:120]}...")
        except Exception as e:
            latency_ms = int((_time.time() - t0) * 1000)
            tracer.api_call(
                agent="builder", model=builder_ctx.model, round_num=round_num,
                tokens_in=0, tokens_out=0, calls=0,
                latency_ms=latency_ms, status="error", error=str(e),
            )
            tracer.step("builder_error", round_num=round_num, error=str(e))
            print(f"  ❌ Round {round_num} Builder 异常: {e}", file=sys.stderr)
            print(f"     scores: {scores_history}", file=sys.stderr)
            traceback.print_exc()
            save_state(slug=slug, seed=seed, package_id=pkg.id,
                       round_num=round_num,
                       scores=scores_history, max_rounds=max_rounds,
                       feedback=feedback)
            logger.save()
            tracer.close()
            return False

        # 读取生成的文档
        if not output_file.exists():
            tracer.step("output_missing", round_num=round_num)
            if round_num == 1:
                print("  ❌ Round 1 Builder 未生成文件，终止流程")
                tracer.decision("round1_no_output", "abort", round_num=round_num)
                logger.save()
                tracer.close()
                return False
            print("  ⚠️  Builder 未生成文件，跳过本轮")
            tracer.decision("output_missing", "skip_round", round_num=round_num)
            continue
        doc_content = output_file.read_text(encoding="utf-8")
        tracer.step("doc_loaded", round_num=round_num, doc_chars=len(doc_content))

        # ── Reviewer A/B 并行 ────────────────────────────
        def _run_reviewer_safe(
            which: str, ctx: AgentContext
        ) -> tuple[ReviewResult, dict]:
            t0 = _time.time()
            try:
                r, tok = _run_reviewer(
                    doc_content, seed, pkg, which, ctx, round_num, max_rounds, tracer=tracer
                )
                return r, tok
            except Exception as e:
                return ReviewResult(total_score=0, error=str(e)), {
                    "calls": 0, "tokens_in": 0, "tokens_out": 0,
                }

        result_a = ReviewResult(total_score=0)
        result_b = ReviewResult(total_score=0)
        tokens_a: dict = {}
        tokens_b: dict = {}
        rev_tasks = {}
        if pkg.reviewer_a:
            rev_tasks["a"] = (rev_a_ctx,)
        if pkg.reviewer_b:
            rev_tasks["b"] = (rev_b_ctx,)

        if rev_tasks:
            print("  🔍 Reviewer A/B 评审中...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    which: pool.submit(_run_reviewer_safe, which, ctx)
                    for which, (ctx,) in rev_tasks.items()
                }
                for which, fut in futures.items():
                    try:
                        r, tok = fut.result()
                    except Exception as e:
                        r = ReviewResult(total_score=0, error=str(e))
                        tok = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
                    if which == "a":
                        result_a, tokens_a = r, tok
                    else:
                        result_b, tokens_b = r, tok

        # ── Reviewer 结果汇报（主线程安全） ────────────────
        for which, r in [("a", result_a), ("b", result_b)]:
            loader = pkg.reviewer_a if which == "a" else pkg.reviewer_b
            if not loader:
                continue
            ctx = rev_a_ctx if which == "a" else rev_b_ctx
            tok = tokens_a if which == "a" else tokens_b
            # tracer 记录
            tracer.api_call(
                agent=f"reviewer_{which}", model=ctx.model,
                round_num=round_num,
                tokens_in=tok.get("tokens_in", 0),
                tokens_out=tok.get("tokens_out", 0),
                calls=tok.get("calls", 0),
                latency_ms=0,
                status="ok" if not r.error else "error",
                error=r.error if r.error else None,
            )
            intent = extract_dimension_score(r.dimensions, INTENT_DIM_NAME)
            dims = _format_dimensions_summary(r.dimensions)
            tracer.review(
                reviewer=which, name=r.reviewer, round_num=round_num,
                total_score=r.total_score, intent=intent, dimensions=dims,
            )
            intent_str = f" 意图{intent}/{INTENT_MAX_SCORE}" if intent is not None else ""
            print(f"     {r.reviewer}: {r.total_score}/100 "
                  f"({'✅' if r.total_score >= 95 else '❌'}){intent_str}")
            print(f"     ↳ {dims}")

        # ── 保存评审记录 ─────────────────────────────────
        save_review_record(
            slug, round_num,
            {
                "reviewer": result_a.reviewer or "N/A",
                "total_score": result_a.total_score,
                "dimensions": result_a.dimensions,
                "blocking_issues": result_a.blocking_issues,
            },
            {
                "reviewer": result_b.reviewer or "N/A",
                "total_score": result_b.total_score,
                "dimensions": result_b.dimensions,
                "blocking_issues": result_b.blocking_issues,
            },
        )

        scores_history.append({
            "round": round_num,
            "reviewer_a_score": result_a.total_score,
            "reviewer_b_score": result_b.total_score,
        })

        # 每轮结束后保存中间态，防止崩溃丢失进度
        tracer.step("state_save", round_num=round_num)
        save_state(slug=slug, seed=seed, package_id=pkg.id,
                   round_num=round_num,
                   scores=scores_history, max_rounds=max_rounds,
                   feedback=feedback)

        # ── Reviewer 健康检查 ───────────────────────────
        health_warnings = _reviewer_health_check(result_a, result_b)
        for w in health_warnings:
            print(f"  {w}")
            tracer.step("health_warning", round_num=round_num, warning=w)

        # ── 连续失败检测 ─────────────────────────────────
        reviewer_scores = []
        if pkg.reviewer_a and not rev_a_dead:
            reviewer_scores.append(result_a.total_score)
        if pkg.reviewer_b and not rev_b_dead:
            reviewer_scores.append(result_b.total_score)

        # 逐 Reviewer 标记失效（连续 2 轮解析失败，非评分 0 分）
        if pkg.reviewer_a and result_a.total_score == 0 and result_a.error:
            rev_a_fails = scores_history[-2:] if len(scores_history) >= 2 else []
            rev_a_fails = [s for s in rev_a_fails if s.get("reviewer_a_score", 0) == 0]
            if len(rev_a_fails) >= 1:
                if not rev_a_dead:
                    rev_a_dead = True
                    print("  ⚠️  Reviewer A 连续失效，切换为单 Reviewer B 模式")
                    tracer.decision("reviewer_dead", "rev_a", round_num=round_num)
        if pkg.reviewer_b and result_b.total_score == 0 and result_b.error:
            rev_b_fails = scores_history[-2:] if len(scores_history) >= 2 else []
            rev_b_fails = [s for s in rev_b_fails if s.get("reviewer_b_score", 0) == 0]
            if len(rev_b_fails) >= 1:
                if not rev_b_dead:
                    rev_b_dead = True
                    print("  ⚠️  Reviewer B 连续失效，切换为单 Reviewer A 模式")
                    tracer.decision("reviewer_dead", "rev_b", round_num=round_num)

        if pkg.reviewer_a and pkg.reviewer_b and rev_a_dead and rev_b_dead:
            print("  ❌ 双 Reviewer 均连续失效，终止流程")
            tracer.decision("reviewer_failure", "both_dead", round_num=round_num)
            logger.save()
            tracer.close()
            return False

        #  Reviewer 复活检测（dead 标记后评分恢复 >0）
        if rev_a_dead and result_a.total_score > 0:
            rev_a_dead = False
            print("  ✅ Reviewer A 已恢复，重启双 Reviewer 模式")
            tracer.decision("reviewer_revived", "rev_a", round_num=round_num)
        if rev_b_dead and result_b.total_score > 0:
            rev_b_dead = False
            print("  ✅ Reviewer B 已恢复，重启双 Reviewer 模式")
            tracer.decision("reviewer_revived", "rev_b", round_num=round_num)

        # ── 收集活跃 Reviewer ───────────────────────────
        active_reviewers = []
        if pkg.reviewer_a:
            active_reviewers.append(("A", result_a))
        if pkg.reviewer_b:
            active_reviewers.append(("B", result_b))

        if not active_reviewers:
            print("❌ 错误: 未配置任何 Reviewer，无法评审")
            tracer.decision("no_reviewers", "abort")
            logger.save()
            tracer.close()
            return False

        # ── 收敛判定 ─────────────────────────────────────
        # 从 Reviewer 配置读取通过阈值（支持不同包不同阈值）
        threshold_a = pkg.reviewer_a.pass_threshold if pkg.reviewer_a else 95
        threshold_b = pkg.reviewer_b.pass_threshold if pkg.reviewer_b else 95

        # 单 Reviewer 降级模式：仅要求存活 Reviewer 通过
        if rev_a_dead or rev_b_dead:
            alive = [r for _, r in active_reviewers if r.total_score > 0]
            alive_labels = [label for label, r in active_reviewers if r.total_score > 0]
            total_ok = alive and all(
                r.total_score >= (threshold_a if lbl == "A" else threshold_b)
                for r, lbl in zip(alive, alive_labels)
            )
            intent_ok = alive and all(
                (extract_dimension_score(r.dimensions, INTENT_DIM_NAME) or 30) >= int(INTENT_MAX_SCORE * 0.90)
                for r in alive
            )
        else:
            total_ok = all(r.total_score >= (threshold_a if label == "A" else threshold_b)
                          for label, r in active_reviewers)
            intent_ok = True
            for _, r in active_reviewers:
                intent = extract_dimension_score(r.dimensions, INTENT_DIM_NAME)
                if intent is not None and intent < int(INTENT_MAX_SCORE * 0.90):
                    intent_ok = False

        # 逐维度门槛检查（预初始化 fail_* 避免后续 NameError）
        per_dim_ok = True
        fail_a: list[str] = []
        fail_b: list[str] = []
        if pkg.reviewer_a and result_a.dimensions and not rev_a_dead:
            ok_a, fail_a = check_per_dimension_threshold(result_a.dimensions, pkg.reviewer_a.scoring)
            per_dim_ok = per_dim_ok and ok_a
        if pkg.reviewer_b and result_b.dimensions and not rev_b_dead:
            ok_b, fail_b = check_per_dimension_threshold(result_b.dimensions, pkg.reviewer_b.scoring)
            per_dim_ok = per_dim_ok and ok_b

        if total_ok and intent_ok and per_dim_ok:
            converged = True
            degraded = rev_a_dead or rev_b_dead
            if degraded:
                print(f"\n✅ 收敛（⚠️ 单 Reviewer 审核 — {'仅 RevA' if not rev_b_dead else '仅 RevB'}）")
            else:
                print(f"\n✅ 收敛！")
            scores_str = ", ".join(f"{label}={r.total_score}" for label, r in active_reviewers)
            intent_str = ", ".join(
                f"{label}意图={extract_dimension_score(r.dimensions, INTENT_DIM_NAME)}/30"
                for label, r in active_reviewers
            )
            tracer.decision("convergence", "converged" if not degraded else "converged_degraded",
                            round_num=round_num, scores=scores_str, intent=intent_str,
                            degraded=degraded)
            for label, r in active_reviewers:
                intent = extract_dimension_score(r.dimensions, INTENT_DIM_NAME)
                intent_str = f" 意图{intent}/30" if intent is not None else ""
                print(f"   Reviewer {label}: {r.total_score}/100{intent_str}")
            logger.round_end(round_num, result_a.total_score, result_b.total_score, converged=True)
            break

        if not total_ok:
            scores = ", ".join(f"{label}={r.total_score}" for label, r in active_reviewers)
            if rev_a_dead or rev_b_dead:
                mode = "单Rev A" if not rev_a_dead else "单Rev B"
                scores += f" ({mode}降级模式)"
            tracer.decision("convergence", "total_fail", round_num=round_num, scores=scores)
            print(f"\n❌ 总分未达标 ({scores})")
        elif not intent_ok:
            tracer.decision("convergence", "intent_fail", round_num=round_num)
            print(f"\n❌ 意图对齐未达标 (需>= {int(INTENT_MAX_SCORE * 0.90)}/30)")
            print(f"   总分虽达 95，但文档可能偏离了种子核心意图，继续迭代。")
        elif not per_dim_ok:
            per_dim_detail = ""
            if fail_a:
                per_dim_detail += f"RevA: {'; '.join(fail_a)}"
            if fail_b:
                if per_dim_detail:
                    per_dim_detail += " | "
                per_dim_detail += f"RevB: {'; '.join(fail_b)}"
            tracer.decision("convergence", "per_dim_fail", round_num=round_num,
                            detail=per_dim_detail)
            print(f"\n❌ 逐维度未达标 (需每维度>= {int(PER_DIM_MIN_RATIO * 100)}% 满分)")
            print(f"   {per_dim_detail}")
            print(f"   总分虽达 95，但存在明显短板维度，继续迭代。")

        logger.round_end(round_num, result_a.total_score, result_b.total_score, converged=False)

        # ── 合并 feedback ────────────────────────────────
        # 过滤 score=0 的 dead Reviewer（避免噪声）
        for_merge = []
        if result_a.total_score > 0:
            for_merge.append(result_a)
        if result_b.total_score > 0:
            for_merge.append(result_b)
        if len(for_merge) == 2:
            feedback = merge_feedback(result_a, result_b)
        elif len(for_merge) == 1:
            feedback = merge_feedback(for_merge[0], ReviewResult())
        else:
            feedback = "本轮无有效评审结果，请检查 Reviewer 配置和网络连接。"

        if not feedback.strip() or feedback == "本轮无有效评审结果，请检查 Reviewer 配置和网络连接。":
            feedback = "本轮 Reviewer 评分解析异常，请检查文档格式并尝试改进。"
        blk = sum(len(r.blocking_issues) for r in for_merge)
        sug = sum(len(r.suggestions) for r in for_merge)
        print(f"     阻塞问题: {blk} 个")
        print(f"     建议: {sug} 条\n")
        tracer.step("round_end", round_num=round_num,
                    blocks=blk, suggestions=sug)

        # ── 停滞检测（最近 3 轮评分无改善时告警） ──
        if len(scores_history) >= 3:
            last3_a = [s["reviewer_a_score"] for s in scores_history[-3:]]
            last3_b = [s["reviewer_b_score"] for s in scores_history[-3:]]
            var_a = max(last3_a) - min(last3_a) if last3_a else 0
            var_b = max(last3_b) - min(last3_b) if last3_b else 0
            if var_a < 2 and var_b < 2 and not converged:
                print(f"  ⚠️  评分停滞（最近3轮 A={last3_a} B={last3_b}），建议手动介入检查")
                tracer.step("stagnation_warning", round_num=round_num,
                            last3_a=str(last3_a), last3_b=str(last3_b))

    # ── 最终状态 ─────────────────────────────────────────
    if not converged:
        tracer.decision("convergence", "max_rounds", round_num=max_rounds)
        last = scores_history[-1] if scores_history else {}
        print(f"\n⚠️  达到最大轮数 {max_rounds}，未收敛。"
              f"最终总分: A={last.get('reviewer_a_score', 'N/A')}, "
              f"B={last.get('reviewer_b_score', 'N/A')}")
        last_review_path = project_dir / "reviews" / f"round-{max_rounds:02d}.json"
        if last_review_path.exists():
            try:
                last_review = json.loads(last_review_path.read_text(encoding="utf-8"))
                for which, key in [("A", "reviewer_a"), ("B", "reviewer_b")]:
                    dims = last_review.get(key, {}).get("dimensions", [])
                    intent = extract_dimension_score(dims, INTENT_DIM_NAME)
                    if intent is not None:
                        print(f"  Reviewer {which} 意图对齐: {intent}/30")
            except Exception:
                pass

        # ── 近收敛检测 ──
        last_a = last.get('reviewer_a_score', 0)
        last_b = last.get('reviewer_b_score', 0)
        if last_a >= 88 and last_b >= 88:
            print(f"\n  💡 评分已接近收敛阈值（A={last_a}, B={last_b}），建议：")
            print(f"     --max-rounds {max_rounds + 3}  继续迭代 2-3 轮大概率收敛")

    tracer.set_rounds(len(scores_history))
    logger.save()
    save_state(slug=slug, seed=seed, package_id=pkg.id,
               round_num=max_rounds,
               scores=scores_history, max_rounds=max_rounds,
               feedback=feedback)

    print(f"\n📂 输出文件: {output_file}")
    print(f"📊 评审记录: {project_dir / 'reviews'}/")
    if VERBOSE_LOG:
        s = tracer.summary()
        print(f"📊 执行日志: {tracer.path}")
        print(f"   {s['total_rounds']} 轮 / {s['total_calls']} 次 API / "
              f"入 {s['total_tokens_in']} tokens / 出 {s['total_tokens_out']} tokens")
    tracer.close()
    return converged
