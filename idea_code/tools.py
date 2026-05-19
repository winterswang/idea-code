"""基础工具：bash / read_file / write_file / edit_file / web_search。"""

import shlex
import subprocess
from pathlib import Path

from .config import WORKDIR


def safe_path(path: str) -> Path:
    p = Path(WORKDIR) / path
    resolved = p.resolve()

    # 路径逃逸检查
    if not str(resolved).startswith(str(Path(WORKDIR).resolve())):
        raise ValueError(f"路径逃逸被阻止: {path}")

    # 符号链接攻击检查：路径中任何组件是 symlink 则拒绝
    check = Path(WORKDIR)
    for part in p.relative_to(WORKDIR).parts:
        check = check / part
        if check.is_symlink():
            raise ValueError(f"符号链接被阻止: {path}")

    return resolved


def run_bash(command: str) -> str:
    """执行 shell 命令。

    使用 shell=False + shlex.split 防止命令注入。
    不支持管道和重定向，仅支持单命令执行。
    """
    try:
        args = shlex.split(command)
    except ValueError as e:
        return f"Error: 命令解析失败 - {e}"

    if not args:
        return "Error: 空命令"

    try:
        result = subprocess.run(
            args, shell=False, cwd=WORKDIR,
            capture_output=True, text=True, timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return "Error: 命令超时 (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... (还有 {len(lines) - limit} 行)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"已写入 {len(content)} 字节到 {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text(encoding="utf-8")
        if old_text not in content:
            return f"Error: 在 {path} 中未找到要替换的文本"
        fp.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        return f"已编辑 {path}"
    except Exception as e:
        return f"Error: {e}"


def run_web_search(query: str, max_results: int = 5) -> str:
    """Web search. Backend selected by SEARCH_PROVIDER env var.

    Supported: bigmodel (default), minimax (requires mmx-cli).
    Falls back gracefully when no API key configured.
    """
    import os
    provider = os.getenv("SEARCH_PROVIDER", "bigmodel")

    if provider == "minimax":
        result = _search_via_minimax_cli(query, max_results)
    else:
        result = _search_via_bigmodel(query, max_results)

    # 退化提示：两个后端都不可用时，告知 Builder 可降级运行
    if result.startswith("Error:"):
        return (
            f"{result}\n\n"
            "⚠️  搜索功能当前不可用（未配置 API Key）。你可以基于训练数据中的知识继续工作，"
            "但在输出中应明确标注「以下信息来自模型预训练知识，未经验证」。"
        )
    return result


def _search_via_bigmodel(query: str, max_results: int) -> str:
    import json
    import os
    import urllib.request
    import uuid

    api_key = os.getenv("BIGMODEL_API_KEY", "")
    api_url = "https://open.bigmodel.cn/api/paas/v4/web_search"
    if not api_key:
        return "Error: 未配置 BIGMODEL_API_KEY。请在 .env 中设置。"

    body = json.dumps({
        "search_query": query,
        "search_engine": "search_std",
        "search_intent": False,
        "count": max(1, min(max_results, 10)),
        "search_domain_filter": "",
        "search_recency_filter": "noLimit",
        "content_size": "medium",
        "request_id": str(uuid.uuid4()),
        "user_id": "idea-code",
    }).encode()

    try:
        req = urllib.request.Request(
            api_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        results = data.get("search_result", data.get("data", []))
        if not results:
            return f"No results for: {query}"

        lines = [f"Search: {query}\n"]
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "")
            link = r.get("link", "")
            content = r.get("content", "")
            media = r.get("media", "")
            date = r.get("publish_date", "")

            lines.append(f"{i}. {title}")
            if media or date:
                meta = " · ".join(filter(None, [media, date]))
                lines.append(f"   来源: {meta}")
            lines.append(f"   URL: {link}")
            if content:
                lines.append(f"   {content[:500]}")
            lines.append("")
        return "\n".join(lines)

    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return f"Error: BigModel search failed (HTTP {e.code}) - {body[:300]}"
    except Exception as e:
        return f"Error: BigModel search failed - {e}"

def _search_via_minimax_cli(query: str, max_results: int) -> str:
    """Search via MiniMax CLI (mmx search query)."""
    import json
    import os
    import subprocess
    import shutil

    if not shutil.which("mmx"):
        return "Error: mmx CLI not found. Install: npm install -g mmx-cli && mmx auth login"

    api_key = os.getenv("MINIMAX_API_KEY", "")
    cmd = ["mmx", "search", "query", query, "--output", "json", "--quiet"]
    if api_key:
        cmd.extend(["--api-key", api_key])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"Error: MiniMax search failed - {result.stderr[:300]}"

        data = json.loads(result.stdout)
        results = data.get("organic", [])
        if not results:
            return f"No results for: {query}"

        lines = [f"Search: {query} (via MiniMax)\n"]
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "")
            link = r.get("link", "")
            snippet = r.get("snippet", "")
            date = r.get("date", "")

            lines.append(f"{i}. {title}")
            if date:
                lines.append(f"   日期: {date}")
            lines.append(f"   URL: {link}")
            if snippet:
                lines.append(f"   {snippet[:500]}")
            lines.append("")
        return "\n".join(lines)

    except json.JSONDecodeError:
        return f"Error: MiniMax returned non-JSON output - {result.stdout[:300]}"
    except subprocess.TimeoutExpired:
        return "Error: MiniMax search timed out (30s)"
    except Exception as e:
        return f"Error: MiniMax search failed - {e}"


TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "web_search": lambda **kw: run_web_search(kw["query"], kw.get("max_results", 5)),
}

TOOLS = [
    {
        "name": "bash",
        "description": "执行 shell 命令",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "读取文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "写入文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "替换文件中的精确文本（首次匹配）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "web_search",
        "description": "搜索互联网获取最新信息。返回标题、URL、来源和摘要。在需要最新数据、事实验证或补充信息时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最大返回结果数（默认 5）"},
            },
            "required": ["query"],
        },
    },
]
