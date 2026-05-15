# AI Coding Rules — Extended
*Load on demand via `/add`. Not loaded at startup.*
*Trigger: agent needs sections 5–10, or user asks for dependency/API/cross-file details.*

---

## 5. Dependency & Package Management
- Missing info → ask. Partial info, low risk → annotate `[assume]` and proceed.
- New library: add to `requirements.txt` via diff, instruct user to run `pip install -r requirements.txt`.
- Never install globally if a virtualenv is active.

---

## 6. Knowledge Mapping (system-map-core.md)
- Auto-update map in same response when changing function signatures, classes, or shared variables.
- Staleness: file in map but not in context → assume unchanged (risk accepted). File in context → verify key exports match map. Mismatch → `[MAP STALE] File X changed. Refresh system-map-core.md.`
- Cross-reference map before naming new entities.
- Do not ask user to `/add` files just for staleness check.

---

## 7. Safety Rules (extended)
- Never name files after stdlib modules (`os.py`, `sys.py`...). Use prefixes.
- Never read/edit `.pkl`, `.pyc`, model weights, or binary files.
- Directory traversal: max depth = `MAX_DIR_DEPTH` (see system-map-core.md constants). If task requires deeper scan → stop and ask user to provide file list manually.

---

## 8. Verification — Extended Failure Budget
Standard failure budget is in `rules-core.md` Section 5. Extended cases:

- Tool missing (pytest, ruff not installed) → one-line warning, ask user to run manually. Do not block.
- Test file does not exist → suggest creating a minimal test before verifying. Ask: "No test file found. Create a basic test first? [y/n]"
- Verification command times out or hangs → `[TIMEOUT] Verification did not complete. Check for infinite loops or missing test teardown.`

---

## 9. Cross-file Bug Fix
*Overridden by `rules.d/diagnose.md` when `@diagnose` is triggered or error spans multiple files.*

- **Step 1 (Read):** Analyze all files in error trace. Find root cause.
- **Step 1b (Reproduce):** Suggest a command to reproduce the error. Ask user to run and confirm.
- **Step 2 (Scope):**
  ```
  Bug location : <file>, <function>, line ~N
  Root cause   : <one sentence>
  Files affected: <list in fix order>
  ```
- **Step 3 (Surgical Diff):** One diff per file, in dependency order. No unrelated changes.
- **Step 4 (Check):** Verify imports and signatures match across all affected files.
- Fix touches >3 files → STOP, ask confirmation.
- Never fix symptoms in caller if root cause is in callee.
- One bug = one patch set. No bundled fixes.

---

## 10. Specialized Rules — Full Trigger Table
*Condensed version in rules-core.md Section 6. Full descriptions here.*

| Context | Load |
|---------|------|
| Any shell command suggested | `rules.d/sandbox.md` *(preloaded)* |
| `@grill` | `rules.d/grill.md` — drill with questions until "proceed" |
| `@caveman` | `rules.d/caveman.md` — ultra-token mode until `@normal` |
| `@diagnose` or multi-file error | `rules.d/diagnose.md` — overrides section 9 above |
| `async def` / `await` in code | `rules.d/async.md` |
| SQL / ORM / migration | `rules.d/database.md` |
| auth / payment / secrets / encryption | `rules.d/security.md` |
| diff >300 lines or ≥3 files | `rules.d/heavy_feature.md` |
| production / destructive DB ops | `rules.d/dangerous_ops.md` |
| 2+ verbs: fix/refactor/add/update/rename | `rules.d/patch_isolation.md` |
| `.py` file, no language override | `rules.d/python.md` |
| `.js`/`.mjs`/`.cjs` file, no override | `rules.d/javascript.md` |
| `@default` / `/default` | Reset to core rules only |