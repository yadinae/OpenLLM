import pytest
from src.freeride import FreeRideManager, FREE_PROVIDERS, FreeRideConfig


def test_free_providers_exist():
    expected = ["groq", "cerebras", "openrouter", "mistral", "gemini", "ollama"]
    assert list(FREE_PROVIDERS.keys()) == expected


def test_freeride_config_defaults():
    config = FreeRideConfig()
    assert config.enabled is False
    assert config.providers == []


def test_get_free_providers():
    class MockRegistry:
        def __init__(self):
            self._models = {}

    freeride = FreeRideManager(MockRegistry())
    providers = freeride.get_free_providers()

    assert "groq" in providers
    assert providers["groq"]["name"] == "Groq"


def test_get_selected_providers():
    class MockRegistry:
        def __init__(self):
            self._models = {}

    freeride = FreeRideManager(MockRegistry())
    providers = freeride.get_free_providers(["groq", "mistral"])

    assert "groq" in providers
    assert "mistral" in providers
    assert len(providers) == 2


def test_provider_model_structure():
    for key, provider in FREE_PROVIDERS.items():
        assert "name" in provider
        assert "endpoint" in provider
        assert "protocol" in provider
        assert "models" in provider
        assert len(provider["models"]) > 0

        for model in provider["models"]:
            assert "name" in model
            assert "rpm" in model
            assert "tpm" in model
            assert "context" in model
