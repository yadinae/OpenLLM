"""Enums and constants for OpenLLM"""

from enum import Enum


class ProtocolType(str, Enum):
    """Protocol type for adapters"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    REST = "rest"
    OLLAMA = "ollama"


class ContextMode(str, Enum):
    """Context management mode"""

    STATIC = "static"
    DYNAMIC = "dynamic"
    RESERVOIR = "reservoir"
    ADAPTIVE = "adaptive"


class ModelType(str, Enum):
    """Model type filter"""

    TEXT = "text"
    CODING = "coding"
    OCR = "ocr"


class ModelScale(str, Enum):
    """Model scale filter"""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class FinishReason(str, Enum):
    """Completion finish reason"""

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
    "context": {
        "mode": "dynamic",
        "max_tokens": 128000,
    },
    "session": {
        "affinity_enabled": True,
        "cache_ttl": 3600,
    },
    "failover": {
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "scoring": {
        "enabled": True,
        "update_interval": 300,
    },
    "sandbox": {
        "enabled": True,
        "max_output_bytes": 50000,
        "timeout_seconds": 30,
        "index_db_path": "~/.openllm/sandbox/content_index.db",
    },
    "session": {
        "affinity_enabled": True,
        "cache_ttl": 3600,
        "event_tracking": True,
        "max_events_per_session": 200,
    },
    "prompt_enhancement": {
        "code_thinking_auto": True,
        "code_thinking_language": "en",
        "terse_enabled": False,
        "terse_intensity": "moderate",
        "terse_language": "en",
    },
}
