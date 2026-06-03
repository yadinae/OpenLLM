"""协议翻译单元测试 — 验证 Anthropic ↔ OpenAI 双向转换"""
from __future__ import annotations


from openllm.translate.anthropic_translate import AnthropicToOpenAI, OpenAIToAnthropic


class TestAnthropicToOpenAI:
    """Anthropic → OpenAI 转换测试"""

    def setup_method(self):
        self.t = AnthropicToOpenAI()

    def test_basic_message_conversion(self):
        """基础消息转换"""
        anthropic_req = {
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "stream": False,
        }
        openai = self.t.to_openai(anthropic_req)
        assert openai["model"] == "claude-3-opus"
        assert len(openai["messages"]) == 1
        assert openai["messages"][0]["role"] == "user"
        assert openai["messages"][0]["content"] == "Hello"
        assert openai["max_tokens"] == 100

    def test_system_prompt_conversion(self):
        """System prompt 应该被插入为第一条 system message"""
        anthropic_req = {
            "messages": [{"role": "user", "content": "Hi"}],
            "system": "You are helpful",
        }
        openai = self.t.to_openai(anthropic_req)
        assert openai["messages"][0]["role"] == "system"
        assert openai["messages"][0]["content"] == "You are helpful"
        assert openai["messages"][1]["role"] == "user"

    def test_content_blocks_conversion(self):
        """Anthropic 的 content_blocks (数组 content) → OpenAI 纯文本"""
        anthropic_req = {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"},
                ],
            }],
        }
        openai = self.t.to_openai(anthropic_req)
        assert openai["messages"][0]["content"] == "Hello\nWorld"

    def test_stop_sequences_conversion(self):
        """stop_sequences → stop"""
        anthropic_req = {
            "messages": [{"role": "user", "content": "Hi"}],
            "stop_sequences": ["\n\n", "stop"],
        }
        openai = self.t.to_openai(anthropic_req)
        assert openai["stop"] == ["\n\n", "stop"]

    def test_single_stop_sequence(self):
        """单个 stop_sequence 应该包装成 list"""
        anthropic_req = {
            "messages": [{"role": "user", "content": "Hi"}],
            "stop_sequences": "\n\n",
        }
        openai = self.t.to_openai(anthropic_req)
        assert openai["stop"] == ["\n\n"]

    def test_anthropic_tool_conversion(self):
        """Anthropic tool → OpenAI function tool"""
        anthropic_req = {
            "messages": [{"role": "user", "content": "Weather?"}],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                }
            ],
        }
        openai = self.t.to_openai(anthropic_req)
        assert "tools" in openai
        assert openai["tools"][0]["type"] == "function"
        assert openai["tools"][0]["function"]["name"] == "get_weather"

    def test_from_openai_basic_response(self):
        """OpenAI 响应 → Anthropic 格式"""
        openai_resp = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Hello back"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        anthropic = self.t.from_openai(openai_resp)
        assert anthropic["type"] == "message"
        assert anthropic["content"][0]["type"] == "text"
        assert anthropic["content"][0]["text"] == "Hello back"
        assert anthropic["stop_reason"] == "end_turn"
        assert anthropic["usage"]["input_tokens"] == 10
        assert anthropic["usage"]["output_tokens"] == 5

    def test_from_openai_empty_choices(self):
        """choices 为空列表时应该不崩溃"""
        openai_resp = {"id": "x", "model": "gpt-4", "choices": []}
        anthropic = self.t.from_openai(openai_resp)
        assert anthropic["type"] == "message"
        assert anthropic["content"] == [{"type": "text", "text": ""}]

    def test_from_openai_no_usage(self):
        """没有 usage 信息时返回 None"""
        openai_resp = {
            "id": "x",
            "model": "gpt-4",
            "choices": [{"index": 0, "message": {"content": "Hi"}, "finish_reason": "stop"}],
        }
        anthropic = self.t.from_openai(openai_resp)
        assert "usage" not in anthropic or anthropic["usage"] is None

    def test_finish_reason_mapping(self):
        """finish_reason 映射完整性"""
        assert self.t._map_finish_reason("stop") == "end_turn"
        assert self.t._map_finish_reason("length") == "max_tokens"
        assert self.t._map_finish_reason("tool_calls") == "tool_use"
        assert self.t._map_finish_reason("content_filter") == "content_filter"
        assert self.t._map_finish_reason(None) is None
        assert self.t._map_finish_reason("unknown") is None

    def test_from_openai_stream_content_delta(self):
        """OpenAI SSE content chunk → Anthropic content_block_delta"""
        chunk = {"choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}]}
        result = self.t.from_openai_stream(chunk)
        assert result["type"] == "content_block_delta"
        assert result["delta"]["type"] == "text_delta"
        assert result["delta"]["text"] == "Hello"
        assert result["index"] == 0

    def test_from_openai_stream_finish(self):
        """OpenAI SSE finish chunk → Anthropic message_delta"""
        chunk = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        result = self.t.from_openai_stream(chunk)
        assert result["type"] == "message_delta"
        assert result["delta"]["stop_reason"] == "end_turn"

    def test_from_openai_stream_ping(self):
        """空 content 且没有 finish_reason → ping"""
        chunk = {"choices": [{"index": 0, "delta": {}, "finish_reason": None}]}
        result = self.t.from_openai_stream(chunk)
        assert result["type"] == "ping"

    # ─── P0/P1 缺陷验证（已修复） ───

    def test_sse_protocol_events_from_openai_stream(self):
        """from_openai_stream 按 chunk 返回正确的事件类型"""
        # content chunk → content_block_delta
        content_chunk = {"choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}]}
        result = self.t.from_openai_stream(content_chunk)
        assert result["type"] == "content_block_delta"
        assert result["delta"]["type"] == "text_delta"
        assert result["delta"]["text"] == "Hello"

        # finish chunk → message_delta
        finish_chunk = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        result = self.t.from_openai_stream(finish_chunk)
        assert result["type"] == "message_delta"
        assert result["delta"]["stop_reason"] == "end_turn"

        # empty chunk → ping
        empty_chunk = {"choices": [{"index": 0, "delta": {}, "finish_reason": None}]}
        result = self.t.from_openai_stream(empty_chunk)
        assert result["type"] == "ping"

        # 完整 SSE 协议序列（message_start / content_block_start /
        # content_block_stop / message_stop）由 _stream_anthropic()
        # 在 messages.py 中实现，不在 from_openai_stream 层面

    def test_tool_type_detection_fallback(self):
        """P0（已修复）: 标准 Anthropic 工具无 type 字段时视为 custom"""
        std_tool = {
            "name": "get_weather",
            "description": "Get weather",
            "input_schema": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        }
        result = self.t._convert_tools([std_tool])
        assert len(result) == 1, (
            "标准 Anthropic 工具定义（无 type 字段）应该被正确转换为 function calling 格式"
        )
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_weather"


class TestOpenAIToAnthropic:
    """OpenAI → Anthropic 转换测试"""

    def setup_method(self):
        self.t = OpenAIToAnthropic()

    def test_from_openai_conversion(self):
        """OpenAIToAnthropic.from_openai 将 OpenAI 响应转 Anthropic 格式"""
        self.t = OpenAIToAnthropic()
        openai_resp = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Hello"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result = self.t.from_openai(openai_resp)
        assert result["type"] == "message"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello"
        assert result["stop_reason"] == "end_turn"

    def test_to_openai_pass_through(self):
        """OpenAIToAnthropic.to_openai 透传（源已是 OpenAI 格式）"""
        self.t = OpenAIToAnthropic()
        req = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
        assert self.t.to_openai(req) == req  # 值相等


class TestAnthropicStreamSSEProtocol:
    """Anthropic SSE 协议完整性测试"""

    def setup_method(self):
        self.t = AnthropicToOpenAI()

    def test_from_openai_stream_event_types(self):
        """from_openai_stream 为每种 chunk 类型返回正确的事件

        完整 SSE 协议序列（message_start → content_block_start →
        content_block_delta* → content_block_stop → message_delta → message_stop）
        由 messages.py 中 _stream_anthropic() 实现。
        from_openai_stream 只负责单个 chunk 的格式转换。
        """
        # 3 chunks 组成完整流
        chunks = [
            {"choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {"content": " World"}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]

        events = []
        for chunk in chunks:
            events.append(self.t.from_openai_stream(chunk))

        event_types = [e["type"] for e in events]
        # from_openai_stream: content→content_block_delta, finish→message_delta
        assert event_types == ["content_block_delta", "content_block_delta", "message_delta"]
        
        # 详细验证每个事件
        assert events[0]["delta"]["type"] == "text_delta"
        assert events[0]["delta"]["text"] == "Hello"
        assert events[1]["delta"]["text"] == " World"
        assert events[2]["delta"]["stop_reason"] == "end_turn"
