# OpenLLM Provider & Combo System — Deep Dive

> **Project**: OpenLLM — AI API Gateway (v0.1.0)
> **GitHub**: https://github.com/yadinae/OpenLLM
> **CLI entry**: `openllm = openllm.cli.__init__:app` (via `pyproject.toml` `[project.scripts]`)
> **Framework**: FastAPI + Uvicorn + httpx + typer

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [How Providers Are Configured & Discovered](#2-how-providers-are-configured--discovered)
3. [How Models Are Discovered From Providers](#3-how-models-are-discovered-from-providers)
4. [How Combos Work (Routing Strategies)](#4-how-combos-work-routing-strategies)
5. [How the CLI `serve` Command Works](#5-how-the-cli-serve-command-works)
6. [How to Add New Providers/Models at Runtime](#6-how-to-add-new-providersmodels-at-runtime)
7. [Globals & Module Interdependencies](#7-globals--module-interdependencies)
8. [Resilience Layer](#8-resilience-layer)

---

## 1. Architecture Overview

```
┌──────────────┐     ┌──────────────────────────────────────────────────────┐
│  CLI (typer) │────▶│                  OpenLLM Gateway                       │
│  openllm serve│    │                                                        │
└──────────────┘     │  ┌──────────────┐   ┌──────────────────────────────┐  │
                     │  │  Validation   │   │         Routes              │  │
  ┌──────────┐       │  │  Middleware   │   │  /v1/chat/completions       │  │
  │ .env     │──────▶│  │  (auth,size)  │   │  /v1/messages (Anthropic)  │──┼──▶ OpenAI-compat Provider
  └──────────┘       │  └──────┬───────┘   │  /v1/models                 │  │     (Groq/DeepSeek/NVIDIA/...)
                     │         │           │  /health                    │  │
  ┌──────────┐       │         ▼           └──────────┬───────────────────┘  │
  │openllm   │──────▶│  ┌────────────────────────┐     │                      │
  │.yaml     │       │  │  Route Resolution:     │     │                      │
  └──────────┘       │  │  1. combo name match   │◀────┘                      │
                     │  │  2. provider/model parse│                            │
                     │  │  3. global model search │                            │
                     │  └───────────┬────────────┘                             │
                     │               ▼                                        │
                     │  ┌──────────────────────────────────────┐              │
                     │  │  Core Engine                          │              │
                     │  │  ┌──────────┐  ┌───────────┐        │              │
                     │  │  │ Registry │  │   Combo   │        │              │
                     │  │  │(Provider │◀─│  Engine   │        │              │
                     │  │  │  Map)    │  │(Fallback/ │        │              │
                     │  │  └────┬─────┘  │ RR)       │        │              │
                     │  │       │        └───────────┘        │              │
                     │  │       ▼                             │              │
                     │  │  ┌──────────┐  ┌───────────┐        │              │
                     │  │  │ Circuit  │  │  Cooldown │        │              │
                     │  │  │ Breaker  │  │  Manager  │        │              │
                     │  │  └──────────┘  └───────────┘        │              │
                     │  └──────────────────────────────────────┘              │
                     └──────────────────────────────────────────────────────┘
```

### Key Design Principles

- **Zero-coupling plugin architecture**: The `Provider` Protocol (`openllm/core/provider.py`) defines the interface; core never imports concrete providers.
- **Protocol translation**: Anthropic ↔ OpenAI bidirectional at `/v1/messages` route.
- **Three-tier routing**: Combo name → `provider/model` prefix → global model auto-discovery.

---

## 2. How Providers Are Configured & Discovered

### 2.1 Configuration Sources (Priority Order)

Providers are loaded in `_load_providers()` in `openllm/server/app.py` (lines 69–118):

| Priority | Source | Details |
|----------|--------|---------|
| 1 | **openllm.yaml** (or .json) | Searched in `[cwd, ~/.openllm, ~/.openllm/]` as `openllm.yaml` → `openllm.json` → `config.yaml` → `config.json` |
| 2 | **Hardcoded fallback** (env-based) | If no config file found, falls back to detecting API keys from env vars for known providers |

### 2.2 Config File Format (`openllm.yaml`)

```yaml
providers:
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY   # Read API key from environment variable
    # api_key: "sk-..."             # OR specify directly (discouraged)
    timeout: 30
    headers: {}                     # Extra HTTP headers
    max_retries: 2

  nvidia:
    endpoint: https://integrate.api.nvidia.com/v1
    api_key_env: NVIDIA_API_KEY
    timeout: 60
```

### 2.3 Config Loading Chain

```
openllm/server/app.py:_load_providers()
  │
  ├──1. Gather env vars
  │     ├── os.environ (system env)
  │     └── ~/.openllm/.env  OR  cwd/.env (via load_env_file())
  │
  ├──2. load_config()
  │     └── find_config() → searches in priority dirs for known filenames
  │     └── yaml.safe_load() or json.loads()
  │
  ├──3. load_providers_from_config(config, env)
  │     └── For each provider in config:
  │           ├── Resolve api_key: api_key_env → env var, or direct api_key
  │           ├── Skip if no api_key found
  │           └── Create ProviderConfig dataclass
  │
  └──4. For each ProviderConfig → OpenAICompatProvider(cfg) → registry.register(name, provider)
```

### 2.4 Hardcoded Fallback Providers

If no config file is found, `_load_providers()` falls back to this hardcoded dict:

```python
provider_configs = {
    "openrouter": {"env_key": "OPENROUTER_API_KEY", "endpoint": "https://openrouter.ai/api/v1"},
    "groq":       {"env_key": "GROQ_API_KEY",       "endpoint": "https://api.groq.com/openai/v1"},
    "deepseek":   {"env_key": "DEEPSEEK_API_KEY",   "endpoint": "https://api.deepseek.com/v1"},
    "nvidia":     {"env_key": "NVIDIA_API_KEY",     "endpoint": "https://integrate.api.nvidia.com/v1"},
    "cerebras":   {"env_key": "CEREBRAS_API_KEY",   "endpoint": "https://api.cerebras.ai/v1"},
}
```

Any provider with a matching env var will be auto-registered.

### 2.5 The `Provider` Protocol (`openllm/core/provider.py`)

A `@runtime_checkable` Protocol (structural typing) requiring:

```python
class Provider(Protocol):
    name: str
    api_version: int = 1

    async def list_models(self) -> list[dict]: ...
    async def chat_completion(self, request: ChatRequest) -> ChatResponse: ...
    async def chat_completion_stream(self, request: ChatRequest) -> AsyncIterator[ChatResponse]: ...
    async def close(self) -> None: ...
    def classify_error(self, exc: Exception) -> ErrorKind: ...
    def auth_header(self) -> dict[str, str]: ...
    @property
    def attribution_header(self) -> dict[str, str]: ...
```

The core engine NEVER imports concrete provider classes — it only depends on the `Provider` protocol. This is the "zero-coupling plugin" design.

### 2.6 The `Registry` (`openllm/core/registry.py`)

```python
class Registry:
    _providers: dict[str, Provider]      # name → Provider instance
    _models_cache: dict[str, list[dict]]  # provider_name → models list

    def register(name, provider)          # Register a provider
    def get(name) -> Provider | None      # Get provider by name
    def list_providers() -> list[str]     # List all registered names
    async def discover_models()           # Call list_models() on EVERY provider
    def get_cached_models() -> list[dict] # Flattened model list (flat with provider field)
    def save_snapshot()                   # Persist registry.json
```

---

## 3. How Models Are Discovered From Providers

### 3.1 Discovery Flow

Triggered at server startup in the `lifespan` context manager:

```
openllm/server/app.py:lifespan()
  │
  └── _load_providers()
        │
        └── registry.discover_models()
              │
              ├── For each registered provider:
              │     └── await provider.list_models()
              │           └── OpenAICompatProvider calls GET /v1/models
              │               on the upstream endpoint
              │
              └── self._models_cache = {provider_name: [{"id": ..., "name": ...}, ...]}
                    │
                    └── registry.save_snapshot()
                          └── Writes registry.json to ~/.openllm/
```

### 3.2 `OpenAICompatProvider.list_models()` (`openllm/providers/openai_compat.py`)

```python
async def list_models(self) -> list[dict]:
    client = await self._get_client()
    resp = await client.get("/v1/models")
    resp.raise_for_status()
    data = resp.json()
    return [
        {"id": m["id"], "name": m["id"], "is_free": False}
        for m in data.get("data", [])
    ]
```

Returns an empty list on error (never raises).

### 3.3 Model Auto-Discovery in Routes

When a user requests a model, the chat route (`openllm/server/routes/chat.py`) tries three resolution strategies:

| Step | Strategy | Example |
|------|----------|---------|
| 1 | **Combo lookup** — match `model` as combo name | `"auto"` → finds combo config |
| 2 | **Provider/model parse** — split on `/` | `"deepseek/deepseek-chat"` → provider=deepseek, model=deepseek-chat |
| 3 | **Global model search** — scan cached models | `"llama-3-70b"` → find which provider has it |

The global search (`_find_model_globally`):
```python
def _find_model_globally(model: str) -> tuple[str, str] | None:
    cached = registry.get_cached_models()
    for m in cached:
        if m["id"] == model:                     # exact match on model id
            return m["provider"], m["id"]
    for pname in registry.list_providers():
        if pname == model:                       # exact match on provider name
            return pname, "auto"
    return None
```

### 3.4 Model Listing API (`GET /v1/models`)

Returns all cached models in OpenAI-compatible format:

```
GET /v1/models → {
  "object": "list",
  "data": [
    {"id": "deepseek/deepseek-chat", "object": "model", "created": 0, "owned_by": "deepseek"},
    {"id": "nvidia/llama-3.1-8b", ...},
    ...
  ]
}
```

Note: Models are returned as `provider/model_id` format for easy routing.

---

## 4. How Combos Work (Routing Strategies)

### 4.1 Combo Configuration Schema

Defined in `openllm.yaml` under the `combos:` key:

```yaml
combos:
  auto:                         # Combo name — clients use this as the "model" value
    strategy: fallback          # Routing strategy
    members:
      - model: auto             # Model to pass to the provider (or "auto")
        provider: opencode      # Provider name (must match a registered provider)
        priority: 0             # Lower number = higher priority
      - model: auto
        provider: deepseek
        priority: 1
      - model: auto
        provider: router
        priority: 2
      - model: auto
        provider: nvidia
        priority: 3

  fast:
    strategy: fallback
    members:
      - model: auto
        provider: opencode
        priority: 0
      - model: auto
        provider: deepseek
        priority: 1

  free:
    strategy: fallback
    members:
      - model: auto
        provider: opencode
        priority: 0
```

### 4.2 Data Types (`openllm/core/types.py`)

```python
class RoutingStrategy(Enum):
    FALLBACK = "fallback"          # Try in priority order, stop on first success
    ROUND_ROBIN = "round_robin"    # Distribute load across members
    PRIORITY = "priority"          # Always try highest priority first, fallback on failure
    COST_OPTIMIZED = "cost_optimized"  # Future: cost-aware routing

@dataclass
class ComboMember:
    model: str         # Model name to send to this provider (usually "auto")
    provider: str      # Provider name matching a registered provider
    priority: int = 0  # 0 = highest priority
    weight: float = 1.0  # For future weighted strategies

@dataclass
class ComboConfig:
    name: str
    strategy: RoutingStrategy = RoutingStrategy.FALLBACK
    members: list[ComboMember] = field(default_factory=list)
```

### 4.3 Combo Engine (`openllm/core/combo.py`)

The `ComboEngine` is initialized with:

```python
combo_engine = ComboEngine(registry, cooldown)
```

It maintains `self._rr_index: dict[str, int]` for round-robin state.

#### 4.3.1 Fallback Strategy (`_execute_fallback`)

```python
async def _execute_fallback(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
    sorted_members = sorted(combo.members, key=lambda m: m.priority)  # 0, 1, 2, ...
    failures = []

    for member in sorted_members:
        # 1. Skip if cooled
        if cooldown.is_cooled(f"provider:{member.provider}"):
            failures.append((member.provider, "cooled"))
            continue
        # 2. Skip if not registered
        provider = registry.get(member.provider)
        if not provider:
            failures.append((member.provider, "not registered"))
            continue
        # 3. Try the provider
        try:
            response = await provider.chat_completion(internal_req)
            response.actual_provider = member.provider
            response.actual_model = member.model
            return response          # First success wins
        except ProviderError as e:
            _record_failure(member.provider, e)  # Auto-set cooldown
            failures.append(...)
            continue                  # Try next member
    raise AllProvidersFailedError(failures)
```

#### 4.3.2 Round-Robin Strategy (`_execute_round_robin`)

```python
async def _execute_round_robin(self, combo, request):
    # Filter out cooled members
    available = [m for m in combo.members if not cooldown.is_cooled(f"provider:{m.provider}")]
    if not available:
        raise AllProvidersFailedError([("all", "no available providers")])

    start_idx = self._rr_index.get(combo.name, 0) % len(available)
    for offset in range(len(available)):
        idx = (start_idx + offset) % len(available)
        member = available[idx]
        self._rr_index[combo.name] = idx + 1   # Advance pointer

        # Try this member; on failure, try next (like fallback)
        try:
            response = await provider.chat_completion(...)
            return response
        except ProviderError as e:
            _record_failure(member.provider, e)
            continue
    raise AllProvidersFailedError(failures)
```

#### 4.3.3 Streaming Fallback (`execute_stream`)

The stream implementation uses "first-chunk locking":

```python
async def execute_stream(self, combo, request):
    for member in sorted_members:
        if cooled or not registered: continue
        try:
            stream = provider.chat_completion_stream(req)
            first_chunk = await stream.__anext__()
            # Lock: first chunk arrived → forward it and the rest
            yield first_chunk
            async for chunk in stream:
                yield chunk
            return
        except StopAsyncIteration:
            failures.append(...)     # Empty stream, try next provider
        except ProviderError as e:
            _record_failure(...)     # Failed, try next provider
            continue
    # All failed
```

### 4.4 How Combos Are Loaded

In `_load_providers()`:

```python
config = load_config()
providers_from_config = load_providers_from_config(config, env)
combos = load_combos_from_config(config)

if providers_from_config:
    # ... register providers ...
    _loaded_combos = {c.name: c for c in combos}     # Store globally
```

The `combos` dict is stored as module-global `_loaded_combos` in `openllm/server/app.py` and accessed via `get_combos()`.

### 4.5 How Combos Are Invoked

In the chat route (`openllm/server/routes/chat.py`):

```python
combo = _find_combo(model)    # Look up model name as combo key
if combo:
    if is_stream:
        return StreamingResponse(_stream_combo(combo.name, internal_req), ...)
    response = await combo_engine.execute(combo, internal_req)
```

So a client can simply set `model: "auto"` (or any combo name) and get automatic fallback routing.

### 4.6 Cooldown Integration

When a provider fails, `_record_failure()` automatically sets a cooldown:

```python
def _record_failure(provider_name, exc):
    if isinstance(exc, RateLimitError):
        cooldown.set_cooldown(f"provider:{provider_name}", 120, "rate_limit")
    elif isinstance(exc, AuthError):
        cooldown.set_cooldown(f"provider:{provider_name}", 300, "auth")
    elif isinstance(exc, ProviderError):
        cooldown.set_cooldown(f"provider:{provider_name}", duration, exc.kind.value)
    else:
        cooldown.set_cooldown(f"provider:{provider_name}", 60, "unknown")
```

Cooldown durations by error type:

| Error Kind | Duration |
|------------|----------|
| `rate_limit` | 120s |
| `auth` | 300s |
| `quota_exhausted` | 3600s (1 hour) |
| `timeout` | 30s |
| `server_error` | 60s |
| `overloaded` | 120s |
| `model_not_found` | 600s (10 min) |
| unknown | 60s |

---

## 5. How the CLI `serve` Command Works

### 5.1 Entry Point Chain

```
Shell: openllm serve
  │
  └── pyproject.toml: [project.scripts] openllm = "openllm.cli.__init__:app"
        │
        └── openllm/cli/__init__.py: app = typer.Typer()
              │
              └── @app.command() def serve(...):
                    │
                    └── 1. logging.basicConfig(...)
                    │
                    └── 2. from openllm.server import create_app
                    │       app = create_app(api_key=api_key)
                    │
                    └── 3. uvicorn.run(app, host=host, port=port, ...)
```

### 5.2 `serve` Command Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--host` / `-H` | `127.0.0.1` | Bind address |
| `--port` / `-p` | `11343` | Port |
| `--log-level` / `-l` | `"info"` | Log level |
| `--reload` | `False` | Hot reload (dev mode) |
| `--api-key` / `-k` | `None` | API auth key (Bearer Token) |

### 5.3 `create_app()` Factory (`openllm/server/app.py`)

```python
def create_app(api_key: str | None = None) -> FastAPI:
    # Set global api_key
    # Build FastAPI with lifespan

    @asynccontextmanager
    async def lifespan(app):
        _load_providers()          # Step 1: Load config, register providers
        await registry.discover_models()  # Step 2: Auto-discover models from each provider
        registry.save_snapshot()   # Step 3: Save registry.json
        health_task = asyncio.create_task(_health_check_loop())  # Step 4: Background health check
        yield
        # Shutdown: cancel health task, close all provider HTTP clients
```

### 5.4 Other CLI Commands

| Command | Description |
|---------|-------------|
| `openllm serve` | Start the gateway server |
| `openllm list-providers` | List registered providers with model counts |
| `openllm doctor` | Diagnostic check — verifies config and provider connectivity |
| `openllm bind <agent>` | Configure client tools (aider/continue/hermes/openclaw/claude-code) |

---

## 6. How to Add New Providers/Models at Runtime

### 6.1 Adding a New Provider (Config File Method)

**Step 1**: Add to `openllm.yaml`:

```yaml
providers:
  my_provider:
    endpoint: https://api.myprovider.com/v1
    api_key_env: MY_PROVIDER_API_KEY
    timeout: 30
```

**Step 2**: Set the env var:

```bash
export MY_PROVIDER_API_KEY=sk-...
```

**Step 3**: Restart the server. The provider is auto-discovered on startup.

### 6.2 Adding a New Provider (Environment Variable Fallback)

If using the hardcoded fallback (no config file), the code already has:

```python
provider_configs = {
    "openrouter": {"env_key": "OPENROUTER_API_KEY", "endpoint": "https://openrouter.ai/api/v1"},
    "groq":       {"env_key": "GROQ_API_KEY", ...},
    "deepseek":   {"env_key": "DEEPSEEK_API_KEY", ...},
    "nvidia":     {"env_key": "NVIDIA_API_KEY", ...},
    "cerebras":   {"env_key": "CEREBRAS_API_KEY", ...},
}
```

To add a new provider here, add a new entry AND modify `openllm/server/app.py`.

### 6.3 Adding a Custom Provider Implementation

For non-OpenAI-compatible APIs (e.g., Anthropic native, Google Gemini native):

1. **Create a new file** in `openllm/providers/` (e.g., `anthropic_native.py`)
2. **Implement the `Provider` protocol**:
   - `list_models()`
   - `chat_completion()`
   - `chat_completion_stream()`
   - `close()`
   - `classify_error()`
   - `auth_header()`
3. **Register it** — currently done in `_load_providers()` in `app.py`. Modify:

```python
# In _load_providers(), after config-based loading
if providers_from_config:
    for cfg in providers_from_config:
        if cfg.name == "anthropic_native":
            from openllm.providers.anthropic_native import AnthropicNativeProvider
            provider = AnthropicNativeProvider(cfg)
        else:
            provider = OpenAICompatProvider(cfg)
        registry.register(cfg.name, provider)
```

### 6.4 Adding a New Combo (Runtime Config)

Simply edit `openllm.yaml`:

```yaml
combos:
  my_combo:
    strategy: fallback
    members:
      - model: auto
        provider: deepseek
        priority: 0
      - model: auto
        provider: nvidia
        priority: 1
```

Then restart the server. Clients can now use `model: "my_combo"`.

### 6.5 Dynamic/Programmatic Registration

The `Registry` supports live registration:

```python
from openllm.server.app import registry
from openllm.core.types import ProviderConfig
from openllm.providers.openai_compat import OpenAICompatProvider

cfg = ProviderConfig(name="new_provider", api_key="sk-...", endpoint="https://...")
provider = OpenAICompatProvider(cfg)
registry.register("new_provider", provider)
```

However, model discovery is a one-time event at startup. To trigger rediscovery:

```python
await registry.discover_models()
```

### 6.6 The `model: auto` Convention

When a combo member specifies `model: auto`, the provider receives `"auto"` as the model name. The `OpenAICompatProvider._extract_model_name()` strips the provider prefix:

```python
def _extract_model_name(self, model: str) -> str:
    if "/" in model:
        return model.split("/", 1)[1]
    return model
```

So `"auto"` → "auto" → sent to upstream as `"auto"`. Many providers (like OpenRouter) auto-select the model when `"auto"` is sent.

---

## 7. Globals & Module Interdependencies

The server module (`openllm/server/app.py`) manages all global singletons:

```python
# In openllm/server/app.py (module level):
registry = Registry()                    # Provider registry
cooldown = CooldownManager()             # Cooldown state (persisted)
combo_engine = ComboEngine(registry, cooldown)  # Routing engine
circuit_breaker = CircuitBreaker()       # Circuit breaker (in-memory)
_loaded_combos: dict[str, object] = {}   # Combo configs
_api_key: str | None = None              # Auth key
```

These are consumed by:

| Module | Uses |
|--------|------|
| `routes/chat.py` | `registry`, `combo_engine`, `cooldown`, `circuit_breaker`, `get_combos()` |
| `routes/messages.py` | `registry`, `cooldown` |
| `routes/models.py` | `registry` |
| `routes/health.py` | `registry` |
| `cli/__init__.py` (list/doctor) | `registry` (via `create_app()`) |

### Dependency Graph

```
cli/__init__.py (serve)
  └── server/app.py (create_app)
        ├── core/config_loader.py → core/types.py
        ├── core/registry.py → core/provider.py (Protocol)
        ├── core/combo.py → core/types.py, core/errors.py, core/cooldown.py
        ├── core/cooldown.py → core/state.py
        ├── core/circuit.py  (standalone)
        ├── core/state.py    (standalone)
        ├── providers/openai_compat.py → core/provider.py, core/types.py, core/errors.py, core/retry.py
        ├── core/retry.py → core/errors.py
        ├── server/validation.py  (standalone)
        ├── server/routes/chat.py → server/app.py (globals), core/types.py, server/validation.py
        ├── server/routes/messages.py → server/app.py, core/types.py, translate/anthropic_translate.py
        └── server/routes/models.py → server/app.py
```

---

## 8. Resilience Layer

### 8.1 Validation (`openllm/server/validation.py`)

| Check | Limit |
|-------|-------|
| Messages per request | ≤ 200 |
| Single message content | ≤ 50,000 chars |
| Request body size | ≤ 2 MB |
| Model name length | ≤ 256 chars |
| Path traversal | Reject `..` |
| Chunked transfer encoding | Rejected (blocks bypass) |

### 8.2 Circuit Breaker (`openllm/core/circuit.py`)

State machine: `CLOSED → OPEN → HALF_OPEN → CLOSED`

| Parameter | Value |
|-----------|-------|
| Failure threshold | 5 consecutive failures |
| Open timeout | 60 seconds |
| Half-open successes needed | 3 consecutive successes |
| Max tracked keys (LRU) | 100 |

### 8.3 Retry (`openllm/core/retry.py`)

| Parameter | Value |
|-----------|-------|
| Max retries | 3 |
| Base delay | 1s (exponential backoff: 1→2→4s) |
| Max delay | 60s |
| Retryable statuses | 429, 500, 502, 503, 504 |
| Not retryable | `AuthError` |

### 8.4 Health Check Loop

```python
async def _health_check_loop():
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        for name in providers:
            try:
                models = await provider.list_models()  # Probe /v1/models
                circuit_breaker.record_success(name)   # Reset failures
            except Exception as e:
                circuit_breaker.record_failure(name)   # May trigger circuit open
```

### 8.5 Cooldown Persistence (`openllm/core/cooldown.py`)

Cooldowns are persisted to `~/.openllm/cooldown.json` using atomic writes (tmp + rename). This means cooldowns survive server restarts.

---

## Appendix: Key File Reference

| File | Purpose |
|------|---------|
| `openllm/cli/__init__.py` | CLI entry: `serve`, `list-providers`, `doctor`, `bind` commands |
| `openllm/cli/binder.py` | One-click agent config (aider/continue/hermes/claude-code) |
| `openllm/server/app.py` | FastAPI factory, globals, `_load_providers()`, health check loop |
| `openllm/server/validation.py` | Request size/content validation |
| `openllm/server/routes/chat.py` | `/v1/chat/completions` — main routing logic |
| `openllm/server/routes/messages.py` | `/v1/messages` — Anthropic compat endpoint |
| `openllm/server/routes/models.py` | `/v1/models` — model listing |
| `openllm/server/routes/health.py` | `/health` — health check |
| `openllm/core/types.py` | All dataclasses and enums |
| `openllm/core/provider.py` | `Provider` Protocol (plugin interface) |
| `openllm/core/config_loader.py` | YAML/JSON config loading |
| `openllm/core/registry.py` | Provider registry + model cache |
| `openllm/core/combo.py` | Combo engine (fallback/RR routing) |
| `openllm/core/cooldown.py` | Cooldown manager (persisted) |
| `openllm/core/circuit.py` | Circuit breaker (LRU + state machine) |
| `openllm/core/retry.py` | Exponential backoff retry |
| `openllm/core/errors.py` | Error type hierarchy |
| `openllm/core/state.py` | JSON/state file utilities |
| `openllm/providers/openai_compat.py` | OpenAI-compatible API adapter |
| `openllm/translate/base.py` | Protocol translator base class |
| `openllm/translate/anthropic_translate.py` | Anthropic ↔ OpenAI translator |
| `openllm/context/manager.py` | Context optimization (4 strategies) |
| `openllm/optimize/rtk.py` | Tool output compression |
| `openllm.yaml` | Current live config |
| `openllm.example.yaml` | Example config template |
| `.env.example` | Example environment variables |
