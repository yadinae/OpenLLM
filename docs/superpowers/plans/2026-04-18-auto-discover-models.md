# Auto Discover Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add capability to automatically discover available models from configured providers and register them in the model registry.

**Architecture:** On startup/discovery trigger, iterate through configured adapters, call their list_available_models() API, create ModelConfig entries with enabled: False, and save to models.yaml.

**Tech Stack:** Python, httpx, PyYAML, Pydantic

---

### Task 1: Add list_available_models to base adapter

**Files:**
- Modify: `openllm/src/adapters/base.py:78-81`

- [ ] **Step 1: Read the current base.py**

Run: `cat openllm/src/adapters/base.py`
Expected: Show lines 78-81 with get_model_info method

- [ ] **Step 2: Add list_available_models method**

```python
async def list_available_models(self) -> list[ModelInfo]:
    """List all available models from provider."""
    return [await self.get_model_info()]
```

Add this method after `get_model_info` (after line 81).

- [ ] **Step 3: Commit**

```bash
git add openllm/src/adapters/base.py
git commit -m "feat: add list_available_models to base adapter"
```

---

### Task 2: Implement list_available_models for Ollama

**Files:**
- Modify: `openllm/src/adapters/ollama.py:85-100`

- [ ] **Step 1: Read ollama.py around get_model_info**

Run: `cat openllm/src/adapters/ollama.py`
Expected: Show existing get_model_info method

- [ ] **Step 2: Implement list_available_models**

Replace current get_model_info with:

```python
async def list_available_models(self) -> list[ModelInfo]:
    """List all available models from Ollama."""
    client = await self.get_client()
    try:
        response = await client.get("/api/tags")
        data = response.json()
        models = data.get("models", [])
        return [
            ModelInfo(
                id=m.get("name", ""),
                created=int(time.time()),
                owned_by="ollama"
            )
            for m in models
            if m.get("name")
        ]
    except Exception:
        return [await self.get_model_info()]
```

- [ ] **Step 3: Commit**

```bash
git add openllm/src/adapters/ollama.py
git commit -m "feat: implement list_available_models for Ollama"
```

---

### Task 3: Implement list_available_models for OpenAI

**Files:**
- Modify: `openllm/src/adapters/openai.py:81-93`

- [ ] **Step 1: Read openai.py**

Run: `cat openllm/src/adapters/openai.py`
Expected: Show get_model_info method

- [ ] **Step 2: Implement list_available_models**

Add after get_model_info:

```python
async def list_available_models(self) -> list[ModelInfo]:
    """List all available models from OpenAI."""
    client = await self.get_client()
    try:
        response = await client.get("/v1/models")
        data = response.json()
        model_list = data.get("data", [])
        return [
            ModelInfo(
                id=m.get("id", ""),
                created=m.get("created", int(time.time())),
                owned_by=m.get("owned_by", "openai")
            )
            for m in model_list
            if m.get("id")
        ]
    except Exception:
        return [await self.get_model_info()]
```

- [ ] **Step 3: Commit**

```bash
git add openllm/src/adapters/openai.py
git commit -m "feat: implement list_available_models for OpenAI"
```

---

### Task 4: Implement list_available_models for Anthropic

**Files:**
- Modify: `openllm/src/adapters/anthropic.py:97-98`

- [ ] **Step 1: Read anthropic.py**

Run: `cat openllm/src/adapters/anthropic.py`
Expected: Show current get_model_info ( Anthropic has limited API)

- [ ] **Step 2: Add list_available_models**

```python
async def list_available_models(self) -> list[ModelInfo]:
    """List available models from Anthropic."""
    return [await self.get_model_info()]
```

Add after get_model_info method.

- [ ] **Step 3: Commit**

```bash
git add openllm/src/adapters/anthropic.py
git commit -m "feat: add list_available_models for Anthropic"
```

---

### Task 5: Implement list_available_models for REST

**Files:**
- Modify: `openllm/src/adapters/rest.py:105-106`

- [ ] **Step 1: Read rest.py**

Run: `cat openllm/src/adapters/rest.py`
Expected: Show current get_model_info method

