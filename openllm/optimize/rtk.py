"""RTK (Real-Time Token Saver) — 工具输出压缩

自动检测工具输出类型（git diff / grep / ls / log / code），
应用最佳压缩策略，在不丢失关键信息的前提下最大化 token 节省。

参考：9router RTK (20-40%节省) / OmniRoute RTK (60-90%节省)
"""

from __future__ import annotations

import re


class RtkCompressor:
    """RTK 工具输出压缩器
    
    用法:
        compressor = RtkCompressor()
        compressed = compressor.compress(tool_output, mode="standard")
    """
    
    MODES = ["lite", "standard", "aggressive", "ultra"]
    
    def compress(self, content: str, mode: str = "standard") -> str:
        """压缩工具输出
        
        Args:
            content: 原始工具输出
            mode: lite(保守) / standard(默认) / aggressive(激进) / ultra(极限)
        
        Returns:
            压缩后的文本
        """
        if not content:
            return content
        
        lines = content.split("\n")
        content_type = self._detect_type(lines)
        
        if content_type == "git_diff":
            return self._compress_git_diff(content, mode)
        elif content_type == "grep":
            return self._compress_grep(content, mode)
        elif content_type == "tree_ls":
            return self._compress_tree(content, mode)
        elif content_type == "log":
            return self._compress_log(content, mode)
        elif content_type == "json":
            return self._compress_json(content, mode)
        else:
            return self._compress_generic(content, mode)
    
    def _detect_type(self, lines: list[str]) -> str:
        """检测输出类型"""
        if not lines:
            return "unknown"
        
        joined = "\n".join(lines[:20])
        
        # git diff
        if re.search(r"^diff --git|^index |^--- |^\+\+\+ ", joined, re.MULTILINE):
            return "git_diff"
        # grep
        if re.search(r"^.+:\d+:", joined, re.MULTILINE):
            return "grep"
        # tree/ls
        if re.search(r"^[│├└ ]+", joined, re.MULTILINE):
            return "tree_ls"
        if re.search(r"^[drwx-]{10}", joined, re.MULTILINE):
            return "tree_ls"
        # JSON array/object at start
        if joined.strip().startswith("[") or joined.strip().startswith("{"):
            return "json"
        # log
        log_keywords = ["error", "warn", "info", "trace", "debug", "202"]
        if any(k in joined[:500].lower() for k in log_keywords) and len(lines) > 20:
            return "log"
        
        return "unknown"
    
    def _compress_git_diff(self, content: str, mode: str) -> str:
        """压缩 git diff — 保留文件头+变更行，去掉上下文"""
        lines = content.split("\n")
        kept = []
        current_file = ""
        skip_ctx = mode in ("aggressive", "ultra")
        
        for line in lines:
            if line.startswith("diff --git"):
                if current_file and kept:
                    kept.append("")
                current_file = re.sub(r"^diff --git a/", "", line).split()[0]
                kept.append(line)
            elif line.startswith("---") or line.startswith("+++"):
                kept.append(line)
            elif line.startswith("@@"):
                kept.append(line)
            elif line.startswith("+") or line.startswith("-"):
                kept.append(line)
            elif skip_ctx:
                continue  # aggressive/ultra 模式去掉上下文行
            else:
                kept.append(line)
        
        return "\n".join(kept)
    
    def _compress_grep(self, content: str, mode: str) -> str:
        """压缩 grep 输出 — 保留匹配行，去掉分隔符"""
        lines = content.split("\n")
        kept = []
        seen = set()

        for line in lines:
            if not line.strip() or line.startswith("--"):
                continue
            # grep 格式: filename:line_number:content
            m = re.match(r"^(.+?:\d+:)(.*)", line)
            if m:
                file_part = m.group(1)  # filename:line_number:
                content_part = m.group(2).strip()
                # 用 file_part + content_part 去重，保留文件上下文
                dedup_key = f"{file_part}{content_part}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    kept.append(line)
            elif line not in seen:
                seen.add(line)
                kept.append(line)
        
        if mode == "ultra":
            return "\n".join(kept[:100])  # 极限模式只保留前100行
        return "\n".join(kept)
    
    def _compress_tree(self, content: str, mode: str) -> str:
        """压缩目录树 — 只保留路径，去掉装饰字符"""
        lines = content.split("\n")
        kept = []
        
        for line in lines:
            # 去掉树形装饰字符
            cleaned = re.sub(r"[│├└─ +|]", " ", line)
            cleaned = re.sub(r" +", " ", cleaned).strip()
            if cleaned:
                kept.append(cleaned)
            elif mode != "ultra":
                kept.append("")
        
        return "\n".join(kept)
    
    def _compress_log(self, content: str, mode: str) -> str:
        """压缩日志 — 保留尾部+错误行"""
        lines = content.split("\n")
        
        # 保留最后 N 行
        if mode == "lite":
            tail = 50
        elif mode == "standard":
            tail = 30
        elif mode == "aggressive":
            tail = 20
        else:
            tail = 10
        
        result = lines[-tail:] if len(lines) > tail else lines
        
        # 在前面加上错误行摘要
        errors = [line for line in lines if any(k in line.lower() for k in ["error", "exception", "traceback", "fail"])]
        if errors and len(lines) > tail:
            summary = f"[RTK] Log compressed: {len(lines)} lines → {len(result)} lines. Errors found: {len(errors)}"
            result = [summary] + result
        
        return "\n".join(result)
    
    def _compress_json(self, content: str, mode: str) -> str:
        """压缩 JSON — 压缩为单行（aggressive+）或截断数组"""
        import json
        try:
            data = json.loads(content)
            if isinstance(data, list) and mode in ("aggressive", "ultra"):
                cap = 20 if mode == "aggressive" else 5
                data = data[:cap]
            # 压缩为单行
            return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        except json.JSONDecodeError:
            return self._compress_generic(content, mode)
    
    def _compress_generic(self, content: str, mode: str) -> str:
        """通用压缩 — 去重复空行+行号+截断"""
        lines = content.split("\n")
        
        # 去重复空行
        kept = []
        prev_empty = False
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue
            prev_empty = is_empty
            kept.append(line)
        
        # aggressive/ultra 截断长度
        max_lines = {"lite": 200, "standard": 150, "aggressive": 100, "ultra": 50}
        limit = max_lines.get(mode, 150)
        
        if len(kept) > limit:
            kept = kept[:limit - 1]
            kept.append(f"[RTK] Output truncated from {len(lines)} to {limit - 1} lines")
        
        return "\n".join(kept)
