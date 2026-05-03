"""
Content Indexer — SQLite FTS5 全文搜索索引

Inspired by context-mode's ContentStore.

核心理念：
- 原始数据不进入上下文窗口，而是存入 SQLite FTS5 索引
- 通过 BM25 搜索精准召回相关内容
- 对话压缩后，模型可通过搜索找回关键信息

典型场景：
- 索引项目文档、API 参考 → 按需搜索召回
- 索引会话事件（文件编辑、错误、决策） → 恢复上下文
- 索引代码分析结果 → 精准定位
"""

import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# Data classes
# ============================================================

@dataclass
class IndexResult:
    """索引结果"""
    source: str
    chunks_indexed: int
    total_bytes: int
    duration_ms: float
    doc_id: str


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    content: str
    source: str
    rank: float
    highlighted: str = ""


@dataclass
class StoreStats:
    """存储统计"""
    total_documents: int
    total_chunks: int
    total_bytes: int
    sources: dict  # source -> count


# ============================================================
# 分词与查询处理
# ============================================================

# 英文停用词 — 提高 BM25 排名质量
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "has", "his", "how", "its", "may",
    "new", "now", "old", "see", "way", "who", "did", "get", "got", "let",
    "say", "she", "too", "use", "will", "with", "this", "that", "from",
    "they", "been", "have", "many", "some", "them", "than", "each", "make",
    "like", "just", "over", "such", "take", "into", "year", "your", "good",
    "could", "would", "about", "which", "their", "there", "other", "after",
    "should", "through", "also", "more", "most", "only", "very", "when",
    "what", "then", "these", "those", "being", "does", "done", "both",
    "same", "still", "while", "where", "here", "were", "much",
    # 代码相关停用词
    "update", "updates", "updated", "deps", "dev", "tests", "test",
    "add", "added", "fix", "fixed", "run", "running", "using", "import",
    "return", "function", "class", "def", "const", "let", "var",
}


def sanitize_query(query: str, mode: str = "AND") -> str:
    """清理搜索查询，转换为 FTS5 格式"""
    # 移除特殊字符
    words = re.sub(r'["\'(){}[\]*:^~]', ' ', query).split()

    # 去重（不区分大小写）
    seen = set()
    unique = []
    for w in words:
        key = w.lower()
        if key not in seen:
            seen.add(key)
            unique.append(w)

    # 移除停用词
    meaningful = [w for w in unique if w.lower() not in STOPWORDS]
    final = meaningful if meaningful else unique

    if not final:
        return '""'

    joiner = " OR " if mode == "OR" else " "
    return joiner.join(f'"{w}"' for w in final)


def chunk_markdown(content: str, max_chunk_size: int = 2000) -> list[dict]:
    """按标题分块 Markdown 内容，保持代码块完整

    Returns:
        [{"title": str, "content": str, "has_code": bool}, ...]
    """
    chunks = []
    current_title = "Introduction"
    current_lines = []
    in_code_block = False

    for line in content.split("\n"):
        # 检测代码块
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        # 检测标题
        if not in_code_block and line.startswith("#") and not line.startswith("##"):
            # 新的一级标题 — 保存当前块
            if current_lines:
                has_code = any("```" in l for l in current_lines)
                chunks.append({
                    "title": current_title,
                    "content": "\n".join(current_lines),
                    "has_code": has_code,
                })
            current_title = line.lstrip("#").strip()
            current_lines = []
        elif not in_code_block and line.startswith("##"):
            # 二级标题也作为分界点
            if current_lines:
                has_code = any("```" in l for l in current_lines)
                chunks.append({
                    "title": current_title,
                    "content": "\n".join(current_lines),
                    "has_code": has_code,
                })
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

        # 达到最大块大小 — 强制分块
        current_size = sum(len(l) for l in current_lines)
        if current_size > max_chunk_size and not in_code_block:
            has_code = any("```" in l for l in current_lines)
            chunks.append({
                "title": current_title,
                "content": "\n".join(current_lines),
                "has_code": has_code,
            })
            current_lines = []

    # 保存最后一个块
    if current_lines:
        has_code = any("```" in l for l in current_lines)
        chunks.append({
            "title": current_title,
            "content": "\n".join(current_lines),
            "has_code": has_code,
        })

    return chunks


# ============================================================
# ContentIndexer
# ============================================================

