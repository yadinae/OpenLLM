"""
Agent Registry — AI Agent 注册、识别与配置管理

解决多 Agent 同时调用 OpenLLM 时的区分问题。

架构设计：
- 每个 Agent 通过 API Key 或 agent_id 识别
- 每个 Agent 有独立配置（默认模型、提示增强、限流、配额）
- 所有 session/sandbox 数据按 agent_id 隔离
- 按 Agent 统计用量和分析

身份识别优先级：
1. X-API-Key 请求头 → 查找注册的 Agent
2. X-Agent-ID 请求头 → 直接使用 agent_id
3. 请求体中的 agent_id 字段 → 兜底
4. 未识别 → 使用 default_agent
"""

import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Data classes
# ============================================================

@dataclass
class AgentQuota:
    """Agent 配额限制"""
    daily_tokens: int = 0          # 每日 token 上限（0 = 无限制）
    daily_requests: int = 0        # 每日请求上限
    rpm: int = 60                  # 每分钟请求数
    tpm: int = 100000              # 每分钟 token 数
    max_context_tokens: int = 128000  # 单次请求最大上下文


@dataclass
class AgentConfig:
    """Agent 配置"""
    agent_id: str = ""
    name: str = ""
    platform: str = ""             # "claude-code", "cursor", "copilot", "gemini-cli", "custom"
    api_key: str = ""
    enabled: bool = True
    default_model: str = ""        # 默认模型（空 = 使用全局默认）
    allowed_models: list = field(default_factory=list)  # 空 = 所有模型可用
    quota: AgentQuota = field(default_factory=AgentQuota)

    # Prompt enhancement defaults
    code_thinking_enabled: bool = True
    terse_enabled: bool = False
    terse_intensity: str = "moderate"

    # Session defaults
    session_tracking_enabled: bool = True
    sandbox_enabled: bool = True

    # Metadata
    created_at: str = ""
    last_used_at: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentUsage:
    """Agent 使用统计"""
    agent_id: str
    today_tokens: int = 0
    today_requests: int = 0
    today_date: str = ""
    total_tokens: int = 0
    total_requests: int = 0
    last_request_at: str = ""


# ============================================================
# Agent Registry
# ============================================================

