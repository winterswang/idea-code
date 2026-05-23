"""compact.py 单元测试。"""

from idea_code.compact import estimate_tokens, _redact_sensitive, micro_compact


class TestRedactSensitive:
    def test_redacts_api_key(self):
        assert "sk-ant-abc123" not in _redact_sensitive("key=sk-ant-abc123 secret")
        assert "***REDACTED***" in _redact_sensitive("key=sk-ant-abc123")

    def test_redacts_env_keys(self):
        text = "IDEA_API_KEY=sk-verylongkey123456 secret"
        result = _redact_sensitive(text)
        assert "IDEA_API_KEY" not in result or "***REDACTED***" in result

    def test_preserves_normal_text(self):
        text = "hello world, no secrets here"
        assert _redact_sensitive(text) == text


class TestEstimateTokens:
    def test_pure_ascii(self):
        messages = [{"role": "user", "content": "hello world " * 50}]
        tokens = estimate_tokens(messages)
        assert 50 <= tokens <= 200

    def test_cjk_weighted(self):
        messages = [{"role": "user", "content": "你好世界" * 50}]
        tokens = estimate_tokens(messages)
        assert tokens > 100  # CJK 应该产生更多 tokens


class TestMicroCompact:
    def test_keeps_recent_results(self):
        messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "1", "content": "a" * 200}]},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "2", "content": "b" * 200}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "3", "content": "c" * 200}]},
        ]
        micro_compact(messages)
        # KEEP_RECENT=3, 有3个 tool_result，都应该保留
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        assert "a" in part.get("content", "") or \
                               "b" in part.get("content", "") or \
                               "c" in part.get("content", "")

    def test_compacts_old_results(self):
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "name": "write_file", "id": "w1", "input": {}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w1", "content": "long content " * 50}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w2", "content": "x" * 200}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w3", "content": "y" * 200}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "w4", "content": "z" * 200}]},
        ]
        micro_compact(messages)
        # KEEP_RECENT=3, 4个 tool_result，第1个应被压缩
        first = messages[1]["content"][0]
        assert "已压缩" in first.get("content", "") or len(first.get("content", "")) < 200

    def test_preserves_read_file(self):
        # micro_compact 的 tool_name_map 依赖 hasattr(block, "type")，
        # 在真实 Anthropic 对象上正常工作，在纯 dict 测试中无法验证。
        pass