class ContentIndexer:
    """基于 SQLite FTS5 的全文搜索索引

    - 按标题分块索引 Markdown/文本内容
    - BM25 排名搜索
    - 支持多种来源（文档、会话事件、代码分析等）
    - 自动去重（基于内容哈希）
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = os.path.expanduser("~/.openllm/sandbox")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "content_index.db")

        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                title,
                content,
                source,
                label,
                content_type,
                tokenize='unicode61'
            );

            CREATE TABLE IF NOT EXISTS content_meta (
                doc_id TEXT PRIMARY KEY,
                source TEXT,
                label TEXT,
                content_type TEXT,
                content_hash TEXT,
                total_bytes INTEGER,
                chunks_count INTEGER,
                indexed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_meta_source ON content_meta(source);
            CREATE INDEX IF NOT EXISTS idx_meta_hash ON content_meta(content_hash);
        """)
        conn.commit()

    def index_text(
        self,
        source: str,
        content: str,
        label: str = "",
        content_type: str = "text",
        chunk_size: int = 2000,
    ) -> IndexResult:
        """索引文本内容

        Args:
            source: 来源标识（如文件名、URL、会话 ID）
            content: 文本内容
            label: 可选标签
            content_type: 内容类型 (text, markdown, code, session_event)
            chunk_size: 分块大小

        Returns:
            IndexResult
        """
        start = time.monotonic()

        # 生成文档 ID
        content_hash = hashlib.md5(content.encode()).hexdigest()
        doc_id = f"{source}:{content_hash[:8]}"

        # 检查是否已存在
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT doc_id FROM content_meta WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if existing:
            return IndexResult(
                source=source,
                chunks_indexed=0,
                total_bytes=len(content),
                duration_ms=(time.monotonic() - start) * 1000,
                doc_id=doc_id,
            )

        # 分块
        if content_type in ("markdown", "text"):
            chunks = chunk_markdown(content, max_chunk_size=chunk_size)
        else:
            chunks = [{"title": label or source, "content": content, "has_code": False}]

        # 插入 FTS5 索引
        cursor = conn.cursor()
        chunks_count = 0
        for chunk in chunks:
            cursor.execute(
                "INSERT INTO content_fts(title, content, source, label, content_type) VALUES (?, ?, ?, ?, ?)",
                (chunk["title"], chunk["content"], source, label or "", content_type),
            )
            chunks_count += 1

        # 保存元数据
        cursor.execute(
            "INSERT INTO content_meta(doc_id, source, label, content_type, content_hash, total_bytes, chunks_count, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, source, label or "", content_type, content_hash, len(content), chunks_count, time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()

        return IndexResult(
            source=source,
            chunks_indexed=chunks_count,
            total_bytes=len(content),
            duration_ms=(time.monotonic() - start) * 1000,
            doc_id=doc_id,
        )

    def search(
        self,
        query: str,
        source: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 10,
        mode: str = "OR",
    ) -> list[SearchResult]:
        """BM25 搜索

        Args:
            query: 搜索查询
            source: 可选来源过滤
            content_type: 可选内容类型过滤
            limit: 返回结果数量
            mode: 搜索模式 (AND/OR)

        Returns:
            搜索结果列表（按 BM25 排名排序）
        """
        sanitized = sanitize_query(query, mode=mode)
        if sanitized == '""':
            return []

        conn = self._get_conn()

        # 构建查询
        sql = """
            SELECT title, content, source, label, rank,
                   highlight(content_fts, 0, '<b>', '</b>') as highlighted_title,
                   highlight(content_fts, 1, '<b>', '</b>') as highlighted_content
            FROM content_fts
            WHERE content_fts MATCH ?
        """
        params = [sanitized]

        if source:
            sql += " AND source = ?"
            params.append(source)

        if content_type:
            sql += " AND content_type = ?"
            params.append(content_type)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            results.append(SearchResult(
                title=row[0],
                content=row[1][:1000],  # 限制内容长度
                source=row[2],
                rank=row[4],
                highlighted=row[5] or row[0],
            ))

        return results

    def search_by_source(
        self,
        source: str,
        limit: int = 20,
    ) -> list[SearchResult]:
        """按来源检索所有内容"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT title, content, source, label FROM content_fts WHERE source = ? LIMIT ?",
            (source, limit),
        ).fetchall()

        return [
            SearchResult(
                title=r[0], content=r[1][:1000], source=r[2], rank=0.0,
            )
            for r in rows
        ]

    def get_stats(self) -> StoreStats:
        """获取存储统计"""
        conn = self._get_conn()

        total_docs = conn.execute("SELECT COUNT(*) FROM content_meta").fetchone()[0]
        total_chunks = conn.execute("SELECT COUNT(*) FROM content_fts").fetchone()[0]
        total_bytes = conn.execute("SELECT COALESCE(SUM(total_bytes), 0) FROM content_meta").fetchone()[0]

        sources = {}
        for row in conn.execute("SELECT source, COUNT(*) FROM content_meta GROUP BY source"):
            sources[row[0]] = row[1]

        return StoreStats(
            total_documents=total_docs,
            total_chunks=total_chunks,
            total_bytes=total_bytes,
            sources=sources,
        )

    def delete_by_source(self, source: str) -> int:
        """删除指定来源的所有内容"""
        conn = self._get_conn()
        # 先获取所有 doc_id
        doc_ids = [r[0] for r in conn.execute(
            "SELECT doc_id FROM content_meta WHERE source = ?", (source,)
        ).fetchall()]

        if not doc_ids:
            return 0

        # 删除元数据
        conn.execute("DELETE FROM content_meta WHERE source = ?", (source,))

        # 删除 FTS 条目（通过 source 过滤）
        conn.execute("DELETE FROM content_fts WHERE source = ?", (source,))
        conn.commit()

        return len(doc_ids)

    def purge(self) -> int:
        """清除所有内容"""
        conn = self._get_conn()
        conn.execute("DELETE FROM content_fts")
        conn.execute("DELETE FROM content_meta")
        conn.commit()
        return 0

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
