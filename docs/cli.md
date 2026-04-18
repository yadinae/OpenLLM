# CLI Reference

## Commands

### serve

Start the OpenLLM server.

```bash
openllm serve [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host` | string | "0.0.0.0" | Server host |
| `--port` | int | 8000 | Server port |
| `--reload` | bool | false | Enable auto-reload |
| `--config` | string | - | Config file path |

**Example:**

```bash
# Default
openllm serve

# Custom port
openllm serve --port 9000

# With config
openllm serve --config /path/to/models.yaml

# Development mode
openllm serve --reload
```

---

### status

Show OpenLLM status.

```bash
openllm status
```

**Example Output:**

```
OpenLLM Status
  Total models: 7
  Enabled: 5

Top models:
  groq/llama-3.3-70b-versatile: 0.850
  mistral/mistral-large-latest: 0.820
```

---

### models

List available models.

```bash
openllm models [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--list` | bool | List models (default) |

**Example:**

```bash
openllm models
```

**Example Output:**

```
Available models:
  [✓] groq/llama-3.3-70b-versatile (openai)
  [✓] mistral/mistral-large-latest (openai)
  [✓] gemini/gemini-2.5-flash (openai)
  [✓] cerebras/qwen-3-235b-a22b (openai)
  [✗] ollama/llama3 (ollama)
```

---

### score

Show model scores.

```bash
openllm score [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--refresh` | bool | Refresh scores |

**Example:**

```bash
openllm score
```

**Example Output:**

```
Model scores:
  groq/llama-3.3-70b-versatile: total=0.850 quality=0.800 speed=0.900
  mistral/mistral-large-latest: total=0.820 quality=0.810 speed=0.850
  gemini/gemini-2.5-flash: total=0.780 quality=0.750 speed=0.850
```

---

### config

Show configuration.

```bash
openllm config [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--show` | bool | Show config (default) |

**Example:**

```bash
openllm config
```

**Example Output:**

```
Current configuration:

Model: groq/llama-3.3-70b-versatile
  Protocol: openai
  Endpoint: https://api.groq.com/openai/v1
  RPM: 30
  TPM: 6000

Model: mistral/mistral-large-latest
  Protocol: openai
  Endpoint: https://api.mistral.ai/v1
  RPM: 30
  TPM: 15000
```

---

### discover

Discover available models from configured providers.

```bash
openllm discover
```

**Description:**

This command queries all configured model providers to discover what models are available. Discovered models are automatically added to `models.yaml` with `enabled: false`, allowing you to review and enable them manually.

**Example:**

```bash
openllm discover
```

**Example Output:**

```
Discovered 3 new models:
  - gpt-4-turbo (openai)
  - gpt-3.5-turbo (openai)
  - llama3:8b (ollama)

Models saved to /path/to/models.yaml (enabled: false)
```

**Supported Providers:**

| Provider | Endpoint | Notes |
|----------|----------|--------|
| OpenAI-compatible | `/v1/models` | Lists all account models |
| Ollama | `/api/tags` | Lists local models |
| Anthropic | N/A | Returns current model only (API limited) |
| REST | `/models` | Custom endpoint |

---

### test

Test configured models for availability and capabilities.

```bash
openllm test [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--all` | bool | Test all models including disabled |

**Example:**

```bash
openllm test
```

**Example Output:**

```
Testing enabled models...
  ✅ groq/llama-3.3-70b-versatile (70b): available (120ms), context: 131072, capabilities: [coding, math]
  ❌ mistral/mistral-large-latest: unavailable

Results: 1/2 models available
```

---

### freeride

FreeRide mode for token freedom - automatically discover and connect to free LLM APIs.

```bash
openllm freeride [OPTIONS]
```

**Options:**

| Option | Type | Description |
|--------|------|-------------|
| `--enable` | bool | Enable FreeRide mode |
| `--disable` | bool | Disable FreeRide mode |
| `--status` | bool | Show FreeRide status |
| `--providers` | string | Comma-separated providers |

**Example:**

```bash
# Enable with all providers
openllm freeride --enable

# Enable specific providers
openllm freeride --enable --providers groq,cerebras

# Show status
openllm freeride --status
```

**Supported Providers:**

- Groq (llama-3.3-70b-versatile, qwen3-32b)
- Cerebras (llama3.1-8b, qwen-3-235b-a22b)
- OpenRouter (deepseek-r1:free, llama-3.3-70b:free)
- Mistral (mistral-small, codestral)
- Gemini (gemini-2.5-flash)
- Ollama (llama3, mistral)

---

## Python API

### Run Server

```python
from openllm.src.server import run

# Default
run()

# Custom
run(host="127.0.0.1", port=9000, reload=False)
```

### Programmatic Usage

```python
from openllm.src.registry import get_registry
from openllm.src.dispatcher import get_dispatcher
from openllm.src.models import ChatRequest, Message

# Get dispatcher
dispatcher = get_dispatcher()

# Create request
request = ChatRequest(
    model="meta-model",
    messages=[Message(role="user", content="Hello!")]
)

# Execute
response = await dispatcher.dispatch(request)

print(response.choices[0].message.content)
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENLLM_HOST` | Server host |
| `OPENLLM_PORT` | Server port |
| `OPENLLM_CONFIG` | Config file path |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GROQ_API_KEY` | Groq API key |
| `MISTRAL_API_KEY` | Mistral API key |
| `CEREBRAS_API_KEY` | Cerebras API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |