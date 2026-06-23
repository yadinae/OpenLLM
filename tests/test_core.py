"""OpenLLM 核心单元测试"""

from __future__ import annotations

import pytest

from openllm.core.types import (
    ErrorKind, RoutingStrategy, TerseLevel,
    ChatMessage, ChatRequest, ChatResponse, TokenUsage,
    ComboConfig, ComboMember, ProviderConfig,
)
from openllm.core.errors import (
    ProviderError, RateLimitError, AuthError,
    ModelNotFoundError, AllProvidersFailedError, ConfigurationError,
)
from openllm.core.state import read_json, write_json_atomic, load_env_file
from openllm.core.cooldown import CooldownManager
from openllm.core.registry import Registry
from openllm.core.combo import ComboEngine


class TestTypes:
    """核心数据类型测试"""

    def test_error_kind_values(self):
        assert ErrorKind.RATE_LIMIT.value == "rate_limit"
        assert ErrorKind.AUTH.value == "auth"
        assert ErrorKind.MODEL_NOT_FOUND.value == "model_not_found"
        assert len(ErrorKind) == 9

    def test_terse_level_distinct(self):
        """P0 回归测试：TerseLevel 成员必须互不相同"""
        values = [m.value for m in TerseLevel]
        assert len(values) == len(set(values)), f"Duplicate values: {values}"
        assert TerseLevel.OFF != TerseLevel.LITE

    def test_routing_strategy(self):
        assert RoutingStrategy.FALLBACK.value == "fallback"
        assert RoutingStrategy.ROUND_ROBIN.value == "round_robin"

    def test_chat_message_creation(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_chat_request_creation(self):
        req = ChatRequest(
            model="test-model",
            messages=[ChatMessage(role="user", content="hi")],
        )
        assert req.model == "test-model"
        assert req.stream is False
        assert req.terse_level == TerseLevel.OFF

    def test_chat_response_with_usage(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        resp = ChatResponse(content="ok", model="m", provider="p", usage=usage)
        assert resp.usage.total_tokens == 15
        assert resp.finish_reason == "stop"

    def test_combo_config(self):
        combo = ComboConfig(
            name="test",
            strategy=RoutingStrategy.FALLBACK,
            members=[
                ComboMember(model="m1", provider="p1", priority=0),
                ComboMember(model="m2", provider="p2", priority=1),
            ],
        )
        assert len(combo.members) == 2
        assert combo.members[0].priority == 0

    def test_provider_config(self):
        cfg = ProviderConfig(name="test", api_key="sk-xxx", endpoint="https://example.com/v1")
        assert cfg.name == "test"
        assert cfg.timeout == 30.0


class TestErrors:
    """错误类型测试"""

    def test_provider_error(self):
        err = ProviderError("test error", "groq", ErrorKind.TIMEOUT, 504)
        assert err.provider == "groq"
        assert err.kind == ErrorKind.TIMEOUT
        assert err.status_code == 504

    def test_rate_limit_error(self):
        err = RateLimitError("groq", 60)
        assert err.kind == ErrorKind.RATE_LIMIT
        assert err.retry_after == 60

    def test_auth_error(self):
        err = AuthError("openai")
        assert err.kind == ErrorKind.AUTH
        assert err.status_code == 401

    def test_model_not_found(self):
        err = ModelNotFoundError("gpt-5", "openai")
        assert "gpt-5" in str(err)
        assert err.kind == ErrorKind.MODEL_NOT_FOUND

    def test_all_providers_failed(self):
        err = AllProvidersFailedError([("p1", "timeout"), ("p2", "auth")])
        assert len(err.failures) == 2

    def test_configuration_error(self):
        err = ConfigurationError("bad config")
        assert err.kind == ErrorKind.INVALID_REQUEST


class TestState:
    """状态管理测试"""

    def test_load_env_file_nonexistent(self, tmp_path):
        """不存在的 .env 返回空 dict"""
        result = load_env_file(tmp_path / ".env")
        assert result == {}

    def test_load_env_file_basic(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\nEMPTY=\n# comment\n")
        result = load_env_file(env_file)
        assert result["KEY"] == "value"
        assert "EMPTY" in result
        assert "# comment" not in result

    @pytest.mark.asyncio
    async def test_atomic_write_read(self, tmp_path):
        data = {"key": "value", "num": 42}
        test_file = tmp_path / "test.json"
        await write_json_atomic(test_file, data)
        assert test_file.exists()
        result = await read_json(test_file)
        assert result == data

    @pytest.mark.asyncio
    async def test_read_json_default(self, tmp_path):
        result = await read_json(tmp_path / "nonexistent.json", {"default": True})
        assert result == {"default": True}


class TestCooldown:
    """冷却管理测试"""

    @pytest.mark.asyncio
    async def test_cooldown_default_not_cooled(self):
        cd = CooldownManager()
        assert not await cd.is_cooled("test-key")

    @pytest.mark.asyncio
    async def test_cooldown_sets_and_expires(self):
        cd = CooldownManager()
        await cd.set_cooldown("test-key", 0.1)  # 100ms
        assert await cd.is_cooled("test-key")
        import time
        time.sleep(0.15)
        assert not await cd.is_cooled("test-key")

    @pytest.mark.asyncio
    async def test_cooldown_clear_specific(self):
        cd = CooldownManager()
        await cd.set_cooldown("key1", 60)
        await cd.set_cooldown("key2", 60)
        await cd.clear("key1")
        assert not await cd.is_cooled("key1")
        assert await cd.is_cooled("key2")

    @pytest.mark.asyncio
    async def test_cooldown_clear_all(self):
        cd = CooldownManager()
        await cd.set_cooldown("key1", 60)
        await cd.set_cooldown("key2", 60)
        await cd.clear()
        assert not await cd.is_cooled("key1")
        assert not await cd.is_cooled("key2")

    @pytest.mark.asyncio
    async def test_get_remaining_zero_for_unknown(self):
        cd = CooldownManager()
        assert await cd.get_remaining("nonexistent") == 0.0

    @pytest.mark.asyncio
    async def test_get_remaining_positive(self):
        cd = CooldownManager()
        await cd.set_cooldown("test", 60)
        remaining = await cd.get_remaining("test")
        assert 0 < remaining <= 60


class TestRegistry:
    """注册表测试"""

    def test_empty_registry(self):
        reg = Registry()
        assert reg.list_providers() == []
        assert reg.get("nonexistent") is None

    def test_register_and_get(self):
        reg = Registry()
        mock = _MockProvider()
        reg.register("test", mock)
        assert reg.get("test") is mock
        assert "test" in reg.list_providers()

    def test_get_cached_empty(self):
        reg = Registry()
        assert reg.get_cached_models() == []


class _MockProvider:
    """用于测试的模拟 Provider"""
    name = "mock"
    api_version = 1

    async def list_models(self):
        return [{"id": "mock-model", "name": "Mock Model", "is_free": True}]

    async def chat_completion(self, request):
        return ChatResponse(content="mock", model="mock", provider="mock")

    async def chat_completion_stream(self, request):
        yield ChatResponse(content="mock", model="mock", provider="mock", is_stream=True)

    def classify_error(self, exc):
        return ErrorKind.UNKNOWN

    def auth_header(self):
        return {"Authorization": "Bearer mock"}


class TestCombo:
    """Combo 路由引擎测试"""

    @pytest.mark.asyncio
    async def test_combo_fallback_single_member(self):
        reg = Registry()
        cd = CooldownManager()
        await cd.clear()
        engine = ComboEngine(reg, cd)

        mock = _MockProvider()
        reg.register("mock", mock)

        combo = ComboConfig(
            name="test",
            strategy=RoutingStrategy.FALLBACK,
            members=[ComboMember(model="m", provider="mock", priority=0)],
        )

        req = ChatRequest(model="m", messages=[ChatMessage(role="user", content="hi")])
        response = await engine.execute(combo, req)
        assert response.content == "mock"
        assert response.actual_provider == "mock"

    @pytest.mark.asyncio
    async def test_combo_fallback_skips_cooled(self):
        reg = Registry()
        cd = CooldownManager()
        engine = ComboEngine(reg, cd)

        mock = _MockProvider()
        reg.register("mock", mock)
        await cd.set_cooldown("provider:mock", 60)

        combo = ComboConfig(
            name="test",
            strategy=RoutingStrategy.FALLBACK,
            members=[ComboMember(model="m", provider="mock", priority=0)],
        )

        req = ChatRequest(model="m", messages=[ChatMessage(role="user", content="hi")])
        with pytest.raises(AllProvidersFailedError):
            await engine.execute(combo, req)

    @pytest.mark.asyncio
    async def test_combo_round_robin(self):
        reg = Registry()
        cd = CooldownManager()
        await cd.clear()
        engine = ComboEngine(reg, cd)

        mock = _MockProvider()
        reg.register("mock", mock)

        combo = ComboConfig(
            name="rr-test",
            strategy=RoutingStrategy.ROUND_ROBIN,
            members=[
                ComboMember(model="m1", provider="mock", priority=0),
            ],
        )

        req = ChatRequest(model="m1", messages=[ChatMessage(role="user", content="hi")])
        response = await engine.execute(combo, req)
        assert response.content == "mock"


class TestConfigLoader:
    """配置加载器测试"""

    def test_load_providers_from_config(self, tmp_path):
        from openllm.core.config_loader import load_providers_from_config

        config = {
            "providers": {
                "test": {
                    "endpoint": "https://test.com/v1",
                    "api_key": "sk-test",
                    "timeout": 60,
                }
            }
        }
        providers = load_providers_from_config(config, {})
        assert len(providers) == 1
        assert providers[0].name == "test"
        assert providers[0].endpoint == "https://test.com/v1"
        assert providers[0].timeout == 60

    def test_load_providers_env_key(self):
        from openllm.core.config_loader import load_providers_from_config

        config = {
            "providers": {
                "test": {
                    "endpoint": "https://test.com/v1",
                    "api_key_env": "TEST_API_KEY",
                }
            }
        }
        providers = load_providers_from_config(config, {"TEST_API_KEY": "sk-env"})
        assert len(providers) == 1
        assert providers[0].api_key == "sk-env"

    def test_load_providers_skip_no_key(self):
        from openllm.core.config_loader import load_providers_from_config

        config = {"providers": {"test": {"endpoint": "https://test.com/v1"}}}
        providers = load_providers_from_config(config, {})
        assert len(providers) == 0

    def test_load_combos_from_config(self):
        from openllm.core.config_loader import load_combos_from_config

        config = {
            "combos": {
                "auto": {
                    "strategy": "fallback",
                    "members": [
                        {"model": "m1", "provider": "p1", "priority": 0},
                        {"model": "m2", "provider": "p2", "priority": 1},
                    ],
                }
            }
        }
        combos = load_combos_from_config(config)
        assert len(combos) == 1
        assert combos[0].name == "auto"
        assert combos[0].strategy == RoutingStrategy.FALLBACK
        assert len(combos[0].members) == 2
