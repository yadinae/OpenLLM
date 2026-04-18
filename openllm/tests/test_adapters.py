"""Tests for protocol adapters"""

import pytest
from openllm.src.adapter_model import AdapterConfig
from openllm.src.adapters.openai import OpenAIAdapter
from openllm.src.adapters.base import AdapterError, RateLimitError


class TestOpenAIAdapter:
    """Tests for OpenAI adapter"""

    @pytest.fixture
    def config(self):
        return AdapterConfig(
            model="gpt-3.5-turbo",
            protocol="openai",
            endpoint="https://api.openai.com/v1",
            api_key="test-key",
        )

    @pytest.fixture
    def adapter(self, config):
        return OpenAIAdapter(config)

    def test_adapter_protocol(self, adapter):
        assert adapter.protocol == "openai"

    def test_adapter_model_name(self, adapter):
        assert adapter.model_name == "gpt-3.5-turbo"

    def test_build_headers(self, adapter):
        headers = adapter._build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-key"


class TestRateLimitError:
    """Tests for rate limit error"""

    def test_rate_limit_error_code(self):
        error = RateLimitError()
        assert error.code == 429

    def test_rate_limit_error_message(self):
        error = RateLimitError("Custom message")
        assert error.message == "Custom message"


class TestAdapterError:
    """Tests for adapter error"""

    def test_adapter_error(self):
        error = AdapterError("Test error", 500)
        assert error.message == "Test error"
        assert error.code == 500
