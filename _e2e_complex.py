import sys, time
sys.path.insert(0, '.')
from idea_code.prompts.manager import get_registry
from idea_code.orchestrator import run

pkg = get_registry('prompts').get('requirements-dev-doc')
start = time.time()
success = run(
    seed='一个支持多币种的个人财务管理App，用户可以记录收支、查看月度报表、设置预算提醒。需要支持离线使用和数据导出。',
    pkg=pkg, max_rounds=10,
)
print(f'\n=== COMPLEX FINAL: {"CONVERGED" if success else "NOT CONVERGED"} in {time.time()-start:.0f}s ===')
