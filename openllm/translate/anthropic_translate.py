"""Anthropic ↔ OpenAI 协议双向翻译（参考 FreeRide 设计）

让使用 Anthropic Message API 的工具（Claude Code）能调用 OpenAI 兼容模型，
反之让使用 OpenAI 的工具能调用 Anthropic 原生 API。
"""

from __future__ import annotations


from .base import ProtocolTranslator


class AnthropicToOpenAI(ProtocolTranslator):
    """Anthropic Message API → OpenAI Chat Completions"""
    
    source_format = "anthropic"
    target_format = "openai"
    
    def to_openai(self, request: dict) -> dict:
        """
        转换 Anthropic 请求到 OpenAI 格式
        
        关键映射:
        - anthropic messages[] → openai messages[]
        - system prompt → system message (OpenAI 方式)
        - max_tokens → max_tokens
        - stop_sequences → stop
        - temperature/top_p → 直通
        """
        openai_req = {
            "model": request.get("model", ""),
            "messages": self._convert_messages(request.get("messages", [])),
            "max_tokens": request.get("max_tokens"),
            "temperature": request.get("temperature"),
            "top_p": request.get("top_p"),
            "stream": request.get("stream", False),
        }
        
        # system prompt 作为单独 key 处理
        system = request.get("system")
        if system:
            openai_req["messages"].insert(0, {"role": "system", "content": system})
        
        # stop_sequences
        stops = request.get("stop_sequences")
        if stops:
            openai_req["stop"] = stops if isinstance(stops, list) else [stops]
        
        # tools
        tools = request.get("tools")
        if tools:
            openai_req["tools"] = self._convert_tools(tools)
        
        return {k: v for k, v in openai_req.items() if v is not None}
    
    def from_openai(self, response: dict) -> dict:
        """将 OpenAI 响应转回 Anthropic Messages 格式"""
        choices = response.get("choices", [{}])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})
        usage = response.get("usage", {})
        
        anthropic_resp = {
            "id": response.get("id", "msg_openllm"),
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": message.get("content", "")}],
            "model": response.get("model", ""),
            "stop_reason": self._map_finish_reason(choice.get("finish_reason")),
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            } if usage else None,
        }
        return {k: v for k, v in anthropic_resp.items() if v is not None}
    
    def from_openai_stream(self, chunk: dict) -> dict:
        """将 OpenAI SSE chunk 转 Anthropic SSE 格式"""
        choices = chunk.get("choices", [{}])
        choice = choices[0] if choices else {}
        delta = choice.get("delta", {})
        content = delta.get("content", "")
        finish = choice.get("finish_reason")
        
        if finish:
            return {
                "type": "message_delta",
                "delta": {"stop_reason": self._map_finish_reason(finish)},
                "usage": {"output_tokens": 0},
            }
        
        if content:
            return {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": content},
            }
        
        return {"type": "ping"}
    
    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """转换 Anthropic 消息到 OpenAI 格式"""
        openai_msgs = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Anthropic 的 content 可能是数组 (多模态)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                content = "\n".join(text_parts) if text_parts else ""
            
            if role == "assistant":
                openai_msgs.append({"role": "assistant", "content": content})
            elif role == "user":
                openai_msgs.append({"role": "user", "content": content})
            else:
                openai_msgs.append({"role": role, "content": content})
        
        return openai_msgs
    
    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """转换 Anthropic 工具定义到 OpenAI 格式

        Anthropic 工具定义有两种形式：
        1. 标准格式: {"name": "...", "description": "...", "input_schema": {...}}
        2. 显式格式: {"type": "custom" | "function", ...}

        两种都处理为标准 OpenAI function calling 格式。
        """
        openai_tools = []
        for tool in tools:
            ttype = tool.get("type")
            # 标准 Anthropic 工具定义没有 "type" 字段 → 视为 custom
            if ttype is None or ttype == "custom":
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                })
            elif ttype == "function":
                # 已经是 OpenAI function calling 格式
                openai_tools.append(tool)
        return openai_tools
    
    @staticmethod
    def _map_finish_reason(reason: str | None) -> str | None:
        """映射 OpenAI finish_reason 到 Anthropic stop_reason"""
        mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "content_filter",
        }
        return mapping.get(reason or "", None)


class OpenAIToAnthropic(ProtocolTranslator):
    """OpenAI Chat Completions → Anthropic Message API

    用于让使用 OpenAI SDK 的工具调用 Anthropic 原生 API。
    OpenLLM 接收 OpenAI 格式请求 → 发往 Anthropic 原生 API → 转回 OpenAI 格式。
    """

    source_format = "openai"
    target_format = "anthropic"

    def to_openai(self, request: dict) -> dict:
        # 已经是 OpenAI 格式，直接透传
        return request

    def from_openai(self, response: dict) -> dict:
        """将 OpenAI 响应转回 Anthropic Messages 格式"""
        choices = response.get("choices", [{}])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})
        usage = response.get("usage", {})

        return {
            "id": "msg_openllm",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": message.get("content", "")}],
            "model": response.get("model", ""),
            "stop_reason": AnthropicToOpenAI._map_finish_reason(choice.get("finish_reason")),
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            } if usage else None,
        }

    def from_openai_stream(self, chunk: dict) -> dict:
        """将 OpenAI SSE chunk 转 Anthropic SSE 格式"""
        choices = chunk.get("choices", [{}])
        choice = choices[0] if choices else {}
        delta = choice.get("delta", {})
        content = delta.get("content", "")
        finish = choice.get("finish_reason")

        if finish:
            return {
                "type": "message_delta",
                "delta": {"stop_reason": AnthropicToOpenAI._map_finish_reason(finish)},
                "usage": {"output_tokens": 0},
            }

        if content:
            return {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": content},
            }

        return {"type": "ping"}
