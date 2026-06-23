"""OpenLLM 核心数据类型 — 零外部依赖"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
# from typing import Any  # reserved for future use


class ErrorKind(Enum):
    """标准化错误类型 — 各 Provider 的错误统一映射到此枚举"""
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    MODEL_NOT_FOUND = "model_not_found"
    QUOTA_EXHAUSTED = "quota_exhausted"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    OVERLOADED = "overloaded"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN = "unknown"


class RoutingStrategy(Enum):
    """Combo 路由策略"""
    FALLBACK = "fallback"
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    COST_OPTIMIZED = "cost_optimized"


class ContextMode(Enum):
    """上下文管理模式（参考 RelayFreeLLM）"""
    STATIC = "static"
    DYNAMIC = "dynamic"
    RESERVOIR = "reservoir"
    ADAPTIVE = "adaptive"


class TerseLevel(Enum):
    """Caveman 输出压缩级别（参考 OmniRoute/9router）"""
    OFF = "off"
    LITE = "lite"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    ULTRA = "ultra"


@dataclass
class ModelInfo:
    """模型元信息"""
    id: str
    provider: str
    name: str = ""
    context_length: int = 4096
    is_free: bool = False
    capabilities: list[str] = field(default_factory=lambda: ["text"])


@dataclass
class ChatMessage:
    """统一内部消息格式"""
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ChatRequest:
    """统一内部请求格式"""
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    original_format: str = "openai"
    combo: str | None = None
    terse_level: TerseLevel = TerseLevel.OFF
    rtk_enabled: bool = True
    context_mode: ContextMode = ContextMode.ADAPTIVE
    session_id: str | None = None


@dataclass
class TokenUsage:
    """Token 用量"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """统一内部响应格式"""
    content: str
    model: str
    provider: str
    usage: TokenUsage | None = None
    finish_reason: str = "stop"
    is_stream: bool = False
    actual_provider: str | None = None
    actual_model: str | None = None


@dataclass
class ProviderConfig:
    """Provider 配置"""
    name: str
    api_key: str
    endpoint: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 2
    max_concurrent: int = 8


@dataclass
class ComboMember:
    """Combo 成员"""
    model: str
    provider: str
    priority: int = 0
    weight: float = 1.0


@dataclass
class ComboConfig:
    """Combo 配置"""
    name: str
    strategy: RoutingStrategy = RoutingStrategy.FALLBACK
    members: list[ComboMember] = field(default_factory=list)
