"""
Sandbox Router — FastAPI 端点暴露沙盒工具

提供 REST API 供 AI 代理调用：
- POST /api/sandbox/execute — 执行代码
- POST /api/sandbox/batch — 批量执行
- POST /api/sandbox/index — 索引内容
- GET  /api/sandbox/search — 搜索索引
- GET  /api/sandbox/stats — 统计信息
- GET  /api/sandbox/languages — 可用语言
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.sandbox.executor import SandboxExecutor
from src.sandbox.batch import BatchExecutor, BatchCommand
from src.sandbox.indexer import ContentIndexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

# ============================================================
# Singletons
# ============================================================

_executor: Optional[SandboxExecutor] = None
_batch: Optional[BatchExecutor] = None
_indexer: Optional[ContentIndexer] = None


def get_executor() -> SandboxExecutor:
    global _executor
    if _executor is None:
        _executor = SandboxExecutor()
    return _executor


def get_batch() -> BatchExecutor:
    global _batch
    if _batch is None:
        _batch = BatchExecutor()
    return _batch


def get_indexer() -> ContentIndexer:
    global _indexer
    if _indexer is None:
        _indexer = ContentIndexer()
    return _indexer


# ============================================================
# Request/Response models
# ============================================================

class ExecuteRequest(BaseModel):
    language: str = Field(..., description="编程语言: python, javascript, shell, etc.")
    code: str = Field(..., description="要执行的代码")
    timeout: Optional[int] = Field(None, description="超时秒数 (默认 30s)")


class ExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    raw_bytes: int
    truncated: bool
    summary: str


class BatchCommandItem(BaseModel):
    language: str
    code: str
    label: str = ""


class BatchRequest(BaseModel):
    commands: list[BatchCommandItem] = Field(..., description="命令列表")
    track_file_reads: bool = Field(True, description="是否追踪文件读取")


class BatchResponse(BaseModel):
    commands_executed: int
    commands_succeeded: int
    commands_failed: int
    total_duration_ms: float
    summary: str
    files_read: list[str]
    context_bytes: int  # 摘要占用的上下文字节数


class IndexRequest(BaseModel):
    source: str = Field(..., description="来源标识")
    content: str = Field(..., description="要索引的内容")
    label: str = Field("", description="可选标签")
    content_type: str = Field("text", description="内容类型: text, markdown, code, session_event")


class IndexResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    total_bytes: int
    duration_ms: float


class SearchResponse(BaseModel):
    query: str
    results: list[dict]
    count: int


# ============================================================
# Endpoints
# ============================================================

@router.post("/execute", response_model=ExecuteResponse)
async def execute_code(req: ExecuteRequest):
    """执行单段代码

    沙盒隔离执行，输出自动截断，防止淹没上下文窗口。
    """
    executor = get_executor()
    result = executor.execute(
        language=req.language,
        code=req.code,
        timeout=req.timeout,
    )

    return ExecuteResponse(
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        raw_bytes=result.raw_bytes,
        truncated=result.truncated,
        summary=result.summary,
    )


@router.post("/batch", response_model=BatchResponse)
async def batch_execute(req: BatchRequest):
    """批量执行多个命令

    只返回摘要，原始数据保留在沙盒中。98% 上下文节省。
    """
    batch = get_batch()
    commands = [
        BatchCommand(language=c.language, code=c.code, label=c.label)
        for c in req.commands
    ]

    result = batch.execute_batch(
        commands=commands,
        track_file_reads=req.track_file_reads,
    )

    return BatchResponse(
        commands_executed=result.commands_executed,
        commands_succeeded=result.commands_succeeded,
        commands_failed=result.commands_failed,
        total_duration_ms=result.total_duration_ms,
        summary=result.summary,
        files_read=result.files_read,
        context_bytes=result.context_bytes,
    )


@router.post("/index", response_model=IndexResponse)
async def index_content(req: IndexRequest):
    """索引内容到 SQLite FTS5

    原始数据不进入上下文窗口，存入索引后可按需搜索召回。
    """
    indexer = get_indexer()
    result = indexer.index_text(
        source=req.source,
        content=req.content,
        label=req.label,
        content_type=req.content_type,
    )

    return IndexResponse(
        doc_id=result.doc_id,
        chunks_indexed=result.chunks_indexed,
        total_bytes=result.total_bytes,
        duration_ms=result.duration_ms,
    )


@router.get("/search", response_model=SearchResponse)
async def search_content(
    q: str,
    source: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 10,
):
    """BM25 搜索索引内容"""
    indexer = get_indexer()
    results = indexer.search(
        query=q,
        source=source,
        content_type=content_type,
        limit=limit,
    )

    return SearchResponse(
        query=q,
        results=[
            {
                "title": r.title,
                "content": r.content,
                "source": r.source,
                "rank": round(r.rank, 4),
                "highlighted": r.highlighted,
            }
            for r in results
        ],
        count=len(results),
    )


@router.get("/stats")
async def get_stats():
    """获取索引统计"""
    indexer = get_indexer()
    stats = indexer.get_stats()

    executor = get_executor()
    runtimes = executor.get_runtime_summary()

    return {
        "index": {
            "total_documents": stats.total_documents,
            "total_chunks": stats.total_chunks,
            "total_bytes": stats.total_bytes,
            "sources": stats.sources,
        },
        "runtimes": runtimes,
    }


@router.get("/languages")
async def get_languages():
    """获取可用的编程语言"""
    executor = get_executor()
    return {
        "available": executor.get_available_languages(),
        "summary": executor.get_runtime_summary(),
    }


@router.delete("/purge")
async def purge_index(source: Optional[str] = None):
    """清除索引

    不带 source 参数时清除全部，带 source 时只清除指定来源。
    """
    indexer = get_indexer()
    if source:
        deleted = indexer.delete_by_source(source)
        return {"deleted_documents": deleted, "source": source}
    else:
        indexer.purge()
        return {"deleted": "all"}
