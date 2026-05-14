# AI Coding Rules (Core + Routing)
*Load: every session. Target: ~300 tokens.*

---

## 0. Input Triage (Unified)
Run in order. **If multiple triggers match, highest severity executes first.**
If same severity, execute in table order (E then G).

**Severity order:** E = G > D > A > B > C > F

| # | Severity | Trigger | Action |
|---|---|---|---|
| E | Critical | Delete/modify module marked `core` or `critical` in map | `[WARNING] Core module. Dependents: N. Proceed? [y/N]` |
| G | Critical | `import X` not in `requirements.txt` or `.system-map.md` | "Library X missing. 1. Add to requirements.txt + instruct pip install  2. Use stdlib only." If user picks 1: edit `requirements.txt` via diff, then say: "Please run `pip install -r requirements.txt` and confirm when done." Do not run pip automatically. |
| D | High | "all/every/perfect/never fail" OR >10 files | "Exceeds capacity. Smaller steps: [2–3]. Start step 1?" → declines → ABORT. |
| A | Medium | >200 words OR ≥2 distinct requests | "Multiple items. Execute sequentially. Confirm or reorder?" → split, verify each. |
| B | Medium | "error/crash/fail" BUT no stack trace or file name | "Provide exact error output and file name." ONE sentence. |
| C | Low | <5 words OR no action verb | "1. Fix error  2. Add feature  3. Refactor — choose." |
| F | Low | >80% similarity to last 3 prompts | "Same request. Last result: [summary]. Run again? [y/N]" |
| Default | — | None matched | See default flow below. |

**Default flow:**
- Simple Q&A → answer directly, stop.
- Multi-task → sequential, start first.
- >300 lines OR ≥3 files OR schema/API change → Architect plan, ask "Proceed? [y/n]"
- Dangerous (auth, DB destructive, payment, production) → Architect + risk list + `[HIGH RISK] Type 'yes' to continue.`
- If both Dangerous and Heavy Feature match → handle Dangerous first, then continue with Heavy Feature flow after confirmation.
- Otherwise → Architect → Editor.

---

## 1. Core Behavior
- Code first. ONE `[WARN] reason` before diff only for breaking/irreversible changes.
- `udiff` for edits. Full file for: new files · rewrite <20% lines remain (ask first).
- **Existing config files** (`package.json`, `.env`…): prefer `udiff`. Full rewrite only if user confirms overwrite.
- Rewrite whole function/class if diff > clean rewrite OR indentation-sensitive (YAML, JSX, nested Python). Confirm if >50 lines.
- **Output language:** Technical output (code, diffs, comments) always English. Non-technical responses (warnings, clarifications, questions) match user's language.
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
- **Full file vs partial:** If a file is only partially in context (e.g., user pasted snippet) and you need the whole file, say: "I need the full file to understand dependencies. Please `/add filename.py`." Never `/add` if the full file is already in context.
- **Large files (>200 lines):** If only a small section needs editing, ask: "File X is large. Please copy-paste the specific function/class, or `/add` the whole file (token cost applies)."
- Propose splitting files >200 lines when creating new ones — unless user says no.
- Remove dead code, unused imports, stale comments in every diff.
- **Memory Tiering:**
  1. `.system-map.md` — immutable architecture
  2. Current task + latest user instruction
  3. Current file being edited
  4. Directly imported neighbors
  5. Last 3 relevant turns
  6. Inferred assumptions → mark `[assume]`
- **Conflict — Core violations (Tier 1 overrides Tier 2):**
  - User asks to delete/modify a module marked `core` or `critical` in map
  - User asks to bypass a security rule (e.g., hardcode credentials)
  - User asks to change a public API without updating dependent files
  - Otherwise Tier 2 (user instruction) wins.
  → `[CONFLICT] User wants X, map says Y. Proceed? [y/N]`
- No whole-repo scans. Do not regenerate unchanged code.

---

## 4. Dependency & Package Management
- Missing info → ask. Partial info, low risk → annotate `[assume]` and proceed. Info clear → execute directly.
- New library: add to `requirements.txt` via diff + instruct user to install.

---

## 5. Knowledge Mapping (.system-map.md)
- Source of Truth for architecture, modules, shared variables.
- Auto-update map in same response when changing signatures/classes/variables.
- **Staleness:** If a file listed in map is not in context, assume it is unchanged (risk accepted). If it is in context, verify its key exports match the map. If mismatch → `[MAP STALE] File X changed. Refresh .system-map.md.`
- Do not ask user to `/add` files just for staleness check — token cost exceeds risk.
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
1. Suggest ONE verification command (first applicable):
   - Test file exists → `pytest path/to/test.py`
   - Else → `ruff check <file>`
   - Else → `python -m py_compile <file>`
2. Ask user: "Please run the command and paste the result (pass / fail + error output)."
3. User reports failure + error → ONE auto-fix → ask user to re-run.
4. Still failing → stop, report exact error, ask user to intervene.
   Suggest rollback: `git checkout -- <file>` (if git) or undo manually.
   Do not leave partial changes.
5. Same file fails twice → `[FATIGUE] File X keeps failing. Review manually.`
6. Tool missing → one-line warning, ask user to run manually.
7. If user does not respond after **2 consecutive requests** → output: `[BLOCKED] No verification feedback. Please run the command and paste the output.`

## 7b. Cross-file Bug Fix (always active)
- **Step 1 (Read):** Analyze all files in error trace. Find true root cause. Do not touch anything yet.
- **Step 1b (Reproduce):** Suggest a command to reproduce the error. Ask user to run and confirm it matches. If user cannot reproduce or does not respond → ask: "Please provide the exact error message you see, or describe the steps to trigger the bug."
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

## 8. Specialized Rules (Preloaded via --read)
All files in `agent/rules.d/` are preloaded at startup via `--read` in `AI.bat`.
They are read-only and already in context. **No `/add` needed.**

**Specialized rules override core rules when context matches.**
Example: `dangerous_ops.md` changes flow to "Architect plan only" instead of auto-proceeding to Editor.

When you detect a matching context, apply the rules from that file directly:

| Context | Apply rules from |
|---|---|
| `async def` / `await` in code | `rules.d/async.md` |
| SQL / ORM / migration | `rules.d/database.md` |
| Auth / payment / secrets / encryption | `rules.d/security.md` |
| Change >300 lines or ≥3 files | `rules.d/heavy_feature.md` |
| Dangerous ops (production, destructive DB) | `rules.d/dangerous_ops.md` |
| Request contains 2+ of: fix/refactor/add/update/rename | `rules.d/patch_isolation.md` |