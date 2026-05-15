# JavaScript / Node.js Rules
*Apply when: user types `@js` OR current file has `.js`/`.mjs`/`.cjs` extension AND no override.*

## Style & Conventions
- Use 2 spaces for indentation. No tabs.
- Semicolons: either always or never (follow existing project).
- Use `const` for immutable bindings, `let` for mutable. Never `var`.
- Use `===` and `!==`, not `==` or `!=` (except for null/undefined check: `x == null`).
- Variable/function names: `camelCase`. Classes/constructors: `PascalCase`. Constants: `UPPER_SNAKE`.

## Modern JS (ES2020+)
- Use `async/await` over raw promises where possible.
- Use `try/catch` with `await` – don't forget to handle errors.
- Use template literals (` ` `) instead of string concatenation.
- Prefer arrow functions for callbacks (but not for methods that need `this`).
- Use spread/rest (`...`) for array/object copying and function arguments.

## Node.js Specific
- Use `fs.promises` API instead of callback-based `fs` functions.
- For environment variables, use `process.env` with fallback values. Never hardcode secrets.
- Use `path.join()` or `path.resolve()` for cross‑platform paths.
- Handle `unhandledRejection` and `uncaughtException` at the top level.

## Error Handling
- Never swallow errors in catch blocks – at least log them.
- In Express/Koa, always call `next(err)` in async routes, or use a wrapper to catch.
- For promises, always add `.catch()` if you don't use `await`.

## Testing (Jest or Vitest)
- Name test files `*.test.js` or `*.spec.js`.
- Use `describe/it` blocks, not bare tests.
- Use `expect` assertions.
- Mock external modules with `jest.mock()` or `vi.mock()`.

## Common Pitfalls to Avoid
- Off‑by‑one with `array.length` in loops (use `for...of` when possible).
- Mutation of function parameters (don't mutate input objects unless expected).
- Using `parseInt` without radix: `parseInt('08', 10)`.
- Blocking the event loop with synchronous heavy computations – use worker threads or split into async chunks.
- Memory leaks from event listeners (remove with `removeEventListener`).

## Browser (if applicable)
- Prefer `addEventListener` over `onclick` attributes.
- Cache DOM queries (`const el = document.getElementById(...)`) rather than re‑querying.
- Use `requestAnimationFrame` for animations, not `setInterval`.

## Activating this rule set
- User types `@js` → apply all rules above.
- If a `.js`/`.mjs`/`.cjs` file is in context and no language override, auto‑apply.
- To deactivate and go back to core rules, user types `@default`.