- [ ] **Step 2: Add list_available_models**

```python
async def list_available_models(self) -> list[ModelInfo]:
    """List available models from REST provider."""
    client = await self.get_client()
    try:
        response = await client.get("/models")
        data = response.json()
        models = data.get("models", [])
        return [
            ModelInfo(
                id=m.get("id", m.get("name", "")),
                created=m.get("created", int(time.time())),
                owned_by=m.get("owned_by", "custom")
            )
            for m in models
        ]
    except Exception:
        return [await self.get_model_info()]
```

- [ ] **Step 3: Commit**

```bash
git add openllm/src/adapters/rest.py
git commit -m "feat: implement list_available_models for REST"
```

---

### Task 6: Add discover_models to ModelRegistry

**Files:**
- Modify: `openllm/src/registry.py`

- [ ] **Step 1: Read registry.py**

Run: `cat openllm/src/registry.py`
Expected: Show full registry code

- [ ] **Step 2: Add discover_models method**

Add after line 96 (after close_all method):

```python
async def discover_models(self, config_path: str | Path) -> list[ModelConfig]:
    """Discover models from all configured providers."""
    from pathlib import Path as PathType
    from openllm.src.models import ModelInfo

    config_path = PathType(config_path)
    discovered = []

    for model in self._models.values():
        adapter = self.get_or_create_adapter(model.name)
        if not adapter:
            continue

        try:
            model_infos = await adapter.list_available_models()
            for mi in model_infos:
                if mi.id in self._models:
                    continue

                config = ModelConfig(
                    name=mi.id,
                    protocol=model.protocol,
                    endpoint=model.endpoint,
                    api_key=model.api_key,
                    enabled=False,
                    rpm=model.rpm,
                    tpm=model.tpm,
                    max_concurrent=model.max_concurrent,
                    daily_limit=model.daily_limit,
                    quality_weight=model.quality_weight,
                    speed_weight=model.speed_weight,
                    context_weight=model.context_weight,
                    reliability_weight=model.reliability_weight,
                    max_context_length=model.max_context_length,
                    capabilities=model.capabilities,
                )
                self._models[config.name] = config
                discovered.append(config)
                logger.info(f"Discovered model: {config.name}")
        except Exception as e:
            logger.warning(f"Failed to discover from {model.name}: {e}")

    if discovered:
        self._save_to_yaml(config_path, discovered)

    return discovered
```

- [ ] **Step 3: Add _save_to_yaml helper method**

Add after discover_models:

```python
def _save_to_yaml(self, config_path: Path, new_models: list[ModelConfig]):
    """Save newly discovered models to YAML config."""
    import yaml

    existing_data = {}
    if config_path.exists():
        with open(config_path) as f:
            existing_data = yaml.safe_load(f) or {}

    existing_models = existing_data.get("models", [])
    existing_names = {m.get("name") for m in existing_models}

    for new_model in new_models:
        if new_model.name not in existing_names:
            existing_models.append(new_model.model_dump())

    existing_data["models"] = existing_models

    with open(config_path, "w") as f:
        yaml.safe_dump(existing_data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved {len(new_models)} new models to {config_path}")
```

- [ ] **Step 4: Commit**

```bash
git add openllm/src/registry.py
git commit -m "feat: add discover_models to ModelRegistry"
```

---

### Task 7: Add CLI discover command

**Files:**
- Modify: `openllm/cli/main.py`

- [ ] **Step 1: Read cli/main.py**

Run: `cat openllm/cli/main.py`
Expected: Show existing CLI commands

- [ ] **Step 2: Add discover command**

Import: Add `from openllm.src.registry import get_registry` if not present

Add new command after models_cmd:

```python
@cli.command("discover")
def discover_cmd():
    """Discover available models from providers"""
    import asyncio
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

    async def run():
        registry = get_registry()
        registry.load_from_yaml(config_path)
        discovered = await registry.discover_models(config_path)

        if not discovered:
            typer.echo("No new models discovered")
            return

        typer.echo(f"Discovered {len(discovered)} new models:")
        for m in discovered:
            typer.echo(f"  - {m.name} ({m.protocol})")

    asyncio.run(run())
```

