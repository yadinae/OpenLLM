"""配置加载器 — 从 YAML/JSON 文件加载 Provider 和 Combo 配置"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from openllm.core.types import ProviderConfig, ComboConfig, ComboMember, RoutingStrategy
from openllm.core.state import get_data_dir

logger = logging.getLogger(__name__)


CONFIG_FILENAMES = [
    "openllm.yaml",
    "openllm.json",
    "config.yaml",
    "config.json",
]


def find_config(path: str | Path | None = None) -> Path | None:
    """查找配置文件"""
    if path:
        p = Path(path)
        if p.exists():
            return p
        return None
    
    # 按优先级搜索
    search_dirs = [
        Path.cwd(),
        get_data_dir(),
        Path.home() / ".openllm",
    ]
    for search_dir in search_dirs:
        for filename in CONFIG_FILENAMES:
            p = search_dir / filename
            if p.exists():
                return p
    return None


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载配置文件"""
    config_path = find_config(path)
    if not config_path:
        return {}
    
    content = config_path.read_text()
    if config_path.suffix in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(content) or {}
    return json.loads(content)


def load_providers_from_config(
    config: dict[str, Any],
    env: dict[str, str] | None = None,
) -> list[ProviderConfig]:
    """从配置加载 Provider 列表
    
    配置格式:
    ```yaml
    providers:
      groq:
        endpoint: https://api.groq.com/openai/v1
        api_key_env: GROQ_API_KEY  # 从环境变量读取
        api_key: "..."  # 或直接指定
        timeout: 30
    ```
    """
    if env is None:
        env = dict(os.environ)
    
    providers: list[ProviderConfig] = []
    raw = config.get("providers", {})
    
    for name, cfg in raw.items():
        api_key = cfg.get("api_key", "")
        env_key = cfg.get("api_key_env", "")

        # 优先 env_key，其次 api_key
        if env_key:
            api_key = env.get(env_key, "")

        # 直写 api_key 安全警告
        if cfg.get("api_key") and not env_key:
            logger.warning(
                "Provider '%s': using direct api_key in config file. "
                "Prefer api_key_env to read from environment variable.", name
            )

        if not api_key:
            continue
        
        providers.append(ProviderConfig(
            name=name,
            api_key=api_key,
            endpoint=cfg.get("endpoint", ""),
            extra_headers=cfg.get("headers", {}),
            timeout=cfg.get("timeout", 30.0),
            max_retries=cfg.get("max_retries", 2),
        ))
    
    return providers


def load_combos_from_config(config: dict[str, Any]) -> list[ComboConfig]:
    """从配置加载 Combo 列表
    
    配置格式:
    ```yaml
    combos:
      auto:
        strategy: fallback
        members:
          - model: auto
            provider: openrouter
            priority: 0
          - model: auto
            provider: groq
            priority: 1
    ```
    """
    combos: list[ComboConfig] = []
    raw = config.get("combos", {})
    
    strategy_map = {
        "fallback": RoutingStrategy.FALLBACK,
        "round_robin": RoutingStrategy.ROUND_ROBIN,
        "round-robin": RoutingStrategy.ROUND_ROBIN,
        "priority": RoutingStrategy.PRIORITY,
        "cost_optimized": RoutingStrategy.COST_OPTIMIZED,
    }
    
    for name, cfg in raw.items():
        strategy = strategy_map.get(cfg.get("strategy", "fallback"), RoutingStrategy.FALLBACK)
        members = []
        for m in cfg.get("members", []):
            members.append(ComboMember(
                model=m.get("model", "auto"),
                provider=m.get("provider", ""),
                priority=m.get("priority", 0),
                weight=m.get("weight", 1.0),
            ))
        combos.append(ComboConfig(
            name=name,
            strategy=strategy,
            members=members,
        ))
    
    return combos
