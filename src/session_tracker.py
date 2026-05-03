"""
Session Event Tracker — 结构化会话事件追踪与精准召回

Inspired by context-mode's session event extraction + SQLite FTS5.

核心理念：
- 对话上下文压缩后，LLM 不会忘记关键信息
- 用规则提取结构化事件（文件操作、错误、工具调用、用户决策）
- 事件存入 SQLite FTS5，通过 BM25 搜索精准召回
- 零 LLM 成本提取，替代昂贵的 LLM 摘要

事件分类体系：
- P0 (critical): 文件编辑、规则文件读取、用户指令
- P1 (important): 工具调用结果、错误/异常、git 操作
- P2 (contextual): 任务变更、环境变量、子代理
- P3 (informational): 一般对话、工具调用请求
"""

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Data classes
# ============================================================

@dataclass
class SessionEvent:
    """结构化会话事件"""
    event_id: str
    session_id: str
    event_type: str        # file_read, file_write, error, tool_call, decision, git, task
    category: str          # file, error, tool, decision, git, task
    data: str              # 完整数据（不截断，存入 FTS5）
    summary: str           # 摘要（用于快速预览）
    priority: int          # 1=critical, 2=important, 3=contextual, 4=informational
    timestamp: str         # ISO 格式时间
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "category": self.category,
            "data": self.data,
            "summary": self.summary,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class RecallResult:
    """上下文召回结果"""
    events: list[SessionEvent]
    total_found: int
    query: str
    context_tokens_saved: int  # 预估节省的 token 数
    recall_mode: str           # "search" | "recent" | "full"


# ============================================================
# 事件提取器 — 纯函数，零副作用
# ============================================================

