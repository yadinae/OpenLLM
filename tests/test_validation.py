"""输入校验单元测试"""
from __future__ import annotations

from openllm.server.validation import validate_chat_messages, validate_model_name


class TestValidateChatMessages:
    def test_empty_messages(self):
        assert validate_chat_messages([]) is not None

    def test_valid_messages(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert validate_chat_messages(msgs) is None

    def test_invalid_role(self):
        msgs = [{"role": "admin", "content": "hello"}]
        assert validate_chat_messages(msgs) is not None

    def test_content_too_long(self):
        msgs = [{"role": "user", "content": "x" * 60000}]
        assert validate_chat_messages(msgs) is not None

    def test_non_dict_message(self):
        assert validate_chat_messages(["string"]) is not None

    def test_too_many_messages(self):
        msgs = [{"role": "user", "content": "hi"} for _ in range(300)]
        assert validate_chat_messages(msgs) is not None

    def test_tool_role_allowed(self):
        msgs = [{"role": "tool", "content": "result"}]
        assert validate_chat_messages(msgs) is None

    def test_system_role_allowed(self):
        msgs = [{"role": "system", "content": "be helpful"}]
        assert validate_chat_messages(msgs) is None


class TestValidateModelName:
    def test_empty_model(self):
        assert validate_model_name("") is not None

    def test_valid_model(self):
        assert validate_model_name("gpt-4") is None

    def test_too_long(self):
        assert validate_model_name("x" * 300) is not None

    def test_provider_model_format(self):
        assert validate_model_name("groq/llama-3") is None
