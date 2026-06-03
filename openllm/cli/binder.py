"""CLI bind — 一键配置客户端工具

参考 FreeRide bind 设计：幂等地将 OpenLLM 网关配置写入客户端配置文件。
"""

from __future__ import annotations

import os
from pathlib import Path


BINDERS: dict[str, dict] = {
    "aider": {
        "file": "~/.aider.conf.yml",
        "config": (
            "openllm-api-key: any-key\n"
            "openllm-api-base: http://{host}:{port}/v1\n"
        ),
    },
    "continue": {
        "file": "~/.continue/config.json",
        "config": (
            '{{\n'
            '  "models": [{{\n'
            '    "title": "OpenLLM",\n'
            '    "provider": "openai",\n'
            '    "model": "auto",\n'
            '    "apiKey": "any-key",\n'
            '    "apiBase": "http://{host}:{port}/v1"\n'
            '  }}]\n'
            '}}\n'
        ),
    },
    "hermes": {
        "file": "~/.hermes/config.yaml",
        "instruction": (
            "Add to ~/.hermes/config.yaml:\n"
            "  providers:\n"
            "    openllm:\n"
            "      base_url: http://{host}:{port}/v1\n"
            "      api_key: any-key\n"
            "      model: auto\n"
        ),
    },
    "openclaw": {
        "file": "~/.openclaw/config.yaml",
        "config": (
            "auth:\n"
            "  profiles:\n"
            "    openllm:\n"
            "      base_url: http://{host}:{port}/v1\n"
            "      api_key: any-key\n"
        ),
    },
    "claude-code": {
        "file": "~/.claude/claude.json",
        "config": (
            '{{\n'
            '  "anthropic_api_base": "http://{host}:{port}/v1",\n'
            '  "anthropic_api_key": "any-key"\n'
            '}}\n'
        ),
    },
}


def bind_agent(
    agent: str,
    host: str = "127.0.0.1",
    port: int = 11343,
) -> str:
    """配置客户端工具指向 OpenLLM 网关
    
    Args:
        agent: 工具名称 (aider/continue/hermes/openclaw/claude-code)
        host: OpenLLM 地址
        port: 端口
    
    Returns:
        操作结果描述
    """
    binder = BINDERS.get(agent)
    if not binder:
        agents = ", ".join(BINDERS.keys())
        return f"Unknown agent '{agent}'. Supported: {agents}"
    
    file_path = os.path.expanduser(binder["file"])
    config_template = binder.get("config", "")
    instruction = binder.get("instruction", "")
    
    if config_template:
        config = config_template.format(host=host, port=port)
        # 确保父目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已配置
        if os.path.exists(file_path):
            content = Path(file_path).read_text()
            if "openllm" in content.lower() or "OpenLLM" in content:
                return f"⚠️  {agent} already configured at {file_path}. Remove previous OpenLLM config first."
        
        Path(file_path).write_text(config)
        return f"✅ Configured {agent} → http://{host}:{port}/v1 at {file_path}"
    
    return f"{instruction.format(host=host, port=port)}"