class EventExtractor:
    """从消息中提取结构化事件

    基于规则的模式匹配，零 LLM 成本。
    支持 13 种事件类型。
    """

    # 文件操作模式
    FILE_PATTERNS = {
        "file_read": [
            re.compile(r"读取[了]?[文件]?\s*[`'「]([^`'」]+)[`'」]", re.IGNORECASE),
            re.compile(r"read(?:ing)?\s+(?:the\s+)?(?:file\s+)?[`'\"#]([^`'\"#\n]+)[`'\"#]", re.IGNORECASE),
            re.compile(r"查看[了]?\s*[`'「]([^`'」]+)[`'」]", re.IGNORECASE),
        ],
        "file_write": [
            re.compile(r"写入[了]?[文件]?\s*[`'「]([^`'」]+)[`'」]", re.IGNORECASE),
            re.compile(r"wrote\s+(?:to\s+)?(?:the\s+)?(?:file\s+)?[`'\"#]([^`'\"#\n]+)[`'\"#]", re.IGNORECASE),
            re.compile(r"创建[了]?[文件]?\s*[`'「]([^`'」]+)[`'」]", re.IGNORECASE),
            re.compile(r"修改[了]?[文件]?\s*[`'「]([^`'」]+)[`'」]", re.IGNORECASE),
            re.compile(r"(?:created|edited|updated|modified)\s+(?:the\s+)?(?:file\s+)?[`'\"#]([^`'\"#\n]+)[`'\"#]", re.IGNORECASE),
        ],
    }

    # 错误模式（更精确 — 要求是实际的错误类型或错误消息）
    ERROR_PATTERNS = [
        # Python Traceback 和异常
        re.compile(r"Traceback\s*\(most recent call last\)", re.IGNORECASE),
        re.compile(r"(\w+Error|Exception):\s*(.+?)(?:\n|$)"),
        # 错误消息格式
        re.compile(r"(?:^|\n)\s*(Error|ERROR|FAILED|FATAL)[:\s]+(.+?)(?:\n|$)", re.MULTILINE),
        # 文件不存在错误
        re.compile(r"FileNotFoundError.*?:\s*(.+)", re.IGNORECASE),
        re.compile(r"No such file or directory", re.IGNORECASE),
        # 中文错误
        re.compile(r"(?:^|\n)\s*错误[：:]\s*(.+?)(?:\n|$)", re.MULTILINE),
    ]

    # 工具调用模式
    TOOL_PATTERNS = [
        re.compile(r"(?:调用|使用|执行|using|calling)\s+(?:工具|tool|命令|command)?\s*[`'「]([^`'」]+)[`'」]", re.IGNORECASE),
        re.compile(r"tool[:\s]+(\w+)", re.IGNORECASE),
    ]

    # Git 操作模式
    GIT_PATTERNS = [
        re.compile(r"git\s+(commit|push|pull|merge|checkout|branch|rebase|stash)\s*(.*)", re.IGNORECASE),
        re.compile(r"提交[了]?[代码]?(?:到)?\s*(\w+)\s*(?:分支)?", re.IGNORECASE),
    ]

    # 用户决策模式
    DECISION_PATTERNS = [
        re.compile(r"(?:决定|选择|采用|使用)\s*[`'「]?([^`'」\n]{5,100})[`'」]?", re.IGNORECASE),
        re.compile(r"(?:let|decided to|chose to|going with)\s+([^\n]{5,100})", re.IGNORECASE),
    ]

    # 规则文件（被读取时会触发 P0 事件）
    RULE_FILES = {
        "CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md", "KIRO.md",
        "copilot-instructions.md", "context-mode.mdc",
        ".hermes/", "memory", ".claude/", ".codex/",
    }

    def extract_from_message(self, message: dict, session_id: str) -> list[SessionEvent]:
        """从单条消息中提取事件

        Args:
            message: {"role": "user|assistant|system", "content": "..."}
            session_id: 会话 ID

        Returns:
            提取到的事件列表
        """
        events = []
        role = message.get("role", "")
        content = message.get("content", "")

        if not content or len(content) < 5:
            return events

        ts = datetime.now().isoformat()

        # 1. 文件操作事件
        events.extend(self._extract_file_events(content, role, session_id, ts))

        # 2. 错误事件
        events.extend(self._extract_error_events(content, role, session_id, ts))

        # 3. 工具调用事件
        events.extend(self._extract_tool_events(content, role, session_id, ts))

        # 4. Git 操作事件
        events.extend(self._extract_git_events(content, role, session_id, ts))

        # 5. 用户决策事件
        events.extend(self._extract_decision_events(content, role, session_id, ts))

        # 6. 规则文件读取事件（P0）
        events.extend(self._extract_rule_events(content, role, session_id, ts))

        return events

    def extract_from_messages(self, messages: list[dict], session_id: str) -> list[SessionEvent]:
        """从多条消息中提取所有事件"""
        all_events = []
        for msg in messages:
            events = self.extract_from_message(msg, session_id)
            all_events.extend(events)
        return all_events

    def _make_event_id(self, session_id: str, event_type: str, data: str) -> str:
        """生成唯一事件 ID"""
        raw = f"{session_id}:{event_type}:{data[:200]}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _extract_file_events(self, content: str, role: str, session_id: str, ts: str) -> list[SessionEvent]:
        """提取文件操作事件"""
        events = []

        for event_type, patterns in self.FILE_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(content):
                    file_path = match.group(1).strip()
                    if len(file_path) < 2:
                        continue

                    priority = 1  # 文件操作 = critical
                    summary = f"{role} {event_type}: `{file_path}`"

                    events.append(SessionEvent(
                        event_id=self._make_event_id(session_id, event_type, file_path),
                        session_id=session_id,
                        event_type=event_type,
                        category="file",
                        data=f"{event_type}: {file_path}\nContext: {content[:500]}",
                        summary=summary,
                        priority=priority,
                        timestamp=ts,
                        metadata={"file_path": file_path, "role": role},
                    ))

        return events

    def _extract_error_events(self, content: str, role: str, session_id: str, ts: str) -> list[SessionEvent]:
        """提取错误事件"""
        events = []

        for pattern in self.ERROR_PATTERNS:
            for match in pattern.finditer(content):
                error_detail = match.group(0).strip()
                if len(error_detail) < 5:
                    continue

                # 排除自然语言中的"error"（如 "there is an error", "the error is"）
                # 真实错误通常是：Type 开头（FileNotFoundError）、Traceback、或大写的 ERROR
                if not (
                    "Error:" in error_detail or
                    "ERROR" in error_detail or
                    "Traceback" in error_detail or
                    "FAILED" in error_detail or
                    "FATAL" in error_detail or
                    "FileNotFoundError" in error_detail or
                    "No such file" in error_detail or
                    error_detail.startswith("Error") or
                    "错误：" in error_detail or
                    "错误:" in error_detail
                ):
                    continue

                events.append(SessionEvent(
                    event_id=self._make_event_id(session_id, "error", error_detail),
                    session_id=session_id,
                    event_type="error",
                    category="error",
                    data=error_detail,
                    summary=f"Error: {error_detail[:100]}",
                    priority=1,  # 错误 = critical
                    timestamp=ts,
                    metadata={"role": role},
                ))
                break  # 每种模式只取第一个

        return events

    def _extract_tool_events(self, content: str, role: str, session_id: str, ts: str) -> list[SessionEvent]:
        """提取工具调用事件"""
        events = []

        # 检测代码块中的工具调用
        code_blocks = re.findall(r"```(\w+)?\n(.*?)```", content, re.DOTALL)
        for lang, block in code_blocks[:5]:
            # 只从 shell/bash 代码块中提取命令
            if lang and lang.lower() not in ("bash", "sh", "shell", "zsh", "console", ""):
                continue

            # 检测 shell 命令
            # 排除 Python/JS 代码行（包含 def, class, function, const, import, var, let）
            skip_patterns = re.compile(r"^\s*(def |class |function |const |let |var |import |from |export |return |if |elif |else |for |while |try |except |with |async |await )", re.IGNORECASE)

            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                if skip_patterns.match(line):
                    continue

                # 只提取看起来像 shell 命令的行
                shell_match = re.match(r"^([a-z][\w./-]+(?:\s+[\w./\"'=-]+)*)", line)
                if shell_match:
                    cmd = shell_match.group(1).strip()
                    if len(cmd) < 3:
                        continue
                    # 排除看起来像 Python/JS 标识符的
                    if any(kw in cmd for kw in ["def ", "class ", "function"]):
                        continue

                    events.append(SessionEvent(
                        event_id=self._make_event_id(session_id, "tool_call", cmd),
                        session_id=session_id,
                        event_type="tool_call",
                        category="tool",
                        data=f"Shell command: {cmd}",
                        summary=f"Executed: {cmd[:80]}",
                        priority=3,
                        timestamp=ts,
                        metadata={"command": cmd, "role": role},
                    ))

        return events

    def _extract_git_events(self, content: str, role: str, session_id: str, ts: str) -> list[SessionEvent]:
        """提取 Git 操作事件"""
        events = []

        for pattern in self.GIT_PATTERNS:
            for match in pattern.finditer(content):
                action = match.group(1)
                detail = match.group(2).strip() if match.lastindex >= 2 else ""
                summary_text = f"git {action}" + (f" {detail[:50]}" if detail else "")

                events.append(SessionEvent(
                    event_id=self._make_event_id(session_id, "git", action),
                    session_id=session_id,
                    event_type="git",
                    category="git",
                    data=f"git {action} {detail}",
                    summary=f"Git: {summary_text}",
                    priority=2,
                    timestamp=ts,
                    metadata={"git_action": action, "detail": detail, "role": role},
                ))

        return events

    def _extract_decision_events(self, content: str, role: str, session_id: str, ts: str) -> list[SessionEvent]:
        """提取用户决策事件"""
        events = []

        # 只从 user 消息中提取决策
        if role != "user":
            return events

        for pattern in self.DECISION_PATTERNS:
            for match in pattern.finditer(content):
                decision = match.group(1).strip()
                if len(decision) < 5:
                    continue

                events.append(SessionEvent(
                    event_id=self._make_event_id(session_id, "decision", decision),
                    session_id=session_id,
                    event_type="decision",
                    category="decision",
                    data=f"User decided: {decision}",
                    summary=f"Decision: {decision[:80]}",
                    priority=1,  # 用户决策 = critical
                    timestamp=ts,
                    metadata={"role": role},
                ))

        return events

    def _extract_rule_events(self, content: str, role: str, session_id: str, ts: str) -> list[SessionEvent]:
        """检测规则文件读取"""
        events = []

        for rule_pattern in self.RULE_FILES:
            if rule_pattern.lower() in content.lower():
                events.append(SessionEvent(
                    event_id=self._make_event_id(session_id, "rule_read", rule_pattern),
                    session_id=session_id,
                    event_type="rule_read",
                    category="rule",
                    data=f"Rule file read: {rule_pattern}",
                    summary=f"Rule read: {rule_pattern}",
                    priority=1,
                    timestamp=ts,
                    metadata={"rule_file": rule_pattern, "role": role},
                ))

        return events


