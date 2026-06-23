"""ModelMetadataRegistry 单元测试"""

from __future__ import annotations

import pytest
from openllm.core.model_metadata import ModelMetadataRegistry, ModelMetadata


class TestModelMetadataRegistry:
    def test_empty_registry(self):
        reg = ModelMetadataRegistry()
        assert reg.list_all() == []

    def test_update_from_api(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("deepseek", [
            {"id": "deepseek-chat", "context_length": 65536,
             "capabilities": ["text", "reasoning"], "supports_reasoning": True},
        ])
        meta = reg.get("deepseek/deepseek-chat")
        assert meta is not None
        assert meta.context_length == 65536
        assert "reasoning" in meta.capabilities
        assert meta.supports_reasoning is True
        assert meta.provider == "deepseek"

    def test_update_from_api_missing_fields_default(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("nvidia", [{"id": "llama-3.1-8b"}])
        meta = reg.get("nvidia/llama-3.1-8b")
        assert meta is not None
        assert meta.context_length == 4096
        assert meta.capabilities == ["text"]
        assert meta.supports_reasoning is False

    def test_update_from_config_overrides_api(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("deepseek", [
            {"id": "deepseek-chat", "context_length": 32000},
        ])
        reg.update_from_config({
            "deepseek/deepseek-chat": {"context_length": 65536},
        })
        meta = reg.get("deepseek/deepseek-chat")
        assert meta is not None
        assert meta.context_length == 65536

    def test_get_nonexistent_returns_none(self):
        reg = ModelMetadataRegistry()
        assert reg.get("nonexistent/model") is None

    def test_list_all_returns_all(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("p1", [{"id": "m1"}, {"id": "m2"}])
        reg.update_from_api("p2", [{"id": "m3"}])
        assert len(reg.list_all()) == 3

    def test_config_creates_new_entry_when_no_api_data(self):
        reg = ModelMetadataRegistry()
        reg.update_from_config({
            "custom/model": {"context_length": 128000, "capabilities": ["text", "vision"]},
        })
        meta = reg.get("custom/model")
        assert meta is not None
        assert meta.context_length == 128000
        assert "vision" in meta.capabilities
