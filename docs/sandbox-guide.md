# Sandbox Guide

## Overview

The sandbox provides isolated multi-language code execution, inspired by [context-mode](https://github.com/mksglu/context-mode)'s `ctx_execute` and `ctx_batch_execute`. It keeps raw data out of the context window — the LLM writes a script, the sandbox runs it, and only results come back.

## Architecture

```
Client Request
    │
    ▼
Sandbox Executor
    ├── Creates isolated temp directory
    ├── Writes script file
    ├── Executes with timeout & output limit
    └── Cleans up temp dir
    │
    ▼
Result: stdout, stderr, exit_code, duration
```

## API Endpoints

### Execute Single Code

```bash
POST /api/sandbox/execute
{
  "language": "python",
  "code": "print('hello')",
  "timeout": 30
}
```

Response:
```json
{
  "success": true,
  "stdout": "hello\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 42,
  "raw_bytes": 6,
  "truncated": false
}
```

### Batch Execution

```bash
POST /api/sandbox/batch
{
  "commands": [
    {"language": "python", "code": "import os; print(len(os.listdir('.')))", "label": "count files"},
    {"language": "shell", "code": "uname -a", "label": "system info"}
  ],
  "track_file_reads": true
}
```

Response:
```json
{
  "commands_executed": 2,
  "commands_succeeded": 2,
  "commands_failed": 0,
  "total_duration_ms": 85,
  "summary": "Batch: 2 commands executed\n  ✅ count files: exit=0, time=42ms\n  ✅ system info: exit=0, time=43ms",
  "files_read": ["./setup.py", "./README.md"],
  "context_bytes": 120
}
```

### Content Indexing

```bash
POST /api/sandbox/index
{
  "source": "docs/api-reference",
  "content": "The /v1/chat/completions endpoint...",
  "label": "API Reference",
  "content_type": "markdown"
}
```

### Search

```bash
GET /api/sandbox/search?q=chat+completions&limit=10
```

## Supported Languages

| Language | Commands Tried | Extension |
|----------|---------------|-----------|
| Python | `python3`, `python` | `.py` |
| JavaScript | `node` | `.js` |
| TypeScript | `npx tsx`, `npx ts-node`, `deno run`, `bun run` | `.ts` |
| Shell | `bash`, `sh` | `.sh` |
| Ruby | `ruby` | `.rb` |
| Perl | `perl` | `.pl` |
| PHP | `php` | `.php` |

## Security

- **Isolated temp directories** — Each execution gets a unique `openllm-sandbox-*` temp dir
- **Output truncation** — Max 50KB output per execution (configurable)
- **Timeout** — Default 30s per execution (configurable)
- **Safe environment** — Only essential env vars passed through
- **Auto-cleanup** — Temp directories removed after execution

## Use Cases

### Code Analysis

Instead of reading 50 files into context:

```python
# Ask the LLM to generate this:
import os, ast
from pathlib import Path

counts = {}
for f in Path('src').rglob('*.py'):
    tree = ast.parse(f.read_text())
    counts[str(f)] = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))

for f, c in sorted(counts.items(), key=lambda x: -x[1]):
    print(f'{f}: {c} functions')
```

The sandbox runs it and returns only the summary.

### Log Analysis

```bash
grep -c "ERROR" /var/log/app.log | xargs -I{} echo "Errors today: {}"
```

### Data Processing

```python
import json
with open('data.json') as f:
    data = json.load(f)
print(f"Records: {len(data)}")
print(f"Categories: {set(r['cat'] for r in data)}")
```

## Configuration

```python
# In src/enums.py DEFAULT_CONFIG
"sandbox": {
    "enabled": True,
    "max_output_bytes": 50000,   # Max output per execution
    "timeout_seconds": 30,       # Max execution time
}
```
