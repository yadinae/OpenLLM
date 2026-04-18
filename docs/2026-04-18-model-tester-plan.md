# Model Auto-Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic model testing capability to detect availability, response time, rate limits, context length, model size, and capabilities.

**Architecture:** Create a ModelTester class that sends test prompts to each model, analyzes responses, measures timing, extracts rate limits from headers, and updates models.yaml with results.

**Tech Stack:** Python, httpx, asyncio, PyYAML

---

### Task 1: Create ModelTestResult dataclass

**Files:**
- Create: `src/tester.py`

- [ ] **Step 1: Write the dataclass**

```python
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ModelTestResult:
    model_name: str
    available: bool
    response_time_ms: float
    rpm_limit: int = 0
    tpm_limit: int = 0
    max_context_length: int = 0
    model_size: str = ""
    capabilities: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    error: Optional[str] = None
    tested_at: datetime = None

    def __post_init__(self):
        if self.tested_at is None:
            self.tested_at = datetime.now()
```

- [ ] **Step 2: Commit**

```bash
git add src/tester.py
git commit -m "feat: add ModelTestResult dataclass"
```

---

### Task 2: Create ModelTester class with capability检测

**Files:**
- Modify: `src/tester.py`

- [ ] **Step 1: Add imports and constants**

```python
import re
import time
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.adapter_model import ModelConfig
from src.adapters.base import create_adapter
from src.models import ChatRequest, Message

logger = logging.getLogger(__name__)


CAPABILITY_TESTS = {
    "coding": (
        "Write a Python function that returns the first 10 fibonacci numbers. Just output the code.",
        lambda r: "def fibonacci" in r or "fibonacci" in r.lower()
    ),
    "math": (
        "Calculate 123 * 456. Show your reasoning step by step.",
        lambda r: "59268" in r or "5*456" in r.lower()
    ),
    "reasoning": (
        "If all roses are flowers and some flowers fade quickly, what can we conclude about roses?",
        lambda r: len(r) > 50  # Requires reasoning, longer response
    ),
    "json": (
        'Output a valid JSON object with exactly {"name": "test", "age": 25}',
        lambda r: "{" in r or '"name"' in r
    ),
}
```

- [ ] **Step 2: Add ModelTester class**

```python
class ModelTester:
    def __init__(self, registry):
        self.registry = registry

    async def test_model(self, config: ModelConfig) -> ModelTestResult:
        """Test a single model."""
        try:
            adapter = create_adapter(
                config.protocol,
                type('AdapterConfig', (), {
                    'model': config.name,
                    'protocol': config.protocol,
                    'endpoint': config.endpoint,
                    'api_key': config.api_key,
                })()
            )

            start = time.time()
            messages = [{"role": "user", "content": "Hello, respond with just 'OK'"}]
            response = await adapter.chat_completions(messages)
            response_time = (time.time() - start) * 1000

            content = response.choices[0].message.content
            available = "OK" in content

            capabilities = self._detect_capabilities(config, adapter)
            model_size = self._extract_model_size(config.name)

            return ModelTestResult(
                model_name=config.name,
                available=available,
                response_time_ms=response_time,
                max_context_length=config.max_context_length,
                model_size=model_size,
                capabilities=capabilities,
            )
        except Exception as e:
            logger.error(f"Test failed for {config.name}: {e}")
            return ModelTestResult(
                model_name=config.name,
                available=False,
                response_time_ms=0,
                error=str(e)
            )

    def _detect_capabilities(self, config, adapter) -> list[str]:
        capabilities = []
        for cap, (prompt, check_fn) in CAPABILITY_TESTS.items():
            try:
                messages = [{"role": "user", "content": prompt}]
                response = asyncio.run(adapter.chat_completions(messages))
                content = response.choices[0].message.content
                if check_fn(content):
                    capabilities.append(cap)
            except Exception:
                pass
        return capabilities

    def _extract_model_size(self, model_name: str) -> str:
        match = re.search(r'(\d+[bB])', model_name)
        return match.group(1) if match else "unknown"

    async def test_all_models(self) -> list[ModelTestResult]:
        results = []
        for config in self.registry.list_models():
            result = await self.test_model(config)
            results.append(result)
        return results
```

- [ ] **Step 3: Commit**

```bash
git add src/tester.py
git commit -m "feat: add ModelTester class with capability detection"
```

---

