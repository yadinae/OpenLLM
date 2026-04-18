"""Model configuration for adapters"""

from typing import Optional
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for a model adapter"""

    name: str = Field(..., description="Model name")
    protocol: str = Field(..., description="Protocol type: openai, anthropic, rest, ollama")
    endpoint: str = Field(..., description="API endpoint URL")
    api_key: str = Field("", description="API key (supports ${ENV_VAR})")
    enabled: bool = Field(True, description="Enable this model")

    # Rate control
    rpm: int = Field(30, description="Requests per minute")
    tpm: int = Field(15000, description="Tokens per minute")
    max_concurrent: int = Field(10, description="Max concurrent requests")
    daily_limit: int = Field(1000, description="Daily request limit")
    cost_limit: float = Field(0.0, description="Cost limit (USD, 0 = unlimited)")

    # Scoring weights
    quality_weight: float = Field(0.4, description="Quality score weight")
    speed_weight: float = Field(0.3, description="Speed score weight")
    context_weight: float = Field(0.2, description="Context score weight")
    reliability_weight: float = Field(0.1, description="Reliability score weight")

    # Attributes
    max_context_length: int = Field(128000, description="Max context length")
    capabilities: list[str] = Field(default_factory=list, description="Model capabilities")


class AdapterConfig(BaseModel):
    """Base adapter configuration"""

    model: str = Field(..., description="Model name")
    protocol: str = Field(..., description="Protocol type")
    endpoint: str = Field(..., description="API endpoint")
    api_key: str = Field("", description="API key")
    timeout: float = Field(30.0, description="Request timeout")
    headers: dict[str, str] = Field(default_factory=dict, description="Additional headers")

    # REST-specific
    method: Optional[str] = Field(None, description="HTTP method for REST")
    body_template: Optional[str] = Field(None, description="Body template for REST")
