import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.adapter_model import ModelConfig, AdapterConfig
from src.models import ModelInfo
from src.registry import ModelRegistry


@pytest.fixture
def registry():
    return ModelRegistry()


@pytest.fixture
def sample_config():
    return ModelConfig(
        name="test-model",
        protocol="openai",
        endpoint="https://api.test.com/v1",
        api_key="test-key",
        enabled=True,
    )


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.list_available_models = AsyncMock(
        return_value=[
            ModelInfo(id="gpt-4", created=1234567890, owned_by="openai"),
            ModelInfo(id="gpt-3.5-turbo", created=1234567890, owned_by="openai"),
        ]
    )
    return adapter


@pytest.mark.asyncio
async def test_discover_models(registry, sample_config, mock_adapter):
    registry._models = {sample_config.name: sample_config}
    registry._adapters = {sample_config.name: mock_adapter}

    discovered = await registry.discover_models("/tmp/test_models.yaml")

    assert len(discovered) == 2
    assert "gpt-4" in [m.name for m in discovered]
    assert "gpt-3.5-turbo" in [m.name for m in discovered]


@pytest.mark.asyncio
async def test_discover_skips_existing_models(registry, sample_config):
    existing_model = ModelConfig(
        name="gpt-4",
        protocol="openai",
        endpoint="https://api.test.com/v1",
        api_key="test-key",
        enabled=True,
    )
    registry._models = {
        sample_config.name: sample_config,
        existing_model.name: existing_model,
    }

    mock_adapter = MagicMock()
    mock_adapter.list_available_models = AsyncMock(
        return_value=[
            ModelInfo(id="gpt-4", created=1234567890, owned_by="openai"),
        ]
    )
    registry._adapters = {sample_config.name: mock_adapter}

    discovered = await registry.discover_models("/tmp/test_models.yaml")

    assert len(discovered) == 0


@pytest.mark.asyncio
async def test_list_available_models_base():
    from src.adapters.base import ProtocolAdapter
    from src.adapter_model import AdapterConfig

    class TestAdapter(ProtocolAdapter):
        protocol = "test"

        async def chat_completions(self, messages, **kwargs):
            pass

        async def embeddings(self, texts, **kwargs):
            pass

        async def get_model_info(self):
            return ModelInfo(id="test-model", created=1234567890, owned_by="test")

    config = AdapterConfig(model="test", protocol="test", endpoint="http://test.com")
    adapter = TestAdapter(config)

    models = await adapter.list_available_models()

    assert len(models) == 1
    assert models[0].id == "test-model"