class AgentRegistry:
    """Agent 注册表

    - 支持内存 + 文件持久化
    - 支持 API Key 查找
    - 支持默认 Agent（未注册请求）
    """

    DEFAULT_AGENT_ID = "default"

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.expanduser("~/.openllm/agents.json")

        self.config_path = config_path
        self._agents: dict[str, AgentConfig] = {}
        self._usage: dict[str, AgentUsage] = {}
        self._api_key_map: dict[str, str] = {}  # api_key → agent_id

        # 创建默认 Agent
        self._agents[self.DEFAULT_AGENT_ID] = AgentConfig(
            agent_id=self.DEFAULT_AGENT_ID,
            name="Default Agent",
            platform="unknown",
            enabled=True,
            code_thinking_enabled=True,
            terse_enabled=False,
        )
        self._usage[self.DEFAULT_AGENT_ID] = AgentUsage(
            agent_id=self.DEFAULT_AGENT_ID,
            today_date=datetime.now().strftime("%Y-%m-%d"),
        )

        # 预注册常见 Agent（无需手动注册即可识别）
        self._pre_register_defaults()

        # 加载持久化配置
        self._load()

    def _pre_register_defaults(self):
        """预注册常见 AI Agent"""
        default_agents = [
            AgentConfig(
                agent_id="nanobot",
                name="Nanobot Agent",
                platform="nanobot",
                enabled=True,
                code_thinking_enabled=True,
                terse_enabled=False,
                default_model="qwen3.6-plus",
                metadata={"description": "Hermes 本地 Agent 系统"},
            ),
            AgentConfig(
                agent_id="hermes",
                name="Hermes Agent",
                platform="hermes",
                enabled=True,
                code_thinking_enabled=True,
                terse_enabled=True,
                terse_intensity="moderate",
                default_model="qwen3.6-plus",
                metadata={"description": "Hermes AI Agent"},
            ),
            AgentConfig(
                agent_id="claude-code",
                name="Claude Code",
                platform="claude-code",
                enabled=True,
                code_thinking_enabled=True,
                terse_enabled=True,
                terse_intensity="moderate",
                default_model="claude-sonnet-4",
                metadata={"description": "Anthropic Claude Code CLI"},
            ),
            AgentConfig(
                agent_id="cursor",
                name="Cursor",
                platform="cursor",
                enabled=True,
                code_thinking_enabled=True,
                terse_enabled=False,
                metadata={"description": "Cursor IDE AI"},
            ),
            AgentConfig(
                agent_id="copilot",
                name="GitHub Copilot",
                platform="copilot",
                enabled=True,
                code_thinking_enabled=False,
                terse_enabled=True,
                terse_intensity="mild",
                metadata={"description": "GitHub Copilot Chat"},
            ),
            AgentConfig(
                agent_id="gemini-cli",
                name="Gemini CLI",
                platform="gemini-cli",
                enabled=True,
                code_thinking_enabled=True,
                terse_enabled=False,
                metadata={"description": "Google Gemini CLI"},
            ),
            AgentConfig(
                agent_id="opencode",
                name="OpenCode",
                platform="opencode",
                enabled=True,
                code_thinking_enabled=True,
                terse_enabled=True,
                terse_intensity="moderate",
                metadata={"description": "OpenCode CLI"},
            ),
        ]

        for agent in default_agents:
            if agent.agent_id not in self._agents:
                self._agents[agent.agent_id] = agent
                self._usage[agent.agent_id] = AgentUsage(
                    agent_id=agent.agent_id,
                    today_date=datetime.now().strftime("%Y-%m-%d"),
                )

        # 加载持久化配置
        self._load()

    def _load(self):
        """从文件加载配置"""
        if not os.path.exists(self.config_path):
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)

            for agent_data in data.get("agents", []):
                quota_data = agent_data.get("quota", {})
                quota = AgentQuota(**quota_data) if quota_data else AgentQuota()

                agent = AgentConfig(
                    agent_id=agent_data["agent_id"],
                    name=agent_data.get("name", agent_data["agent_id"]),
                    platform=agent_data.get("platform", "unknown"),
                    api_key=agent_data.get("api_key", ""),
                    enabled=agent_data.get("enabled", True),
                    default_model=agent_data.get("default_model", ""),
                    allowed_models=agent_data.get("allowed_models", []),
                    quota=quota,
                    code_thinking_enabled=agent_data.get("code_thinking_enabled", True),
                    terse_enabled=agent_data.get("terse_enabled", False),
                    terse_intensity=agent_data.get("terse_intensity", "moderate"),
                    session_tracking_enabled=agent_data.get("session_tracking_enabled", True),
                    sandbox_enabled=agent_data.get("sandbox_enabled", True),
                    created_at=agent_data.get("created_at", ""),
                    last_used_at=agent_data.get("last_used_at", ""),
                    metadata=agent_data.get("metadata", {}),
                )
                self._agents[agent.agent_id] = agent

                if agent.api_key:
                    self._api_key_map[agent.api_key] = agent.agent_id

            # 加载使用统计
            for usage_data in data.get("usage", []):
                usage = AgentUsage(**usage_data)
                self._usage[usage.agent_id] = usage

            logger.info(f"Loaded {len(self._agents)} agents from {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to load agent config: {e}")

    def save(self):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

        data = {
            "agents": [self._agent_to_dict(a) for a in self._agents.values()],
            "usage": [
                {
                    "agent_id": u.agent_id,
                    "today_tokens": u.today_tokens,
                    "today_requests": u.today_requests,
                    "today_date": u.today_date,
                    "total_tokens": u.total_tokens,
                    "total_requests": u.total_requests,
                    "last_request_at": u.last_request_at,
                }
                for u in self._usage.values()
            ],
        }

        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _agent_to_dict(self, agent: AgentConfig) -> dict:
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "platform": agent.platform,
            "api_key": agent.api_key,
            "enabled": agent.enabled,
            "default_model": agent.default_model,
            "allowed_models": agent.allowed_models,
            "quota": {
                "daily_tokens": agent.quota.daily_tokens,
                "daily_requests": agent.quota.daily_requests,
                "rpm": agent.quota.rpm,
                "tpm": agent.quota.tpm,
                "max_context_tokens": agent.quota.max_context_tokens,
            },
            "code_thinking_enabled": agent.code_thinking_enabled,
            "terse_enabled": agent.terse_enabled,
            "terse_intensity": agent.terse_intensity,
            "session_tracking_enabled": agent.session_tracking_enabled,
            "sandbox_enabled": agent.sandbox_enabled,
            "created_at": agent.created_at,
            "last_used_at": agent.last_used_at,
            "metadata": agent.metadata,
        }

    def register(self, config: AgentConfig, generate_api_key: bool = False) -> tuple[bool, str]:
        """注册新 Agent

        Returns:
            (success, api_key) — 如果 generate_api_key=True 或配置中没有 API Key，会自动生成
        """
        if config.agent_id in self._agents:
            logger.warning(f"Agent {config.agent_id} already exists")
            return False, ""

        api_key = config.api_key
        if generate_api_key or not api_key:
            api_key = self._generate_api_key(config.agent_id)
            config.api_key = api_key

        if not config.created_at:
            config.created_at = datetime.now().isoformat()

        self._agents[config.agent_id] = config
        if api_key:
            self._api_key_map[api_key] = config.agent_id

        if config.agent_id not in self._usage:
            self._usage[config.agent_id] = AgentUsage(
                agent_id=config.agent_id,
                today_date=datetime.now().strftime("%Y-%m-%d"),
            )

        self.save()
        logger.info(f"Registered agent: {config.agent_id} ({config.name})")
        return True, api_key

    @staticmethod
    def _generate_api_key(agent_id: str) -> str:
        """生成 API Key: sk-{agent_id}-{random}"""
        random_part = secrets.token_hex(16)
        return f"sk-{agent_id}-{random_part}"

    def unregister(self, agent_id: str) -> bool:
        """注销 Agent（不能注销默认 Agent）"""
        if agent_id == self.DEFAULT_AGENT_ID:
            return False

        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]
        if agent.api_key and agent.api_key in self._api_key_map:
            del self._api_key_map[agent.api_key]

        del self._agents[agent_id]
        self.save()
        logger.info(f"Unregistered agent: {agent_id}")
        return True

    def identify_by_api_key(self, api_key: str) -> Optional[AgentConfig]:
        """通过 API Key 识别 Agent"""
        if not api_key:
            return None

        agent_id = self._api_key_map.get(api_key)
        if agent_id and agent_id in self._agents:
            agent = self._agents[agent_id]
            if agent.enabled:
                return agent

        return None

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """获取 Agent 配置"""
        return self._agents.get(agent_id)

    def get_or_default(self, agent_id: str) -> AgentConfig:
        """获取 Agent，不存在则返回默认"""
        agent = self._agents.get(agent_id)
        if agent and agent.enabled:
            return agent
        return self._agents[self.DEFAULT_AGENT_ID]

    def get_all_agents(self) -> list[AgentConfig]:
        """获取所有 Agent"""
        return list(self._agents.values())

    def identify_from_request(self, headers: dict, body_agent_id: Optional[str] = None, require_auth: bool = False) -> AgentConfig:
        """从请求中识别 Agent

        优先级：
        1. X-API-Key 头 → API Key 查找
        2. X-Agent-ID 头 → 直接使用
        3. body agent_id → 直接使用
        4. 默认 Agent

        Args:
            require_auth: 如果为 True，提供了 X-API-Key 但无效时拒绝（而不是降级到 default）
        """
        # 1. API Key
        api_key = headers.get("x-api-key") or headers.get("X-API-Key")
        if api_key:
            agent = self.identify_by_api_key(api_key)
            if agent:
                return agent
            if require_auth:
                # 提供了 API Key 但无效 → 拒绝
                return None

        # 2. X-Agent-ID header
        agent_id = headers.get("x-agent-id") or headers.get("X-Agent-ID")
        if agent_id:
            return self.get_or_default(agent_id)

        # 3. Body agent_id
        if body_agent_id:
            return self.get_or_default(body_agent_id)

        # 4. Default
        return self._agents[self.DEFAULT_AGENT_ID]

    # ============================================================
    # Usage tracking
    # ============================================================

    def record_usage(self, agent_id: str, tokens: int = 0):
        """记录使用量"""
        if agent_id not in self._usage:
            self._usage[agent_id] = AgentUsage(
                agent_id=agent_id,
                today_date=datetime.now().strftime("%Y-%m-%d"),
            )

        usage = self._usage[agent_id]
        today = datetime.now().strftime("%Y-%m-%d")

        # 重置每日统计
        if usage.today_date != today:
            usage.today_tokens = 0
            usage.today_requests = 0
            usage.today_date = today

        usage.today_tokens += tokens
        usage.today_requests += 1
        usage.total_tokens += tokens
        usage.total_requests += 1
        usage.last_request_at = datetime.now().isoformat()

        # 更新 Agent 最后使用时间
        if agent_id in self._agents:
            self._agents[agent_id].last_used_at = usage.last_request_at

        # 每 10 次请求保存一次
        if usage.today_requests % 10 == 0:
            self.save()

    def get_usage(self, agent_id: str) -> AgentUsage:
        """获取 Agent 使用统计"""
        if agent_id not in self._usage:
            return AgentUsage(agent_id=agent_id)
        return self._usage[agent_id]

    def get_all_usage(self) -> dict[str, AgentUsage]:
        return dict(self._usage)

    def check_quota(self, agent_id: str, tokens: int = 0) -> tuple[bool, str]:
        """检查配额是否超限

        Returns:
            (是否允许, 拒绝原因)
        """
        agent = self.get_or_default(agent_id)
        usage = self.get_usage(agent_id)

        quota = agent.quota

        if quota.daily_requests > 0 and usage.today_requests >= quota.daily_requests:
            return False, f"Daily request limit exceeded ({quota.daily_requests})"

        if quota.daily_tokens > 0 and usage.today_tokens + tokens > quota.daily_tokens:
            return False, f"Daily token limit exceeded ({quota.daily_tokens})"

        return True, ""

    def get_session_prefix(self, agent_id: str) -> str:
        """获取 Agent 的 session 前缀"""
        return f"{agent_id}:"


# ============================================================
# Global instance
# ============================================================

_registry: Optional[AgentRegistry] = None


def get_registry(config_path: Optional[str] = None) -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry(config_path=config_path)
    return _registry


def reset_registry():
    global _registry
    if _registry:
        _registry.save()
    _registry = None
