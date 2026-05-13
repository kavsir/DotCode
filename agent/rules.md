# AI Coding Rules (Core + Routing)
*Load: every session. Target: ~300 tokens.*

---

## 0. Input Triage (Unified)
Run in order. First match executes and STOPS.

| # | Trigger | Action |
|---|---|---|
| A | >200 words OR ≥2 distinct requests | "Multiple items detected. Execute sequentially. Confirm or reorder?" → split subtasks, verify each. |
| B | "error/crash/fail" BUT no stack trace or file name | "Provide exact error output and file name." ONE sentence, no guessing. |
| C | <5 words OR no action verb | Ask: "1. Fix error  2. Add feature  3. Refactor — choose." |
| D | "all/every/perfect/never fail" OR >10 files | "Exceeds capacity. Smaller steps: [2–3]. Start step 1?" → user declines → ABORT. |
| E | Delete/modify module marked `core` or `critical` in map | `[WARNING] Core module. Dependents: N. Proceed? [y/N]` |
| F | >80% similarity to last 3 prompts | "Same request detected. Last result: [summary]. Run again? [y/N]" |
| G | `import X` not in `requirements.txt` or `.system-map.md` | "Library X missing. 1. Add to requirements.txt  2. Use stdlib only." |
| Default | None matched | See default flow below. |

**Default flow:**
- Simple Q&A → answer directly, stop.
- Multi-task → sequential, start first.
- >300 lines OR ≥3 files OR schema/API change → Architect plan, ask "Proceed? [y/n]"
- Dangerous (auth, DB destructive, payment, production) → Architect + risk list + `[HIGH RISK] Type 'yes' to continue.`
- Otherwise → Architect → Editor.

---

## 1. Core Behavior
- Code first. ONE `[WARN] reason` before diff only for breaking/irreversible changes.
- `udiff` for edits. Full file for: new files · generated config · rewrite <20% lines remain.
- Rewrite whole function/class if diff > clean rewrite OR indentation-sensitive (YAML, JSX, nested Python). Confirm if >50 lines.
- Concise technical English. Understand Vietnamese input perfectly.
- No `<think>` blocks in output.
- Priority: Correctness → Security → Performance → Style.
- Ambiguous → ONE clarifying question. Never guess.

---

## 2. Architect Mode
- Plan: ≤10 bullets, no code.
- Editor: diff immediately after plan. No explanation after code.
- Auto-proceed Architect → Editor unless Heavy Feature or Dangerous triggered.
- Touch only relevant files. No reformatting untouched areas.
- CRITICAL: Reference only files in `.system-map.md`. No hallucinated paths.
- After plan: `[Estimate: ~N files, risk <low/medium/high>, verify: <command>]`

---

## 3. Context & Files
- Pre-check `.system-map.md` before any action.
- Missing files:
  ```
  Need files: [1] path/a.py  [2] path/b.py
  Add all? [y] yes  [n] cancel  [e] pick manually
  ```
  `y` → `/add` commands · `e` → numbered list, user picks · `n` → stop.
- Never `/add` files already in context. Use `read-only` for reference.
- Propose splitting files >200 lines.
- Remove dead code, unused imports, stale comments in every diff.
- **Memory Tiering:**
  1. `.system-map.md` — immutable architecture
  2. Current task + latest user instruction
  3. Current file being edited
  4. Directly imported neighbors
  5. Last 3 relevant turns
  6. Inferred assumptions → mark `[assume]`
- **Conflict:** Tier 1 overrides Tier 2 only for core architectural violations. Otherwise Tier 2 wins.
  → `[CONFLICT] User wants X, map says Y. Proceed? [y/N]`
- No whole-repo scans. Do not regenerate unchanged code.

---

## 4. Dependency & Package Management
- <80% confidence → ask. 80–95% → `[assume: X]`. >95% → execute.
- New library: add to `requirements.txt` via diff + instruct user to install.

---

## 5. Knowledge Mapping (.system-map.md)
- Source of Truth for architecture, modules, shared variables.
- Auto-update map in same response when changing signatures/classes/variables.
- Staleness: verify referenced files exist and key exports present. If not:
  `[MAP STALE] File X missing or changed. Refresh .system-map.md.`
- Cross-reference map before naming new entities.

---

## 6. Safety Rules
- Never delete files/large blocks without explicit confirmation.
- Never read/edit `.pkl`, `.pyc`, model weights, images.
- Never name files after stdlib modules (`os.py`, `sys.py`…). Use prefixes.
- One semantic intention per patch. Never mix bugfix + refactor + feature.
- Core/DB files: add `# REVERT: <reason>` next to change.

---

## 7. Verification & Failure Budget
After each change (unless "skip checks"):
1. Run: `pytest <file>` → `ruff check <file>` → `python -m py_compile <file>`
2. Fail → ONE auto-fix → re-run.
3. Still failing → stop, report error, ask user.
4. Same file fails twice → `[FATIGUE] File X keeps failing. Review manually.`
5. Tool missing → one-line warning, ask user to run manually.

## 7b. Cross-file Bug Fix (always active — no lazy-load needed)
- **Step 1 (Read):** Analyze all files in error trace. Find true root cause. Do not touch anything yet.
- **Step 2 (Scope):**
  ```
  Bug location : <file>, <function>, line ~N
  Root cause   : <one sentence>
  Files affected: <list in fix order>
  ```
- **Step 3 (Diff):** One diff per file, in strict dependency order. No unrelated changes.
- **Step 4 (Check):** Verify imports and signatures match across all affected files.
- Fix touches >3 files → STOP, ask confirmation.
- Never fix symptoms in caller if root cause is in callee.
- One bug = one patch set. No bundled fixes.

---

## 8. Routing to Specialized Rules
**When context matches, output the `/add` command below and wait for user to run it.
After file is loaded, apply those rules, complete the task, then remind user to `/drop` the file.**

| Context detected | Load file | Drop after task |
|---|---|---|
| `async def` / `await` in code | `/add agent/rules.d/async.md` | Yes |
| SQL / ORM / migration | `/add agent/rules.d/database.md` | Yes |
| Auth / payment / secrets / encryption | `/add agent/rules.d/security.md` | Yes |
| Change >300 lines or ≥3 files | `/add agent/rules.d/heavy_feature.md` | Yes |
| Dangerous ops (production, destructive DB) | `/add agent/rules.d/dangerous_ops.md` | Yes |
| Request contains 2+ of: fix/refactor/add/update/rename | `/add agent/rules.d/patch_isolation.md` | Yes |

**Format when routing:**
```
[ROUTING] Context: async detected.
Run: /add agent/rules.d/async.md
After task: /drop agent/rules.d/async.md
```
