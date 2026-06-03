"""Provider Protocol — 零耦合插件接口（参考 FreeRide 设计）"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from .types import ChatRequest, ChatResponse, ErrorKind


@runtime_checkable
class Provider(Protocol):
    """Provider 插件协议
    
    每个 Provider 插件实现此接口，核心零耦合。
    新增 Provider = 新增一个文件，实现此接口。
    """
    name: str
    api_version: int = 1
    
    async def list_models(self) -> list[dict]:
        """返回可用模型列表 [{"id": str, "name": str, "is_free": bool}, ...]"""
        ...
    
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """非流式聊天补全"""
        ...
    
    async def chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        """流式聊天补全，逐 chunk yield ChatResponse"""
        ...

    async def close(self) -> None:
        """释放 Provider 持有的资源（HTTP 客户端、文件句柄等）

        由服务器生命周期管理，确保优雅关闭。
        可选实现；没有资源需要释放的 Provider 可以省略。
        """
        ...

    def classify_error(self, exc: Exception) -> ErrorKind:
        """将 Provider 特有异常归一到 ErrorKind"""
        ...
    
    def auth_header(self) -> dict[str, str]:
        """构造认证 HTTP 头"""
        ...
    
    @property
    def attribution_header(self) -> dict[str, str]:
        """归属标记头"""
        return {}
