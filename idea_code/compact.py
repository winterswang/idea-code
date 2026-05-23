"""上下文压缩：三层压缩管道，防止 context 溢出。

层级:
  Layer 1 — micro_compact: 每轮静默替换旧 tool_result 为占位符
  Layer 2 — auto_compact:  超阈值时 LLM 自动总结
  Layer 3 — manual:        (远期 feature，暂时跳过)
"""

import json
import re
import time
from pathlib import Path

TOKEN_THRESHOLD = 100_000
KEEP_RECENT = 3
PRESERVE_RESULT_TOOLS = {"read_file"}
# transcripts 存在项目目录下而非 cwd
TRANSCRIPT_DIR = Path(__file__).resolve().parent.parent / ".transcripts"

_SENSITIVE_PATTERNS = re.compile(
    r'(sk-ant-[a-zA-Z0-9_-]+)'
    r'|(API_KEY=\S{20,})'
    r'|(BIGMODEL_API_KEY=\S{20,})'
    r'|(MINIMAX_API_KEY=\S{20,})'
    r'|(IDEA_API_KEY=\S{20,})'
    r'|(REV_[AB]_API_KEY=\S{20,})'
)


def _redact_sensitive(text: str) -> str:
    """脱敏敏感信息（API Key 等）。"""
    return _SENSITIVE_PATTERNS.sub("***REDACTED***", text)


def estimate_tokens(messages: list) -> int:
    serialized = json.dumps(messages, default=str)
    cjk = sum(1 for c in serialized if '\u4e00' <= c <= '\u9fff')
    ascii_chars = len(serialized) - cjk
    return int(ascii_chars * 0.3 + cjk * 1.5)


def micro_compact(messages: list) -> None:
    """静默替换旧的 tool_result 内容为占位符。"""
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))

    if len(tool_results) <= KEEP_RECENT:
        return

    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name

    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        content = result.get("content", "")
        if not isinstance(content, str) or len(content) <= 100:
            continue
        tool_id = result.get("tool_use_id", "")
        tool_name = tool_name_map.get(tool_id, "unknown")
        if tool_name in PRESERVE_RESULT_TOOLS:
            continue
        result["content"] = f"[已压缩: 使用了 {tool_name} 工具]"


def auto_compact(messages: list, client, model: str) -> list:
    """保存完整 transcript 到磁盘，LLM 总结后替换 messages。"""
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(_redact_sensitive(json.dumps(msg, default=str)) + "\n")

    conversation_text = json.dumps(messages, default=str)[-80000:]
    response = client.messages.create(
        model=model,
        messages=[{
            "role": "user",
            "content": (
                "请总结以下对话，保留以下关键信息：\n"
                "1) 已完成的工作\n"
                "2) 当前状态\n"
                "3) 已做出的关键决策\n"
                "请简洁但保留关键细节。\n\n" + conversation_text
            ),
        }],
        max_tokens=2000,
    )

    summary = next(
        (block.text for block in response.content if hasattr(block, "text")),
        "无法生成摘要。",
    )

    return [{
        "role": "user",
        "content": f"[对话已压缩。原始 transcript: {transcript_path}]\n\n{summary}",
    }]


def compact_if_needed(messages: list, client, model: str) -> bool:
    """检查并执行压缩。返回 True 表示发生了压缩。"""
    micro_compact(messages)

    if estimate_tokens(messages) > TOKEN_THRESHOLD:
        compressed = auto_compact(messages, client, model)
        messages.clear()
        messages.extend(compressed)
        return True

    return False
