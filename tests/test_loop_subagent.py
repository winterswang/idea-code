"""单元测试：Agent 核心循环 + 子 Agent 提取逻辑。"""

from unittest.mock import MagicMock, patch, ANY
from dataclasses import dataclass

import pytest

from idea_code.loop import agent_loop


# ── Helper: mock content block types ──────────────────────────────────

class MockTextBlock:
    type = "text"
    def __init__(self, text: str):
        self.text = text

class MockThinkingBlock:
    type = "thinking"
    thinking = "... deep thoughts"
    signature = "abc"

class MockToolUseBlock:
    type = "tool_use"
    def __init__(self, name: str, input_: dict, id_: str = "tu-1"):
        self.name = name
        self.input = input_
        self.id = id_


# ── Helper: mock response ────────────────────────────────────────────

class MockUsage:
    input_tokens = 10
    output_tokens = 50

class MockResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = MockUsage()


# ── Helper: mock AgentContext ─────────────────────────────────────────

@dataclass
class MockAgentContext:
    client: MagicMock
    model: str = "test-model"
    max_tokens: int = 8000


# ── Tests: agent_loop ─────────────────────────────────────────────────

class TestAgentLoop:
    def test_returns_stop_reason(self):
        """验证 agent_loop 返回 stop_reason 字段。"""
        client = MagicMock()
        client.messages.create.return_value = MockResponse(
            content=[MockTextBlock("hello")],
            stop_reason="end_turn",
        )
        ctx = MockAgentContext(client=client)
        messages = [{"role": "user", "content": "hi"}]

        result = agent_loop(messages, "system", [], {}, ctx)
        assert result["stop_reason"] == "end_turn"
        assert result["calls"] == 1
        assert result["tokens_in"] == 10
        assert result["tokens_out"] == 50

    def test_max_tokens_stop_reason(self):
        """验证 max_tokens 截断时 stop_reason 正确传回。"""
        client = MagicMock()
        client.messages.create.return_value = MockResponse(
            content=[MockThinkingBlock()],
            stop_reason="max_tokens",
        )
        ctx = MockAgentContext(client=client)
        messages = [{"role": "user", "content": "long text"}]

        result = agent_loop(messages, "system", [], {}, ctx)
        assert result["stop_reason"] == "max_tokens"

    def test_tool_use_cycle(self):
        """验证 tool_use 后循环继续，最终 stop_reason 是最终响应。"""
        client = MagicMock()
        client.messages.create.side_effect = [
            # 第 1 次: tool_use
            MockResponse(
                content=[MockToolUseBlock("bash", {"command": "echo hello"}, "tu-1")],
                stop_reason="tool_use",
            ),
            # 第 2 次: end_turn
            MockResponse(
                content=[MockTextBlock("done")],
                stop_reason="end_turn",
            ),
        ]
        ctx = MockAgentContext(client=client)
        messages = [{"role": "user", "content": "run command"}]
        tool_handlers = {"bash": lambda **kw: "hello"}

        result = agent_loop(messages, "system", [{"name": "bash"}], tool_handlers, ctx)
        assert result["stop_reason"] == "end_turn"
        assert result["calls"] == 2
        # tool_result 应被追加到 messages 的 user content list 中
        has_tool_result = False
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        has_tool_result = True
        assert has_tool_result

    def test_unknown_tool_handled(self):
        """验证未知工具名不会崩溃。"""
        client = MagicMock()
        client.messages.create.side_effect = [
            MockResponse(
                content=[MockToolUseBlock("unknown_tool", {}, "tu-x")],
                stop_reason="tool_use",
            ),
            MockResponse(
                content=[MockTextBlock("ok")],
                stop_reason="end_turn",
            ),
        ]
        ctx = MockAgentContext(client=client)
        messages = [{"role": "user", "content": "use tool"}]

        result = agent_loop(messages, "system", [], {}, ctx)
        assert result["stop_reason"] == "end_turn"


# ── Tests: run_subagent text extraction ───────────────────────────────

class TestSubagentExtraction:
    """测试 run_subagent 的文本提取逻辑（通过 mock agent_loop）。"""

    def _make_usage(self, stop_reason="end_turn"):
        return {"calls": 1, "tokens_in": 10, "tokens_out": 20, "stop_reason": stop_reason}

    @patch("idea_code.subagent.agent_loop")
    def test_textblock_extracted(self, mock_loop):
        """正常 TextBlock 应被提取返回。"""
        from idea_code.subagent import run_subagent
        mock_loop.return_value = self._make_usage()
        # 让 mock 在 messages 中写入 assistant TextBlock
        def fake_loop(messages, system, tools, handlers, ctx):
            messages.append({
                "role": "assistant",
                "content": [MockTextBlock("正常输出")],
            })
            return self._make_usage()
        mock_loop.side_effect = fake_loop
        ctx = MagicMock()

        text, usage = run_subagent("prompt", "system", ctx)
        assert "正常输出" in text
        assert usage["stop_reason"] == "end_turn"

    @patch("idea_code.subagent.agent_loop")
    def test_thinking_block_no_text(self, mock_loop):
        """仅 ThinkingBlock 时不应返回 (无输出)。mock 场景下由 agent_loop 控制。"""
        from idea_code.subagent import run_subagent
        mock_loop.return_value = self._make_usage()
        ctx = MagicMock()

        text, usage = run_subagent("prompt", "system", ctx)
        # agent_loop mock 不产生 messages → has_content_blocks=False → 无重试
        assert usage["calls"] == 1

    def test_retry_on_thinking_block_only(self):
        """验证 ThinkingBlock-only 响应触发 retry 逻辑。"""
        from idea_code.subagent import run_subagent, _MAX_RETRY_DEPTH
        from idea_code.context import AgentContext

        # 第 1 次调用返回 ThinkingBlock-only
        call_count = 0

        def fake_agent_loop(messages, system, tools, handlers, ctx):
            nonlocal call_count
            call_count += 1
            # 在 messages 中写入 assistant 消息
            if call_count == 1:
                messages.append({
                    "role": "assistant",
                    "content": [MockThinkingBlock()],
                })
                return {"calls": 1, "tokens_in": 10, "tokens_out": 5, "stop_reason": "max_tokens"}
            else:
                messages.append({
                    "role": "assistant",
                    "content": [MockTextBlock("retry success")],
                })
                return {"calls": 1, "tokens_in": 10, "tokens_out": 20, "stop_reason": "end_turn"}

        ctx = AgentContext(client=MagicMock(), model="test", max_tokens=8000)
        with patch("idea_code.subagent.agent_loop", fake_agent_loop):
            text, usage = run_subagent("prompt", "system", ctx)

        assert call_count == 2  # 重试了一次
        assert "retry success" in text
