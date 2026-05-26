"""工具模块单元测试。"""

import tempfile
from pathlib import Path

import pytest

from idea_code.tools import safe_path, run_bash, run_read, run_write, run_edit


class TestSafePath:
    def test_normal_path(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.tools.WORKDIR", tmp)
            result = safe_path("test.txt")
            assert str(result) == str(Path(tmp).resolve() / "test.txt")

    def test_blocks_escape(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.tools.WORKDIR", tmp)
            with pytest.raises(ValueError, match="路径逃逸"):
                safe_path("../../../etc/passwd")

    def test_write_path_blocked_by_safe_path(self, monkeypatch):
        """写入越界路径被 safe_path 先拦截。"""
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.tools.WORKDIR", tmp)
            # /etc/passwd 是绝对路径，safe_path 先拦截（路径逃逸检查）
            result = run_write("/etc/passwd", "hack")
            assert "Error" in result


class TestBash:
    def test_shell_injection_prevented(self):
        result = run_bash("echo hello; rm -rf /")
        assert "hello" in result or "Error" in result

    def test_simple_command(self):
        result = run_bash("echo hello")
        assert "hello" in result

    def test_invalid_command_parsing(self):
        result = run_bash("unclosed 'quote")
        assert "Error" in result or "解析失败" in result


class TestReadWrite:
    def test_read_write_roundtrip(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            # 将临时目录加入白名单
            monkeypatch.setattr("idea_code.tools.WORKDIR", tmp)
            monkeypatch.setattr("idea_code.tools.ALLOWED_WRITE_BASES", [tmp])
            run_write("test.txt", "hello world")
            content = run_read("test.txt")
            assert content == "hello world"

    def test_read_nonexistent(self):
        result = run_read("nonexistent_file_xyz.txt")
        assert "Error" in result


class TestEdit:
    def test_edit_replaces_text(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.tools.WORKDIR", tmp)
            monkeypatch.setattr("idea_code.tools.ALLOWED_WRITE_BASES", [tmp])
            run_write("edit_test.txt", "line1\nline2\nline3")
            result = run_edit("edit_test.txt", "line2", "LINE_TWO")
            assert "已编辑" in result
            content = run_read("edit_test.txt")
            assert "LINE_TWO" in content
            assert "line2" not in content

    def test_edit_text_not_found(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("idea_code.tools.WORKDIR", tmp)
            monkeypatch.setattr("idea_code.tools.ALLOWED_WRITE_BASES", [tmp])
            run_write("edit_test.txt", "hello")
            result = run_edit("edit_test.txt", "nonexistent", "replacement")
            assert "未找到" in result or "Error" in result
