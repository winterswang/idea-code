"""子 agent：独立 context 执行任务，返回最终文本 + token 用量。

Builder 和 Reviewer 都通过子 agent 模式运行，保持 context 隔离。

内置 max_tokens 耗尽重试：当 LLM 输出只有 ThinkingBlock 无 TextBlock
（DeepSeek 等模型 thinking 过长吃掉全部 token 预算）时，自动以更高
max_tokens 重试，最多 2 次。
"""

from .loop import agent_loop
from .tools import TOOLS, TOOL_HANDLERS
from .context import AgentContext

# thinking 耗尽时 max_tokens 的增长倍数
_MAX_TOKENS_RETRY_MULTIPLIER = 2
# 最大重试次数（避免无限递归）
_MAX_RETRY_DEPTH = 2


def run_subagent(
    prompt: str,
    system: str,
    ctx,  # AgentContext
    _depth: int = 0,
) -> tuple[str, dict]:
    """启动子 agent，返回 (最终文本, token_info)。

    token_info = {"calls": N, "tokens_in": N, "tokens_out": N,
                  "stop_reason": str}
    messages 在内部创建和销毁，不返回给调用方。
    """
    messages = [{"role": "user", "content": prompt}]
    usage = agent_loop(messages, system, TOOLS, TOOL_HANDLERS, ctx)

    # 提取最终文本
    has_content_blocks = False
    has_thinking_only = False
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                has_content_blocks = len(content) > 0
                # 检查是否只有 ThinkingBlock（无文本）
                if has_content_blocks:
                    has_thinking_only = all(
                        hasattr(b, "thinking") for b in content
                    )
                texts = [b.text for b in content if hasattr(b, "text") and b.text.strip()]
                if texts:
                    return "\n".join(texts), usage
            elif isinstance(content, str) and content.strip():
                return content, usage

    # 检测: thinking 吃掉全部 token 预算 → 增大 max_tokens 重试
    stop_reason = usage.get("stop_reason", "")
    if (
        has_content_blocks
        and has_thinking_only
        and stop_reason == "max_tokens"
        and _depth < _MAX_RETRY_DEPTH
    ):
        retry_ctx = AgentContext(
            client=ctx.client,
            model=ctx.model,
            max_tokens=ctx.max_tokens * _MAX_TOKENS_RETRY_MULTIPLIER,
        )
        return run_subagent(prompt, system, retry_ctx, _depth=_depth + 1)

    return "(无输出)", usage
