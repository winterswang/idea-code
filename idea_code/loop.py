"""Agent 核心循环。

内置 compact_if_needed，在每次 LLM 调用前检查压缩。
每次调用后累积 token 用量，循环结束后返回汇总。
"""

from .compact import compact_if_needed


def agent_loop(
    messages: list,
    system: str,
    tools: list,
    tool_handlers: dict,
    ctx,  # AgentContext
) -> dict:
    """核心循环：LLM 调用 → 工具执行 → 结果返回 → 循环。

    原地修改 messages，循环直到 stop_reason != "tool_use"。
    每次 LLM 调用前自动调用 compact_if_needed 管理上下文。

    Returns:
        {"calls": N, "tokens_in": N, "tokens_out": N}
    """
    calls = 0
    tokens_in = 0
    tokens_out = 0

    while True:
        compact_if_needed(messages, ctx.client, ctx.model)

        response = ctx.client.messages.create(
            model=ctx.model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=ctx.max_tokens,
        )
        calls += 1
        # 提取 token 用量
        if hasattr(response, "usage"):
            tokens_in += getattr(response.usage, "input_tokens", 0)
            tokens_out += getattr(response.usage, "output_tokens", 0)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return {
                "calls": calls,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "stop_reason": response.stop_reason,
            }

        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = tool_handlers.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"未知工具: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output),
                })

        messages.append({"role": "user", "content": results})
