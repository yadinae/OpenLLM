"""配置加载器边界条件测试"""
from __future__ import annotations

import json

import pytest

from openllm.core.config_loader import (
    find_config,
    load_config,
    load_providers_from_config,
    load_combos_from_config,
)
from openllm.core.types import RoutingStrategy


class TestFindConfig:
    def test_find_config_nonexistent_path(self):
        result = find_config("/nonexistent/path/config.yaml")
        assert result is None

    def test_find_config_explicit_path(self, tmp_path):
        cfg = tmp_path / "openllm.yaml"
        cfg.write_text("key: value")
        result = find_config(cfg)
        assert result == cfg

    def test_find_config_no_config_exists(self):
        # 确保没有配置存在时返回 None
        result = find_config()
        # 可能返回 None 或某个默认路径
        if result is not None:
            assert result.exists()


class TestLoadConfig:
    def test_load_config_no_file(self):
        result = load_config("/nonexistent/path/config.yaml")
        assert result == {}

    def test_load_json_config(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"key": "value", "num": 42}')
        result = load_config(cfg)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_load_yaml_config(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("key: value\nnum: 42\n")
        result = load_config(cfg)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_load_invalid_json(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("{invalid json}")
        with pytest.raises(json.JSONDecodeError):
            load_config(cfg)

    def test_load_invalid_yaml(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(": invalid yaml :")
        import yaml
        with pytest.raises(yaml.YAMLError):
            load_config(cfg)


class TestLoadProvidersFromConfig:
    def test_empty_config(self):
        result = load_providers_from_config({}, {})
        assert result == []

    def test_provider_with_env_key_but_missing_env(self):
        """env_key 指向的环境变量不存在 → api_key 为空 → 跳过"""
        config = {
            "providers": {
                "test": {
                    "endpoint": "https://test.com/v1",
                    "api_key_env": "MISSING_KEY",
                }
            }
        }
        result = load_providers_from_config(config, {})
        assert len(result) == 0

    def test_provider_priority_env_over_api_key(self):
        """api_key_env 优先于 api_key"""
        config = {
            "providers": {
                "test": {
                    "api_key": "direct-key",
                    "api_key_env": "ENV_KEY",
                }
            }
        }
        result = load_providers_from_config(config, {"ENV_KEY": "env-key"})
        assert result[0].api_key == "env-key"

    def test_provider_default_timeout(self):
        config = {"providers": {"test": {"api_key": "sk-test"}}}
        result = load_providers_from_config(config, {})
        assert result[0].timeout == 30.0

    def test_provider_default_max_retries(self):
        config = {"providers": {"test": {"api_key": "sk-test"}}}
        result = load_providers_from_config(config, {})
        assert result[0].max_retries == 2


class TestLoadCombosFromConfig:
    def test_empty_config(self):
        result = load_combos_from_config({})
        assert result == []

    def test_strategy_mapping(self):
        strategies = {
            "fallback": RoutingStrategy.FALLBACK,
            "round_robin": RoutingStrategy.ROUND_ROBIN,
            "round-robin": RoutingStrategy.ROUND_ROBIN,
            "priority": RoutingStrategy.PRIORITY,
            "cost_optimized": RoutingStrategy.COST_OPTIMIZED,
            "unknown_fallback": RoutingStrategy.FALLBACK,
        }
        for strat_name, expected in strategies.items():
            config = {
                "combos": {
                    "test": {
                        "strategy": strat_name,
                        "members": [],
                    }
                }
            }
            result = load_combos_from_config(config)
            assert result[0].strategy == expected, f"Strategy '{strat_name}' mapped to {result[0].strategy}, expected {expected}"

    def test_member_defaults(self):
        config = {
            "combos": {
                "test": {
                    "members": [{"provider": "p1"}],  # 没有 model，没有 priority
                }
            }
        }
        result = load_combos_from_config(config)
        assert result[0].members[0].model == "auto"
        assert result[0].members[0].priority == 0
        assert result[0].members[0].weight == 1.0
