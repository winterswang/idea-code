"""子 agent：独立 context 执行任务，返回最终文本 + token 用量。

Builder 和 Reviewer 都通过子 agent 模式运行，保持 context 隔离。
"""

from .loop import agent_loop
from .tools import TOOLS, TOOL_HANDLERS


def run_subagent(
    prompt: str,
    system: str,
    ctx,  # AgentContext
) -> tuple[str, dict]:
    """启动子 agent，返回 (最终文本, token_info)。

    token_info = {"calls": N, "tokens_in": N, "tokens_out": N}
    messages 在内部创建和销毁，不返回给调用方。
    """
    messages = [{"role": "user", "content": prompt}]
    usage = agent_loop(messages, system, TOOLS, TOOL_HANDLERS, ctx)

    # 提取最终文本
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                texts = [b.text for b in content if hasattr(b, "text") and b.text.strip()]
                if texts:
                    return "\n".join(texts), usage
            elif isinstance(content, str) and content.strip():
                return content, usage

    return "(无输出)", usage
