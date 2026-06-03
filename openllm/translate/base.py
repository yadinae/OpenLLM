"""协议翻译基类 — 在 API 格式之间双向转换"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProtocolTranslator(ABC):
    """协议翻译器基类
    
    负责在 OpenAI Chat Completions 格式和其他 API 格式之间双向转换。
    每个方向实现一对方法：to_openai / from_openai
    """
    
    source_format: str = ""  # 源格式标识，如 "anthropic"
    target_format: str = "openai"
    
    @abstractmethod
    def to_openai(self, request: dict) -> dict:
        """将源格式请求转换为 OpenAI 格式"""
        ...
    
    @abstractmethod
    def from_openai(self, response: dict) -> dict:
        """将 OpenAI 格式响应转换为源格式"""
        ...
    
    def to_openai_stream(self, chunk: dict) -> dict:
        """（可选）将源格式流式 chunk 转换为 OpenAI SSE 格式"""
        return chunk
    
    def from_openai_stream(self, chunk: dict) -> dict:
        """（可选）将 OpenAI SSE chunk 转换为目标格式"""
        return chunk
