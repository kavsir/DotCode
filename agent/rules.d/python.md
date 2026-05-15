# Python-Specific Rules
*Apply when: user types `@python` OR current file has `.py` extension AND no explicit override.*

## Style & Conventions (PEP 8)
- Use 4 spaces for indentation. No tabs.
- Maximum line length: 88 (Black default) or 79 if project follows strict PEP8.
- Use `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- Imports order: standard library → third-party → local modules. Group with blank lines.

## Type Hints (modern Python)
- Add type hints to all function arguments and return types (unless legacy codebase).
- Use `from typing import ...` for Python <3.9; use built‑in types (`list`, `dict`) for 3.9+.
- Prefer `Optional[X]` or `X | None` over `Union[X, None]`.
- Avoid circular imports – use `if TYPE_CHECKING` when needed.

## Code Patterns
- Use `with` for file/network/resource management. Never manually call `.close()`.
- Do not use mutable default arguments (`def f(arg=[])`). Use `None` and assign inside.
- Prefer `pathlib.Path` over `os.path` for file paths.
- Use `f-strings` for formatting, not `%` or `.format()` (unless logging with lazy evaluation).

## Error Handling
- Catch specific exceptions, never bare `except:`.
- Re-raise with context: `raise NewError("msg") from original_exc`.
- Use `try/except/else` (else runs if no exception) for clarity.

## Async (if applicable)
- For async functions, add `await` before all I/O calls (network, file, DB).
- Do not mix `asyncio` and `threading` without justification.
- Use `asyncio.create_task()` with stored reference to avoid garbage collection.

## Testing (pytest)
- Name test files `test_*.py` or `*_test.py`.
- Test function names `test_<behavior>`.
- Use `assert` statements, not `self.assertEqual` (pytest style).
- For fixtures, use `conftest.py` for session/module scope.

## Common Pitfalls to Avoid
- Modifying a list while iterating over it → iterate over a copy (`list[:]`).
- Using `datetime.now()` without timezone → use `datetime.now(timezone.utc)` for UTC.
- Assuming dictionary iteration order (Python <3.7) – not an issue in 3.7+, but don't rely on it.
- Using `json.loads` on untrusted input – no fix, but be aware of DoS via large payloads.

## Activating this rule set
- User types `@python` → apply all rules above.
- If a `.py` file is in context and no `@js` or other language override, auto‑apply.
- To deactivate and go back to core rules, user types `@default`.