### Task 3: Add CLI test command

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: Add test command**

```python
@cli.command("test")
def test_cmd():
    """Test all configured models"""
    import asyncio
    from pathlib import Path
    from src.tester import ModelTester
    from src.registry import get_registry

    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

    async def run():
        registry = get_registry()
        registry.load_from_yaml(config_path)
        tester = ModelTester(registry)

        typer.echo("Testing models...")
        results = await tester.test_all_models()

        for r in results:
            if r.available:
                caps = ", ".join(r.capabilities) if r.capabilities else "none"
                typer.echo(
                    f"  ✅ {r.model_name}: "
                    f"available ({r.response_time_ms:.0f}ms), "
                    f"capabilities: [{caps}]"
                )
            else:
                typer.echo(f"  ❌ {r.model_name}: unavailable")

        typer.echo(f"\nTested {len(results)} models")

    asyncio.run(run())
```

- [ ] **Step 2: Test command**

```bash
.venv/bin/openllm test
```

- [ ] **Step 3: Commit**

```bash
git add cli/main.py
git commit -m "feat: add CLI test command"
```

---

### Task 4: Add auto-test to server startup

**Files:**
- Modify: `src/server.py`

- [ ] **Step 1: Add timer task**

Add to server startup:

```python
async def start_model_tester(registry, config_path, interval_seconds=3600):
    """Background task to test models periodically."""
    from src.tester import ModelTester
    
    tester = ModelTester(registry)
    
    while True:
        try:
            results = await tester.test_all_models()
            tester.update_config(results, config_path)
            logger.info(f"Model test completed: {len(results)} models tested")
        except Exception as e:
            logger.error(f"Model test failed: {e}")
        
        await asyncio.sleep(interval_seconds)
```

- [ ] **Step 2: Add update_config method to ModelTester**

```python
def update_config(self, results: list[ModelTestResult], config_path: Path):
    """Update models.yaml with test results."""
    import yaml
    
    with open(config_path) as f:
        data = yaml.safe_load(f)
    
    for result in results:
        for model in data.get("models", []):
            if model.get("name") == result.model_name:
                model["rpm"] = result.rpm_limit or model.get("rpm", 30)
                model["tpm"] = result.tpm_limit or model.get("tpm", 15000)
                model["max_context_length"] = result.max_context_length or model.get("max_context_length", 128000)
                model["capabilities"] = result.capabilities
    
    with open(config_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Updated {len(results)} models in {config_path}")
```

- [ ] **Step 3: Commit**

```bash
git add src/server.py
git commit -m "feat: add auto-test timer to server"
```

---

### Task 5: Add tests

**Files:**
- Create: `tests/test_tester.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.tester import ModelTester, ModelTestResult, CAPABILITY_TESTS


def test_extract_model_size():
    tester = ModelTester(None)
    
    assert tester._extract_model_size("groq/llama-3.3-70b-versatile") == "70b"
    assert tester._extract_model_size("mistral/mistral-large-latest") == "unknown"
    assert tester._extract_model_size("qwen-3-32b") == "32b"


def test_capability_tests_exist():
    expected = ["coding", "math", "reasoning", "json"]
    assert list(CAPABILITY_TESTS.keys()) == expected


@pytest.mark.asyncio
async def test_model_tester_init():
    registry = MagicMock()
    tester = ModelTester(registry)
    
    assert tester.registry is registry


def test_model_test_result_defaults():
    result = ModelTestResult(
        model_name="test-model",
        available=True,
        response_time_ms=100
    )
    
    assert result.model_name == "test-model"
    assert result.available is True
    assert result.response_time_ms == 100
    assert result.capabilities == []
    assert result.languages == []
```

- [ ] **Step 2: Run tests**

```bash
.venv/bin/pytest tests/test_tester.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_tester.py
git commit -m "test: add ModelTester tests"
```

---

### Task 6: Integration test

**Files:**
- Modify: Run full test suite

- [ ] **Step 1: Run all tests**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: All tests pass

- [ ] **Step 2: Commit**

```bash
git commit -m "test: run full test suite"
```

---

## Plan Complete Checklist

- [x] Task 1: Create ModelTestResult dataclass
- [x] Task 2: Create ModelTester class with capability detection
- [x] Task 3: Add CLI test command
- [x] Task 4: Add auto-test to server startup
- [x] Task 5: Add tests
- [x] Task 6: Integration test