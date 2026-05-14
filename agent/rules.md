# AI Coding Rules
*Load every session. Integrates Karpathy's 4 principles + specialized routing.*

---

## 0. Guiding Principles (Karpathy)
Apply these principles before any code. They override all specific instructions below.

### 0.1 Think Before Coding
- **Don't assume.** If uncertain, ask.
- **If multiple interpretations exist** → list them briefly, don't pick silently.
- **If a simpler approach exists** → propose it. Push back when request overcomplicates.
- **If confused** → stop, state what's unclear, ask.

### 0.2 Simplicity First
- Write minimum code that solves the problem.
- No features beyond the request.
- No abstractions for single-use code.
- If you wrote >50 lines and it could be 20, rewrite.
- Ask: "Would a senior engineer call this overcomplicated?"

### 0.3 Surgical Changes
- When editing existing code: change only the lines required.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor unrelated code.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code → mention it, don't delete it.
- Only remove imports/variables/functions that **your changes** made unused.
- Test: every changed line must trace directly to the user's request.

### 0.4 Goal-Driven Execution
- Before coding, define verifiable success criteria.
  - Bad: "Add validation" → Good: "Write a test for invalid inputs, then make it pass"
  - Bad: "Fix the bug" → Good: "Write a test that reproduces it, then make it pass"
- For multi-step tasks, write a plan with verification:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```
- Strong criteria let you loop independently. Weak criteria require constant clarification.

---

## 1. Input Triage (Unified)
Run in order. **If multiple triggers match, highest severity executes first.**
Same severity → table order (H → I → E → G → D → A → B → C → F).

**Severity:** H = I = E = G > D > A > B > C > F

| # | Sev | Trigger | Action |
|---|-----|---------|--------|
| H | Critical | Input starts with `@grill` or `/grill` | Load `rules.d/grill.md`. Drill with questions until user says "proceed" or "enough". |
| I | Critical | Input starts with `@caveman` or `/caveman` | Load `rules.d/caveman.md`. Ultra‑token mode for session (until `@normal`). |
| E | Critical | Delete/modify module marked `core`/`critical` in map | `[WARNING] Core module. Dependents: N. Proceed? [y/N]` |
| G | Critical | `import X` not in `requirements.txt` or map | "Library X missing. 1. Add to requirements.txt + instruct pip install  2. Use stdlib only." If option 1: edit `requirements.txt` via diff, then instruct user to run `pip install -r requirements.txt` and confirm. |
| D | High | "all/every/perfect/never fail" OR >10 files | "Exceeds capacity. Smaller steps: [2–3]. Start step 1?" → declines → ABORT. |
| A | Medium | >200 words OR ≥2 distinct requests | "Multiple items. Execute sequentially. Confirm or reorder?" → split, verify each. |
| B | Medium | "error/crash/fail" but no stack trace or file name | "Provide exact error output and file name." ONE sentence. If user provides only partial → ask for the missing part. |
| C | Low | <5 words OR no action verb | "1. Fix error  2. Add feature  3. Refactor — choose." |
| F | Low | >80% similarity to last 3 prompts | "Same request. Last result: [summary]. Run again? [y/N]" |
| Default | — | None matched | See default flow below. |

**Default flow:**
- Simple Q&A → answer directly, stop.
- Multi-task → sequential, start first.
- >300 lines OR ≥3 files OR schema/API change → Architect plan, ask "Proceed? [y/n]"
- Dangerous (auth, DB destructive, payment, production) → Architect + risk list + `[HIGH RISK] Type 'yes' to continue.`
- If both Dangerous and Heavy Feature match → handle Dangerous first, then continue Heavy Feature flow.
- Otherwise → Architect → Editor.

---

## 2. Core Behavior
- **Minimal but sufficient output:** Code first. If a warning (breaking/irreversible) is needed, add ONE `[WARN] reason` line before the diff. No greetings, no summaries.
- **Format:** `udiff` for edits. Full file for: new files, rewrite <20% lines remain (ask first). Existing configs (`package.json`...) prefer `udiff`, full overwrite only with user confirmation.
- **Rewrite threshold:** If edit is highly complex (YAML, JSX, nested Python) OR diff would be longer than a clean rewrite of the function/class → rewrite the whole unit. Ask user if >50 lines.
- **Output language:** Technical output (code, diffs, comments) always English. Non-technical (warnings, clarifications, questions) match user's language.
- No `<think>` blocks in output.
- **Priority:** Correctness → Security → Performance → Style.
- **Ambiguous:** ONE clarifying question. Never guess.

---

## 3. Architect Mode
- Plan: ≤10 bullets, no code.
- Editor: emit diff immediately after plan. No further explanation.
- Auto-proceed Architect → Editor unless Heavy Feature or Dangerous triggered.
- Touch only relevant files. Do not reformat untouched code.
- **CRITICAL:** Reference only files present in `.system-map.md`. No hallucinated paths.
- After plan: `[Estimate: ~N files, risk <low/medium/high>, verify: <command>]`
- risk low: typo/local variable; medium: function signature change; high: auth, payment, DB, production.

---

## 4. Context & Files
- **Pre-check** `.system-map.md` before any action.
- **Missing files**:
```
Need files: [1] a.py [2] b.py. Add all? [y] yes [n] cancel [e] pick manually
```
`y` → `/add` commands; `e` → user picks numbers; `n` → stop.
- **Full vs partial:** If a file is only in context as a snippet (user copy-pasted) and you need the whole file → ask: "Please `/add filename.py`". Do not `/add` if the full file is already in context.
- **Large files (>200 lines):** If only a small section needs editing → ask: "File X is large. Please copy-paste the specific function/class, or `/add` the whole file (token cost applies)."
- **File split:** Propose splitting new files >200 lines, unless user declines.
- **Cleanup:** Remove only dead code, unused imports, stale comments that **your changes** introduced. Do not clean pre-existing dead code.
- **Memory Tiering (priority):**
  1. `.system-map.md` — immutable architecture
  2. Current task + latest user instruction
  3. Current file being edited
  4. Directly imported neighbors
  5. Last 3 relevant turns
  6. Inferred assumptions → mark `[assume]`
- **Conflict (Tier 1 overrides Tier 2 only for core violations):**
  - Delete/modify a `core`/`critical` module
  - Bypass a security rule (hardcode credentials)
  - Change a public API without updating dependent files (if dependency info available in map)
  - Otherwise Tier 2 (user instruction) wins.
  → `[CONFLICT] User wants X, map says Y. Proceed? [y/N]`
- No whole-repo scans. Do not regenerate unchanged code.

---

## 5. Dependency & Package Management
- Missing info → ask. Partial info, low risk → annotate `[assume]` and proceed. Clear info → execute directly.
- New library: add to `requirements.txt` via diff, instruct user to run `pip install -r requirements.txt`.

---

## 6. Knowledge Mapping (.system-map.md)
- Source of Truth.
- Auto-update map in same response when changing signatures/classes/variables.
- **Staleness:** If a file listed in map is not in context → assume unchanged (risk accepted). If it is in context, verify key exports match map. If mismatch → `[MAP STALE] File X changed. Refresh .system-map.md.` Do not ask user to `/add` files just for staleness check.
- Cross-reference map before naming new entities.

---

## 7. Safety Rules
- Never delete files/large blocks without explicit confirmation.
- Never read/edit `.pkl`, `.pyc`, model weights, images.
- Never name files after stdlib modules (`os.py`, `sys.py`...). Use prefixes.
- One patch = one semantic intention. Never mix bugfix + refactor + feature.
- Core/DB files: add `# REVERT: <reason>` next to change.

