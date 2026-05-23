"""RESEARCH: 复杂度验收 — 现代 API 网关方案调研"""
import sys, time, os
os.environ["IDEA_VERBOSE_LOG"] = "1"
sys.path.insert(0, '.')
from idea_code.prompts.manager import get_registry
from idea_code.orchestrator import run

pkg = get_registry('prompts').get('requirements-research')
start = time.time()
success = run(
    seed='调研当前主流 API 网关方案（Kong、APISIX、Traefik、Envoy + Istio、AWS API Gateway）的技术架构、性能基准、插件生态、服务网格集成能力、云原生适配度、运维复杂度以及适用场景对比，给出企业级选型建议。',
    pkg=pkg, max_rounds=10,
)
elapsed = time.time() - start
print(f'\n=== RESEARCH: {"CONVERGED" if success else "NOT CONVERGED"} in {elapsed:.0f}s ===')
