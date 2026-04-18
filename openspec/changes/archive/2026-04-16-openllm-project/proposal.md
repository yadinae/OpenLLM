# Proposal: OpenLLM - AI Model Aggregation Platform

## Project Overview

| Field | Value |
|-------|-------|
| **Name** | OpenLLM |
| **Type** | AI Model Aggregation Platform with Scoring |
| **Version** | 1.0.0 |
| **Tech Stack** | Python + FastAPI + Pydantic |
| **Deployment** | Native Python (pip) |
| **Target Users** | Self-hosted users, developers avoiding API costs |

## Problem Statement

Free AI APIs are useful but using them directly has pain points:

- Rate limits cause interruptions
- Multiple providers require different SDKs
- No unified API
- Hard to know which model performs best
- Context management in multi-turn conversations
- No user-friendly extension mechanism

## Solution

Combine RelayFreeLLM's aggregation architecture with FreeRide's scoring approach:

1. **Protocol-Based Adapter Architecture** - Not provider-based, but protocol-based
2. **Automatic Failover** - When rate limited, automatically switch providers
3. **Model Scoring** - Automatic scoring and ranking based on output quality
4. **Rate Control** - Per-model rate/token/concurrent limits
5. **OpenAI-Compatible API** - Drop-in for existing code

## Core Features

| Priority | Feature | Source | Description |
|----------|--------|--------|-------------|
| P0 | Multi-protocol aggregation | RelayFreeLLM | OpenAI/Anthropic/REST/Ollama adapters |
| P0 | Automatic failover | RelayFreeLLM | Auto-switch when rate limited |
| P0 | Model scoring | FreeRide-inspired | Automatic quality scoring |
| P0 | Rate control | New | RPM/TPM/Concurrency/Daily/Cost |
| P0 | Context management | RelayFreeLLM | Static/Dynamic/Reservoir/Adaptive |
| P0 | Session affinity | RelayFreeLLM | Pin users to providers |
| P0 | OpenAI-compatible API | RelayFreeLLM | Standard /v1/chat/completions |
| P1 | CLI management | New | openllm command tool |
| P1 | Configurable extension | New | models.yaml configuration |

## Non-Goals

- Web UI dashboard (future feature)
- Cloud-hosted deployment
- Paid model support
- Embedding/reranking models (v2)

## Dependencies

- **RelayFreeLLM**: Core aggregation logic (reference)
- **FreeRide**: Scoring methodology (reference)
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **pydantic**: Data validation
- **httpx**: Async HTTP client
- **python-dotenv**: Environment variables
- **typer**: CLI framework

## Risks

- Rate limits change frequently - require configurable limits
- Model availability varies - require fallback mechanism
- Scoring algorithms need tuning - use configurable weights
- Protocol variations between providers - require adapter abstraction