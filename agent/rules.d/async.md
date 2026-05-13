# Async & Concurrency Rules
*Loaded when: `async def` / `await` detected in code.*

- Preserve async/sync architecture. Never introduce blocking calls (`time.sleep`, `requests.get`) into async paths. Use `asyncio.sleep`, `aiohttp`.
- Never call async functions from sync code without `asyncio.run()` unless already inside event loop. If uncertain, ask.
- When adding shared state across coroutines, document locking mechanism (`asyncio.Lock` or `threading.Lock`).
- Do not mix `asyncio` and `threading` without explicit justification.