- [ ] **Step 3: Commit**

```bash
git add openllm/cli/main.py
git commit -m "feat: add CLI discover command"
```

---

### Task 8: Add tests for discover functionality

**Files:**
- Create: `openllm/tests/test_discover.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openllm.src.adapter_model import ModelConfig, AdapterConfig
from openllm.src.models import ModelInfo
from openllm.src.registry import ModelRegistry


@pytest.fixture
def registry():
    return ModelRegistry()


@pytest.fixture
def sample_config():
    return ModelConfig(
        name="test-model",
        protocol="openai",
        endpoint="https://api.test.com/v1",
        api_key="test-key",
        enabled=True,
    )


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.list_available_models = AsyncMock(return_value=[
        ModelInfo(id="gpt-4", created=1234567890, owned_by="openai"),
        ModelInfo(id="gpt-3.5-turbo", created=1234567890, owned_by="openai"),
    ])
    return adapter


@pytest.mark.asyncio
async def test_discover_models(registry, sample_config, mock_adapter):
    registry._models = {sample_config.name: sample_config}
    registry._adapters = {sample_config.name: mock_adapter}

    with patch("openllm.src.registry.get_registry", return_value=registry):
        discovered = await registry.discover_models("/tmp/test_models.yaml")

    assert len(discovered) == 2
    assert "gpt-4" in [m.name for m in discovered]
    assert "gpt-3.5-turbo" in [m.name for m in discovered]


@pytest.mark.asyncio
async def test_discover_skips_existing_models(registry, sample_config):
    existing_model = ModelConfig(
        name="gpt-4",
        protocol="openai",
        endpoint="https://api.test.com/v1",
        api_key="test-key",
        enabled=True,
    )
    registry._models = {
        sample_config.name: sample_config,
        existing_model.name: existing_model,
    }

    mock_adapter = MagicMock()
    mock_adapter.list_available_models = AsyncMock(return_value=[
        ModelInfo(id="gpt-4", created=1234567890, owned_by="openai"),
    ])
    registry._adapters = {sample_config.name: mock_adapter}

    discovered = await registry.discover_models("/tmp/test_models.yaml")

    assert len(discovered) == 0


def test_list_available_models_base():
    from openllm.src.adapters.base import ProtocolAdapter
    from openllm.src.adapter_model import AdapterConfig

    class TestAdapter(ProtocolAdapter):
        protocol = "test"

        async def chat_completions(self, messages, **kwargs):
            pass

        async def embeddings(self, texts, **kwargs):
            pass

        async def get_model_info(self):
            return ModelInfo(id="test-model", created=1234567890, owned_by="test")

    config = AdapterConfig(model="test", protocol="test", endpoint="http://test.com")
    adapter = TestAdapter(config)

    models = adapter.list_available_models()

    assert len(models) == 1
    assert models[0].id == "test-model"
```

- [ ] **Step 2: Run tests**

```bash
.venv/bin/pytest openllm/tests/test_discover.py -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add openllm/tests/test_discover.py
git commit -m "test: add tests for discover functionality"
```

---

### Task 9: Integration test

**Files:**
- Modify: Run existing test suite

- [ ] **Step 1: Run all tests**

```bash
.venv/bin/pytest openllm/tests/ -v --tb=short
```

Expected: All tests pass including new discover tests

- [ ] **Step 2: Commit**

```bash
git commit -m "test: run full test suite for discover feature"
```

---

## Plan Complete Checklist

- [x] Task 1: Add list_available_models to base adapter
- [x] Task 2: Implement list_available_models for Ollama
- [x] Task 3: Implement list_available_models for OpenAI
- [x] Task 4: Implement list_available_models for Anthropic
- [x] Task 5: Implement list_available_models for REST
- [x] Task 6: Add discover_models to ModelRegistry
- [x] Task 7: Add CLI discover command
- [x] Task 8: Add tests for discover functionality
- [x] Task 9: Integration test