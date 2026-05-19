"""Prompt 管理器：目录扫描 + 动态注册。

每个 Prompt 包 = prompts/ 下的一个子目录，包含：
  - config.json:  包元数据 + 模型配置（含 scoring_file 引用）
  - scoring-*.json: 独立评分维度文件
  - *.md:         静态角色 Prompt
  - *-context.md: 动态上下文模板

新增 Prompt 包只需加目录，无需改代码。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScoringDim:
    dimension: str
    max_score: int
    description: str
    calibration: dict = field(default_factory=dict)


@dataclass
class ReviewerConfig:
    name: str
    model: str
    prompt_file: str
    context_file: str
    scoring_philosophy: str = ""
    pass_threshold: int = 95
    scoring: list[ScoringDim] = field(default_factory=list)


@dataclass
class BuilderConfig:
    role: str
    model: str
    prompt_file: str
    context_file: str


@dataclass
class PackageConfig:
    """一个 Prompt 包的完整配置。"""
    id: str
    label: str
    description: str
    output_file: str
    input_type: str
    reviewer_count: int
    builder: BuilderConfig
    reviewer_a: ReviewerConfig | None
    reviewer_b: ReviewerConfig | None

    # 缓存的 Prompt 内容（加载后填充）
    _builder_prompt: str = ""
    _builder_context: str = ""
    _reviewer_a_prompt: str = ""
    _reviewer_a_context: str = ""
    _reviewer_b_prompt: str = ""
    _reviewer_b_context: str = ""

    def render_builder_prompt(self, **kwargs) -> str:
        """渲染 Builder 的 system prompt。"""
        return self._render(self._builder_prompt, kwargs)

    def render_builder_context(self, **kwargs) -> str:
        """渲染 Builder 的 user context。"""
        return self._render(self._builder_context, kwargs)

    def render_reviewer_prompt(self, which: str, **kwargs) -> str:
        """渲染 Reviewer 的 system prompt。which = "a" | "b"."""
        if which == "a" and self._reviewer_a_prompt:
            return self._render(self._reviewer_a_prompt, kwargs)
        if which == "b" and self._reviewer_b_prompt:
            return self._render(self._reviewer_b_prompt, kwargs)
        return ""

    def render_reviewer_context(self, which: str, **kwargs) -> str:
        """渲染 Reviewer 的 user context。which = "a" | "b"."""
        if which == "a" and self._reviewer_a_context:
            return self._render(self._reviewer_a_context, kwargs)
        if which == "b" and self._reviewer_b_context:
            return self._render(self._reviewer_b_context, kwargs)
        return ""

    @staticmethod
    def _render(template: str, kwargs: dict) -> str:
        result = template
        for key, value in kwargs.items():
            result = result.replace("{" + key + "}", str(value))
        return result


class PromptRegistry:
    """Prompt 注册表：扫描 prompts/ 目录，动态注册所有 Prompt 包。"""

    def __init__(self, prompts_root: str | Path = "prompts"):
        self.prompts_root = Path(prompts_root)
        self._packages: dict[str, PackageConfig] = {}
        self._scan()

    def _scan(self) -> None:
        if not self.prompts_root.exists():
            return

        for pkg_dir in sorted(self.prompts_root.iterdir()):
            if not pkg_dir.is_dir():
                continue

            config_path = pkg_dir / "config.json"
            if not config_path.exists():
                continue

            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"[警告] 跳过 {pkg_dir.name}: config.json 解析失败 - {e}")
                continue

            pkg_id = pkg_dir.name
            builder_raw = raw.get("builder", {})
            rev_a_raw = raw.get("reviewer_a", {})
            rev_b_raw = raw.get("reviewer_b", {})

            pkg = PackageConfig(
                id=pkg_id,
                label=raw.get("label", pkg_id),
                description=raw.get("description", ""),
                output_file=raw.get("output_file", f"{pkg_id}.md"),
                input_type=raw.get("input", {}).get("type", "seed_text"),  # v5 预留: existing_file / git_diff
                reviewer_count=int(raw.get("reviewer_count", 2)),
                builder=BuilderConfig(
                    role=builder_raw.get("role", ""),
                    model=builder_raw.get("model", "IDEA"),
                    prompt_file=builder_raw.get("prompt_file", "builder.md"),
                    context_file=builder_raw.get("context_file", "builder-context.md"),
                ),
                reviewer_a=self._parse_reviewer(rev_a_raw, pkg_dir) if rev_a_raw else None,
                reviewer_b=self._parse_reviewer(rev_b_raw, pkg_dir) if rev_b_raw else None,
            )

            # 加载 Prompt 文件内容
            pkg._builder_prompt = self._read_file(pkg_dir / pkg.builder.prompt_file)
            pkg._builder_context = self._read_file(pkg_dir / pkg.builder.context_file)
            if pkg.reviewer_a:
                pkg._reviewer_a_prompt = self._read_file(pkg_dir / pkg.reviewer_a.prompt_file)
                pkg._reviewer_a_context = self._read_file(pkg_dir / pkg.reviewer_a.context_file)
            if pkg.reviewer_b:
                pkg._reviewer_b_prompt = self._read_file(pkg_dir / pkg.reviewer_b.prompt_file)
                pkg._reviewer_b_context = self._read_file(pkg_dir / pkg.reviewer_b.context_file)

            self._packages[pkg_id] = pkg

    @staticmethod
    def _parse_reviewer(raw: dict, pkg_dir: Path) -> ReviewerConfig:
        scoring = []
        scoring_file = raw.get("scoring_file", "")
        if scoring_file:
            scoring_path = pkg_dir / scoring_file
            if scoring_path.exists():
                try:
                    scoring_data = json.loads(scoring_path.read_text(encoding="utf-8"))
                    for dim in scoring_data.get("dimensions", []):
                        scoring.append(ScoringDim(
                            dimension=dim.get("dimension", ""),
                            max_score=dim.get("max_score", 0),
                            description=dim.get("description", ""),
                            calibration=dim.get("calibration", {}),
                        ))
                except json.JSONDecodeError:
                    pass

        return ReviewerConfig(
            name=raw.get("name", ""),
            model=raw.get("model", "IDEA"),
            prompt_file=raw.get("prompt_file", ""),
            context_file=raw.get("context_file", ""),
            scoring_philosophy=scoring_data.get("scoring_philosophy", ""),
            pass_threshold=scoring_data.get("pass_threshold", 95),
            scoring=scoring,
        )

    @staticmethod
    def _read_file(path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return ""

    def list_packages(self) -> list[str]:
        return sorted(self._packages.keys())

    def get(self, package_id: str) -> PackageConfig | None:
        return self._packages.get(package_id)

    def list_packages_detail(self) -> list[dict]:
        result = []
        for pid, pkg in self._packages.items():
            result.append({
                "id": pid,
                "label": pkg.label,
                "output_file": pkg.output_file,
                "description": pkg.description,
                "reviewer_count": pkg.reviewer_count,
            })
        return result


_registry: PromptRegistry | None = None


def get_registry(prompts_root: str | Path = "prompts") -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry(prompts_root)
    return _registry
