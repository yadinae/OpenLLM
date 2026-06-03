# Changelog

## v0.1.0 (2026-06-03)

- Initial release
- Protocol translation: Anthropic Messages API ↔ OpenAI Chat Completions
- Combo routing: Fallback / Round-Robin / Priority
- Circuit Breaker: CLOSED→OPEN→HALF_OPEN state machine with LRU eviction
- Exponential backoff retry with httpx error recognition
- RTK tool output compression (git diff / grep / tree / log / JSON)
- 4 context management strategies (Static / Dynamic / Reservoir / Adaptive)
- Input validation: message count, content length, role whitelist
- Optional Bearer Token authentication
- Provider health check background task
- CLI: serve / list-providers / doctor / bind
- 139 tests, ruff zero errors
