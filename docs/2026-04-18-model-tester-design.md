# Model Auto-Test Design

## Summary

Add capability to automatically test configured models and update their configuration with discovered capabilities.

## Motivation

Currently, models discovered via `discover` command may not be actually available or may have different capabilities. We need a way to automatically test models and update their configuration.

## Design

### Approach: Timer-based testing (Option C)

1. **Timer-based** - Run tests on a schedule (e.g., every hour)
2. **Manual trigger** - Via CLI command `openllm test`
3. **Auto-save** - Test results update `models.yaml`

### Components

#### 1. ModelTestResult dataclass (`src/tester.py`)

```python
@dataclass
class ModelTestResult:
    model_name: str
    available: bool
    response_time_ms: float
    rpm_limit: int
    tpm_limit: int
    max_context_length: int
    model_size: str
    capabilities: list[str]
    languages: list[str]
    error: str = None
```

#### 2. ModelTester class (`src/tester.py`)

Test prompts for capability detection:

```python
CAPABILITY_PROMPTS = {
    "coding": "Write a Python function that returns the first 10 fibonacci numbers. Just output the code.",
    "math": "Calculate 123 * 456. Show your reasoning step by step.",
    "reasoning": "If all roses are flowers and some flowers fade quickly, what can we conclude about roses?",
    "json": 'Output a valid JSON object with exactly {"name": "test", "age": 25}',
    "vision": "[Image test - if supported]",
    "tool_use": "Use the browser to search for weather in Tokyo",
}
```

Test logic:
1. Send test prompt to model
2. Analyze response to determine capability
3. Measure response time
4. Extract rate limits from response headers
5. Update model configuration

#### 3. Server integration (`server.py`)

```python
async def start_model_tester():
    tester = ModelTester(registry)
    while True:
        await tester.test_all_models()
        await asyncio.sleep(3600)  # 1 hour
```

#### 4. CLI command (`cli/main.py`)

```bash
openllm test
```

Output:
```
Testing models...
  ✅ groq/llama-3.3-70b-versatile: available (120ms), rpm: 30, tpm: 6000, context: 131072, size: 70B, capabilities: [coding, math, reasoning]
  ❌ mistral/mistral-large-latest: unavailable

Results saved to config/models.yaml
```

### Update Flow

```
1. Server starts
2. ModelTester runs on schedule
3. For each model in registry:
   a. Send test prompts
   b. Analyze capabilities
   c. Measure response time
   d. Extract rate limits
4. Update ModelConfig
5. Save to models.yaml
```

### Detected Fields

| Field | Source | Notes |
|-------|--------|-------|
| available | Test request | True/False |
| response_time_ms | Timing measurement | Average of 3 requests |
| rpm_limit | Response header | X-RateLimit-Limit |
| tpm_limit | Response header | X-RateLimit-Limit |
| max_context_length | Test or default | From model info |
| model_size | Model name parsing | e.g., "70B" from name |
| capabilities | Response analysis | Coding, Math, Reasoning, etc. |
| languages | Test prompt | Detect from response |

## Testing

1. Unit test for each capability detector
2. Integration test for full test flow
3. CLI test for `test` command

## Future considerations

- Add success/failure rate tracking
- Add latency trend analysis
- Add cost estimation