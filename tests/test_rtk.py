"""RTK 压缩器边界条件测试"""
from __future__ import annotations

import json

from openllm.optimize.rtk import RtkCompressor

class TestRtkCompressor:
    def setup_method(self):
        self.c = RtkCompressor()

    def test_empty_content(self):
        assert self.c.compress("") == ""
        assert self.c.compress(None) is None

    def test_git_diff_detection(self):
        content = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 hello
-world
+world2
+new line"""
        result = self.c.compress(content)
        assert "diff --git" in result
        assert "world" in result  # removed line
        assert "world2" in result  # added line

    def test_git_diff_aggressive_removes_context(self):
        """aggressive 模式下上下文行（无 +/- 前缀）应该被移除"""
        content = """diff --git a/f.py b/f.py
--- a/f.py
+++ b/f.py
@@ -1,5 +1,6 @@
 context_line_1
 context_line_2
-old_line
+new_line
 context_line_3"""
        result = self.c.compress(content, mode="aggressive")
        assert "context_line_1" not in result, "aggressive 模式应移除上下文行"
        assert "context_line_2" not in result
        assert "context_line_3" not in result
        assert "old_line" in result
        assert "new_line" in result

    def test_grep_detection(self):
        content = """file1.py:10:def hello():
file2.py:20:    print("world")
-- separator --"""
        result = self.c.compress(content)
        assert "file1.py:10" in result
        assert "-- separator --" not in result, "分隔符应被移除"

    def test_grep_ultra_truncation(self):
        """ultra 模式只保留前 100 行"""
        lines = [f"file{i}.py:{i}:content_{i}" for i in range(200)]
        content = "\n".join(lines)
        result = self.c.compress(content, mode="ultra")
        result_lines = result.split("\n")
        assert len(result_lines) <= 100, f"ultra 模式应限制在 100 行以内，实际 {len(result_lines)}"

    def test_grep_deduplication(self):
        content = """a.py:1:hello
b.py:2:hello
c.py:3:world"""
        result = self.c.compress(content)
        # 内容相同的行应该去重（但文件路径保留）
        assert "a.py:1:hello" in result
        assert "b.py:2:hello" in result  # 不同文件不被去重

    def test_tree_detection(self):
        content = """src/
├── main.py
│   └── helper.py"""
        result = self.c.compress(content)
        assert "src/" in result
        # 树形装饰字符应该被移除
        assert "├──" not in result

    def test_log_detection_with_202_prefix(self):
        """P2: 以 '202' 开头的日志检测——容易误判其他内容"""
        content = "2024-01-01 10:00:00 INFO starting\n" * 50
        result = self.c.compress(content)
        # 应被识别为日志
        assert "[RTK]" in result or len(result.split("\n")) < 50

    def test_log_false_positive(self):
        """P2: 风险——非日志内容包含 '202' 可能被误判为日志"""
        # git diff 可能包含 "202" 在行号或内容中
        content = "diff --git a/2023_report.py b/2024_report.py\n" * 30
        result = self.c.compress(content)
        # 应该被检测为 git_diff，而不是 log
        assert "diff --git" in result

    def test_json_detection(self):
        content = '{"key": "value", "list": [1, 2, 3]}'
        result = self.c.compress(content, mode="aggressive")
        import json
        parsed = json.loads(result)  # 应该能解析
        assert parsed["key"] == "value"

    def test_json_array_truncation_aggressive(self):
        """aggressive 模式下 JSON 数组只保留前 20 项"""
        data = [{"id": i} for i in range(100)]
        content = json.dumps(data)
        result = self.c.compress(content, mode="aggressive")
        parsed = json.loads(result)
        assert len(parsed) <= 20

    def test_json_array_truncation_ultra(self):
        """ultra 模式下 JSON 数组只保留前 5 项"""
        data = [{"id": i} for i in range(100)]
        content = json.dumps(data)
        result = self.c.compress(content, mode="ultra")
        parsed = json.loads(result)
        assert len(parsed) <= 5

    def test_json_malformed_fallback(self):
        """格式错误的 JSON 应该走通用压缩"""
        content = "{not json"
        result = self.c.compress(content)
        assert result is not None

    def test_generic_dedup_empty_lines(self):
        content = "line1\n\n\n\nline2"
        result = self.c.compress(content)
        assert "line1" in result
        assert "line2" in result
        # 连续空行应该被压缩
        assert result.count("\n") <= 2

    def test_generic_truncation_standard(self):
        lines = [f"line{i}" for i in range(300)]
        content = "\n".join(lines)
        result = self.c.compress(content, mode="standard")
        result_lines = result.split("\n")
        assert len(result_lines) <= 150, "standard 模式应限制在 150 行"

    def test_unknown_type_preserves_content(self):
        content = "just some random text\nwith multiple lines\n"
        result = self.c.compress(content)
        assert "just some random text" in result

