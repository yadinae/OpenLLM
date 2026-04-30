"""Data models for OpenLLM"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Chat message"""

    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class Usage(BaseModel):
    """Token usage information"""

    prompt_tokens: int = Field(0, description="Number of prompt tokens")
    completion_tokens: int = Field(0, description="Number of completion tokens")
    total_tokens: int = Field(0, description="Total number of tokens")


class Choice(BaseModel):
    """Chat completion choice"""

    index: int = Field(..., description="Choice index")
    message: Message = Field(..., description="Response message")
    finish_reason: Optional[str] = Field(None, description="Finish reason")


class ChatResponse(BaseModel):
    """Chat completion response"""

    id: str = Field(..., description="Unique identifier")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[Choice] = Field(..., description="Completion choices")
    usage: Usage = Field(default_factory=Usage, description="Token usage")
    complexity: Optional[str] = Field(None, description="Request complexity level")
    routing_applied: Optional[bool] = Field(None, description="Whether auto-routing was applied")
    recommended_model: Optional[str] = Field(None, description="Recommended model for this request")


class ChatRequest(BaseModel):
    """Chat completion request"""

    model: str = Field("meta-model", description="Model name or meta-model")
    messages: list[Message] = Field(..., description="Chat messages")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(2048, ge=1, description="Max tokens to generate")
    stream: bool = Field(False, description="Enable streaming")
    session_id: Optional[str] = Field(None, description="Session ID for affinity")
    model_type: Optional[str] = Field(None, description="Model type filter")
    model_scale: Optional[str] = Field(None, description="Model scale filter")


class StreamChoice(BaseModel):
    """Streaming choice delta"""

    index: int = Field(..., description="Choice index")
    delta: Message = Field(..., description="Delta message")
    finish_reason: Optional[str] = Field(None, description="Finish reason")


class StreamChatResponse(BaseModel):
    """Streaming chat response"""

    id: str = Field(..., description="Unique identifier")
    object: str = Field("chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[StreamChoice] = Field(..., description="Completion choices")


class ModelInfo(BaseModel):
    """Model information"""

    id: str = Field(..., description="Model ID")
    object: str = Field("model", description="Object type")
    created: int = Field(..., description="Unix timestamp")
    owned_by: str = Field("openllm", description="Model owner")


class ModelList(BaseModel):
    """List of models"""

    object: str = Field("list", description="Object type")
    data: list[ModelInfo] = Field(..., description="Model list")


class EmbeddingRequest(BaseModel):
    """Embedding request"""

    model: str = Field(..., description="Model name")
    input: str | list[str] = Field(..., description="Input text or texts")


class EmbeddingData(BaseModel):
    """Embedding data"""

    object: str = Field("embedding", description="Object type")
    embedding: list[float] = Field(..., description="Embedding vector")
    index: int = Field(..., description="Data index")


class EmbeddingResponse(BaseModel):
    """Embedding response"""

    object: str = Field("list", description="Object type")
    data: list[EmbeddingData] = Field(..., description="Embedding list")
    model: str = Field(..., description="Model used")
    usage: Usage = Field(default_factory=Usage, description="Token usage")


class ChatError(BaseModel):
    """Chat error response"""

    message: str = Field(..., description="Error message")
    type: str = Field("error", description="Error type")
    code: int = Field(..., description="Error code")


class UsageInfo(BaseModel):
    """Usage statistics"""

    total_requests: int = Field(0, description="Total requests")
    total_tokens: int = Field(0, description="Total tokens")
    model_usage: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Per-model usage"
    )
