"""AgentContext — 封装 Anthropic client + model + max_tokens。

由 Orchestrator 创建并持有，注入给下层模块。
"""

from dataclasses import dataclass
from anthropic import Anthropic


@dataclass
class AgentContext:
    client: Anthropic
    model: str
    max_tokens: int = 8000


def create_context(api_key: str, model: str, base_url: str | None = None,
                   max_tokens: int = 8000) -> AgentContext:
    """工厂函数：从环境变量创建 AgentContext。"""
    import os
    if not api_key:
        raise ValueError("api_key 不能为空")
    if base_url:
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        client = Anthropic(base_url=base_url, api_key=api_key, timeout=300)
    else:
        client = Anthropic(api_key=api_key, timeout=300)
    return AgentContext(client=client, model=model, max_tokens=max_tokens)