# ============================================================
# Session Event Store — SQLite FTS5 存储
# ============================================================

class SessionEventStore:
    """SQLite FTS5 事件存储"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = os.path.expanduser("~/.openllm/sessions")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "session_events.db")

        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self):
        """初始化数据库"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                category TEXT NOT NULL,
                data TEXT NOT NULL,
                summary TEXT NOT NULL,
                priority INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                summary,
                data,
                content='events',
                content_rowid='rowid',
                tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
                INSERT INTO events_fts(rowid, summary, data)
                VALUES (new.rowid, new.summary, new.data);
            END;

            CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
                INSERT INTO events_fts(events_fts, rowid, summary, data)
                VALUES('delete', old.rowid, old.summary, old.data);
            END;

            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_priority ON events(priority);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        """)
        conn.commit()

    def store_event(self, event: SessionEvent) -> bool:
        """存储单个事件"""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO events
                   (event_id, session_id, event_type, category, data, summary, priority, timestamp, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.session_id,
                    event.event_type,
                    event.category,
                    event.data,
                    event.summary,
                    event.priority,
                    event.timestamp,
                    json.dumps(event.metadata, ensure_ascii=False),
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def store_events(self, events: list[SessionEvent]) -> int:
        """批量存储事件"""
        stored = 0
        for event in events:
            if self.store_event(event):
                stored += 1
        return stored

    def search(
        self,
        query: str,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        max_priority: int = 4,
        limit: int = 20,
    ) -> list[SessionEvent]:
        """BM25 搜索事件"""
        from src.sandbox.indexer import sanitize_query

        sanitized = sanitize_query(query, mode="OR")
        if sanitized == '""':
            return []

        conn = self._get_conn()

        sql = """
            SELECT e.event_id, e.session_id, e.event_type, e.category,
                   e.data, e.summary, e.priority, e.timestamp, e.metadata
            FROM events e
            JOIN events_fts f ON e.rowid = f.rowid
            WHERE events_fts MATCH ?
              AND e.priority <= ?
        """
        params = [sanitized, max_priority]

        if session_id:
            sql += " AND e.session_id = ?"
            params.append(session_id)

        if event_type:
            sql += " AND e.event_type = ?"
            params.append(event_type)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_session_events(
        self,
        session_id: str,
        event_types: Optional[list[str]] = None,
        max_priority: int = 4,
        limit: int = 50,
    ) -> list[SessionEvent]:
        """获取指定会话的事件"""
        conn = self._get_conn()

        sql = "SELECT event_id, session_id, event_type, category, data, summary, priority, timestamp, metadata FROM events WHERE session_id = ? AND priority <= ?"
        params: list = [session_id, max_priority]

        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            sql += f" AND event_type IN ({placeholders})"
            params.extend(event_types)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_critical_events(self, session_id: str) -> list[SessionEvent]:
        """获取关键事件（P1）"""
        return self.get_session_events(session_id, max_priority=1, limit=100)

    def delete_session(self, session_id: str) -> int:
        """删除指定会话的所有事件"""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount

    def get_stats(self, session_id: Optional[str] = None) -> dict:
        """获取事件统计"""
        conn = self._get_conn()

        if session_id:
            total = conn.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", (session_id,)).fetchone()[0]
            by_type = dict(conn.execute(
                "SELECT event_type, COUNT(*) FROM events WHERE session_id = ? GROUP BY event_type",
                (session_id,),
            ).fetchall())
        else:
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            by_type = dict(conn.execute(
                "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
            ).fetchall())

        return {"total_events": total, "by_type": by_type}

    def _row_to_event(self, row) -> SessionEvent:
        """将数据库行转为 SessionEvent"""
        metadata = {}
        if row[8]:
            try:
                metadata = json.loads(row[8])
            except json.JSONDecodeError:
                metadata = {"raw": row[8]}

        return SessionEvent(
            event_id=row[0],
            session_id=row[1],
            event_type=row[2],
            category=row[3],
            data=row[4],
            summary=row[5],
            priority=row[6],
            timestamp=row[7],
            metadata=metadata,
        )

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ============================================================
# Session Event Tracker — 主控制器
# ============================================================

class SessionEventTracker:
    """会话事件追踪器

    核心流程：
    1. 从消息中提取结构化事件（EventExtractor）
    2. 存入 SQLite FTS5（SessionEventStore）
    3. 上下文压缩后，通过 BM25 搜索召回关键事件
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        auto_extract: bool = True,
    ):
        self.extractor = EventExtractor()
        self.store = SessionEventStore(db_path=db_path)
        self.auto_extract = auto_extract

    def process_messages(
        self,
        messages: list[dict],
        session_id: str,
    ) -> list[SessionEvent]:
        """处理消息列表，提取并存储事件

        Args:
            messages: 消息列表
            session_id: 会话 ID

        Returns:
            提取到的新事件列表
        """
        events = self.extractor.extract_from_messages(messages, session_id)
        stored = self.store.store_events(events)

        if stored > 0:
            logger.info(f"Session {session_id}: extracted & stored {stored} events")

        return events

    def recall(
        self,
        query: str,
        session_id: str,
        max_events: int = 10,
    ) -> RecallResult:
        """上下文召回 — 搜索相关历史事件

        Args:
            query: 当前上下文/问题
            session_id: 会话 ID
            max_events: 最大召回事件数

        Returns:
            RecallResult
        """
        events = self.store.search(
            query=query,
            session_id=session_id,
            max_priority=2,  # 只召回 P0 和 P1 事件
            limit=max_events,
        )

        # 估算节省的 token 数
        # 假设原始对话 ~2000 tokens，召回的事件摘要 ~200 tokens
        original_tokens = max_events * 200  # 粗略估算
        recalled_tokens = sum(len(e.summary) // 4 for e in events)
        saved = max(0, original_tokens - recalled_tokens)

        return RecallResult(
            events=events,
            total_found=len(events),
            query=query,
            context_tokens_saved=saved,
            recall_mode="search",
        )

    def get_session_context(self, session_id: str, max_events: int = 20) -> str:
        """获取会话上下文摘要（用于注入 system prompt）

        Returns:
            格式化的上下文字符串
        """
        # 先获取关键事件
        critical = self.store.get_critical_events(session_id)

        # 再获取最近的其他事件
        recent = self.store.get_session_events(
            session_id, max_priority=2, limit=max_events
        )

        # 去重（critical 事件优先）
        seen = set()
        ordered = []
        for e in critical + recent:
            if e.event_id not in seen:
                seen.add(e.event_id)
                ordered.append(e)

        if not ordered:
            return ""

        lines = [f"## Session Context ({session_id})"]
        lines.append("")
        lines.append("### Key Events")
        lines.append("")

        for e in ordered[:max_events]:
            priority_marker = "🔴" if e.priority == 1 else "🟡"
            lines.append(f"- {priority_marker} {e.summary}")
            if e.event_type == "error":
                lines.append(f"  - Detail: {e.data[:100]}")

        return "\n".join(lines)

    def enrich_messages(
        self,
        messages: list[dict],
        session_id: str,
        max_tokens: int = 2000,
    ) -> tuple[list[dict], dict]:
        """用召回的事件增强消息（替代传统摘要）

        Args:
            messages: 当前消息列表
            session_id: 会话 ID
            max_tokens: 最大额外 token 数

        Returns:
            (增强后的消息列表, 元数据)
        """
        # 先处理当前消息，提取事件
        self.process_messages(messages, session_id)

        # 用最后一条用户消息作为搜索查询
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")[:500]
                break

        if not last_user:
            return messages, {"recalled": 0, "tokens_saved": 0}

        # 召回相关事件
        recall = self.recall(last_user, session_id)

        if not recall.events:
            return messages, {"recalled": 0, "tokens_saved": 0}

        # 构建上下文注入
        context_parts = ["### Previous Session Context"]
        for e in recall.events:
            context_parts.append(f"- {e.summary}")

        context_text = "\n".join(context_parts)

        # 插入到 system message 中
        enhanced_messages = []
        context_injected = False

        for msg in messages:
            if msg.get("role") == "system" and not context_injected:
                enhanced_msg = {
                    "role": "system",
                    "content": msg.get("content", "") + "\n\n" + context_text,
                }
                enhanced_messages.append(enhanced_msg)
                context_injected = True
            else:
                enhanced_messages.append(msg)

        if not context_injected:
            enhanced_messages.insert(0, {
                "role": "system",
                "content": context_text,
            })

        return enhanced_messages, {
            "recalled": recall.total_found,
            "tokens_saved": recall.context_tokens_saved,
        }

    def delete_session(self, session_id: str) -> int:
        """删除会话的所有事件"""
        return self.store.delete_session(session_id)

    def get_stats(self, session_id: Optional[str] = None) -> dict:
        """获取统计"""
        return self.store.get_stats(session_id)

    def close(self):
        """关闭数据库"""
        self.store.close()


# ============================================================
# Global instance
# ============================================================

_tracker: Optional[SessionEventTracker] = None


def get_tracker(db_path: Optional[str] = None) -> SessionEventTracker:
    """获取全局事件追踪器实例"""
    global _tracker
    if _tracker is None:
        _tracker = SessionEventTracker(db_path=db_path)
    return _tracker


def reset_tracker():
    """重置全局实例（用于测试）"""
    global _tracker
    if _tracker:
        _tracker.close()
    _tracker = None
