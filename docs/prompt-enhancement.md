# Prompt Enhancement Guide

## Overview

OpenLLM can automatically enhance system prompts before sending requests to models. Two enhancement strategies are available, inspired by [context-mode](https://github.com/mksglu/context-mode):

1. **Code Thinking** — Instructs the LLM to analyze data via code instead of reading everything into context
2. **Terse Mode** — Compresses LLM output by removing filler words and pleasantries

## Code Thinking Mode

### Problem

When asked to analyze large amounts of data, LLMs tend to read everything into context:

> ❌ "Let me read all 50 files to understand the codebase structure..."
> (Consumes 200K+ tokens of context)

### Solution

Code thinking instructs the LLM to write a script instead:

> ✅ "I'll write a Python script to scan the directory and count functions..."
> (Consumes ~5K tokens for the script + ~500 bytes for results)

### Auto-Detection

Code thinking is auto-enabled when the user message contains keywords:

**English:**
- `count`, `scan`, `analyze`, `list all`, `find all`
- `in all files`, `across the codebase`, `throughout`
- `statistics`, `summary of`, `report on`

**Chinese:**
- `统计`, `扫描`, `分析所有`, `列出所有`
- `所有文件中`, `整个代码库`
- `统计信息`, `汇总`

### Manual Override

```json
{
  "code_thinking": true
}
```

### Injected Prompt

When enabled, this is appended to the system prompt:

```
## Code Thinking Mode
When analyzing data, files, or complex information:
1. Write code to analyze instead of reading raw data
2. Execute scripts in the sandbox
3. Return only results and summaries
```

## Terse Mode

### Problem

LLMs tend to be verbose with filler:

> ❌ "Sure! I'd be happy to help you with that. Let me take a look at the file and see what we can do to improve it. Based on my analysis, I think the best approach would be to..."

### Solution

Terse mode compresses output by 65-75%:

> ✅ "File analyzed. Issue: null pointer at line 42. Fix: add null check before access."

### Intensity Levels

| Level | Compression | Behavior |
|-------|-------------|----------|
| `mild` | ~30-40% | Remove obvious filler, keep natural flow |
| `moderate` | ~50-65% | Short sentences, minimal pleasantries |
| `extreme` | ~65-75% | Telegraphic style, fragments OK |

### Configuration

Per-agent defaults:
```json
{
  "terse_enabled": true,
  "terse_intensity": "moderate"
}
```

Per-request override:
```json
{
  "terse": true,
  "terse_intensity": "extreme"
}
```

### Safety

Terse mode auto-expands for:
- Security warnings
- Irreversible actions (delete, drop, rm -rf)
- User confusion detected in conversation

## Combined Effect

When both are enabled:

1. **Input side**: Code thinking reduces input tokens by 50-90% (scripts vs raw data)
2. **Output side**: Terse mode reduces output tokens by 50-75%
3. **Combined**: Up to 90% total token savings on analysis tasks

## API Integration

All enhancement is handled by `PromptEnhancer` in the request pipeline:

```
Request → Agent Config → PromptEnhancer → Model
                                   ↑
                    ┌───────────────┤
                    │ Code thinking (auto-detect or force)
                    │ Terse mode (per-agent or per-request)
                    └───────────────┤
                          Session event recall
```

## Testing Enhancement

```bash
POST /api/session/enhance/test
{
  "messages": [{"role": "user", "content": "统计所有 Python 文件的函数数量"}],
  "code_thinking": true,
  "terse": true,
  "terse_intensity": "moderate"
}
```

Returns the enhanced messages with injected instructions visible.