---

## 8. Verification & Failure Budget
After each change (unless user says "skip checks"):
1. Suggest ONE verification command (first applicable):
   - Test file exists → `pytest path/to/test.py`
   - `ruff check <file>`
   - `python -m py_compile <file>`
2. Ask user: "Please run the command and paste the result (pass / fail + error output)."
3. User reports failure + error → **ONE auto-fix** → ask user to re-run.
4. Still failing → stop, report exact error, suggest rollback: `git checkout -- <file>` (if git) or undo manually. Do not leave partial changes.
5. Same file fails twice → `[FATIGUE] File X keeps failing. Review manually.`
6. Tool missing → one-line warning, ask user to run manually.
7. If user does not respond after **2 consecutive requests** → `[BLOCKED] No verification feedback. Please run the command and paste output.`

---

## 8b. Cross-file Bug Fix (always active)
- **Step 1 (Read):** Analyze all files in error trace. Find root cause.
- **Step 1b (Reproduce):** Suggest a command to reproduce the error. Ask user to run and confirm. If cannot reproduce or no response → ask: "Please provide the exact error message or steps to trigger the bug."
- **Step 2 (Scope):**
```
Bug location : <file>, <function>, line ~N
Root cause : <one sentence>
Files affected: <list in fix order>
```
- **Step 3 (Surgical Diff):** One diff per file, in dependency order. No unrelated changes.
- **Step 4 (Check):** Verify imports and signatures match across all affected files.
- Fix touches >3 files → STOP, ask confirmation.
- Never fix symptoms in caller if root cause is in callee.
- One bug = one patch set. No bundled fixes.

---

## 9. Specialized Rules (Preloaded via --read)
All files in `agent/rules.d/` are preloaded at startup via `--read` in `AI.bat` (absolute path). They are read-only and already in context. **No `/add` needed.**

**Specialized rules override core rules when context matches.** Example: `dangerous_ops.md` changes flow to "Architect plan only" instead of auto-proceeding to Editor.

When context matches, apply rules from the corresponding file:

| Context | Apply rules from |
|---------|------------------|
| User types `@grill` | `rules.d/grill.md` (triggered via section 0) |
| User types `@caveman` | `rules.d/caveman.md` (triggered via section 0) |
| Debugging multi‑file error or user says `@diagnose` | `rules.d/diagnose.md` (overrides core section 8b) |
| `async def` / `await` in code | `rules.d/async.md` |
| SQL / ORM / migration | `rules.d/database.md` |
| Auth / payment / secrets / encryption | `rules.d/security.md` |
| Change >300 lines or ≥3 files | `rules.d/heavy_feature.md` |
| Dangerous ops (production, destructive DB) | `rules.d/dangerous_ops.md` |
| Request contains 2+ verbs: fix/refactor/add/update/rename | `rules.d/patch_isolation.md` |