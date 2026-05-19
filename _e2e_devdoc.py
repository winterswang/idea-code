"""DEV-DOC: 复杂度验收 — AI 代码审查平台"""
import sys, time, os
os.environ["IDEA_VERBOSE_LOG"] = "1"
sys.path.insert(0, '.')
from idea_code.prompts.manager import get_registry
from idea_code.orchestrator import run

pkg = get_registry('prompts').get('requirements-dev-doc')
start = time.time()
success = run(
    seed='一个面向企业团队的 AI 驱动代码审查平台，支持接入 GitHub/GitLab 仓库，自动对 PR 进行安全漏洞检测、代码风格审查、架构一致性检查，生成结构化审查报告并支持人工覆审和团队协作标注。需要支持私有化部署、多语言代码分析、自定义规则引擎和 CI/CD 流水线集成。',
    pkg=pkg, max_rounds=7,
)
elapsed = time.time() - start
print(f'\n=== DEV-DOC: {"CONVERGED" if success else "NOT CONVERGED"} in {elapsed:.0f}s ===')
