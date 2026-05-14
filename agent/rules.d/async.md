# Async & Concurrency Rules
*Apply when: `async def` / `await` detected in code.*

- Preserve async/sync architecture. Never introduce blocking calls (`time.sleep`, `requests.get`) into async paths. Use `asyncio.sleep`, `aiohttp`.
- Never call async functions from sync code without `asyncio.run()` unless already inside event loop.
- If you cannot determine whether code runs in async context, ask: "Does this function run inside an event loop? [y/N]"
- When editing async code, never remove existing `await` unless you are certain the function is no longer a coroutine. If uncertain, keep `await`.
- When adding shared state across coroutines, document locking mechanism (`asyncio.Lock` or `threading.Lock`).
- Do not mix `asyncio` and `threading` without explicit justification.
- Never use `asyncio.create_task()` without storing the task reference — it may be garbage collected silently.
- For yielding control in long-running coroutines, use `await asyncio.sleep(0)`.
- Do not change `async def` to `def` or vice versa without explicit user request.