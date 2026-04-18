# Auto Discover Models Design

## Summary

Add capability to automatically discover available models from configured providers and register them in the model registry.

## Motivation

Currently, models must be manually configured in `models.yaml`. Users want OpenLLM to automatically discover what models are available from each provider and register them.

## Design

### Approach: Hybrid (Option C)

1. **Startup discovery** - When server starts, scan all configured adapters
2. **CLI command** - Manual trigger via `openllm discover`
3. **Auto-save** - Save discovered models to `models.yaml` with `enabled: false`

### Components

#### 1. ProtocolAdapter base class

Add new method to `base.py`:

```python
async def list_available_models(self) -> list[ModelInfo]:
    """List all available models from provider."""
    # Default: return just the current model
    return [await self.get_model_info()]
```

#### 2. Adapter implementations

**Ollama** (`ollama.py`):
- Endpoint: `GET /api/tags`
- Parse: `models[].name`
- Return as `list[ModelInfo]`

**OpenAI** (`openai.py`):
- Endpoint: `GET /v1/models`
- Parse: `data[].id`
- Return as `list[ModelInfo]`

**Anthropic** (`anthropic.py`):
- Endpoint: N/A (limited API access)
- Return current model only (same as base)

**REST** (`rest.py`):
- Configurable via adapter config
- Parse JSON `models` array

#### 3. ModelRegistry (`registry.py`)

Add new method:

```python
async def discover_models(self, config_path: str) -> list[ModelConfig]:
    """Discover models from all configured providers."""
    discovered = []
    for model in self._models.values():
        adapter = self.get_or_create_adapter(model.name)
        if adapter:
            try:
                model_infos = await adapter.list_available_models()
                for mi in model_infos:
                    # Create ModelConfig with enabled: False
                    config = ModelConfig(
                        name=mi.id,
                        protocol=model.protocol,
                        endpoint=model.endpoint,
                        enabled=False,  # User must enable manually
                        capabilities=model.capabilities,
                        model_type=model.model_type,
                        model_scale=model.model_scale,
                    )
                    if config.name not in self._models:
                        self._models[config.name] = config
                        discovered.append(config)
            except Exception as e:
                logger.warning(f"Failed to discover from {model.name}: {e}")
    # Save to YAML
    self._save_to_yaml(config_path, discovered)
    return discovered
```

Add private helper:

```python
def _save_to_yaml(self, config_path: str, models: list[ModelConfig]):
    """Save models to YAML config."""
    # Load existing
    # Merge new models
    # Write back
```

#### 4. CLI command (`cli/main.py`)

```python
@cli.command("discover")
def discover_cmd():
    """Discover available models from providers"""
    # Call registry.discover_models()
    # Print results
```

#### 5. Server integration (`server.py`)

On startup after loading YAML, optionally trigger discovery:

```python
# After registry.load_from_yaml()
if config.get("auto_discover", False):
    await registry.discover_models(config_path)
```

### Data Flow

```
1. CLI/server starts
2. Registry loads from models.yaml
3. Registry.discover_models() called
4. For each configured model:
   a. Create/get adapter
   b. Call adapter.list_available_models()
   c. Parse response to list[ModelInfo]
   d. Create ModelConfig (enabled: False)
   e. Add to registry if not exists
5. Save to models.yaml
```

### ModelConfig fields

Make sure `ModelConfig` has:
- `name`: str
- `protocol`: str
- `endpoint`: str
- `enabled`: bool
- `api_key`: str (optional)
- `capabilities`: list[str] (optional)
- `model_type`: str (optional)
- `model_scale`: str (optional)

## Testing

1. Unit test each adapter's `list_available_models()`
2. Integration test full discovery flow
3. CLI test for `discover` command

## Future considerations

- Add "refresh" flag to update existing models
- Selective discovery per protocol
- Cache discovery results