# Diagnose – Systematic Debugging
*Apply when: user explicitly asks to diagnose a bug (`@diagnose`), OR an error spans multiple files.*  
**Overrides** core section 9 (Cross‑file Bug Fix) when context matches.

## The 6‑step loop
Execute these steps strictly in order. Do not skip.

### 1. Reproduce
- Suggest one command to reproduce the error exactly.
- Ask user to run it and confirm the output.

### 2. Minimise
- Find the smallest input / steps that still trigger the bug.
- **Actively propose specific removals** — do not ask the user to figure out what is unrelated.
  - Example: *"Does the database config affect this bug? If not, let's exclude it and re-run."*
- Remove confirmed-unrelated factors (unused imports, irrelevant configs) after user confirms.

### 3. Hypothesise
- Propose **1–2 hypotheses** for the root cause.
- For each hypothesis, describe what evidence would confirm or refute it.

### 4. Instrument
- Suggest adding logs, print statements, or assertions to test the hypotheses.
- Ask user to run with instrumentation and share the output.
- Example: `Add `print(f"value of x: {x}")` before line 42.`

### 5. Fix
- Based on evidence, apply a **minimal surgical fix**.
- Do not add features, refactor, or improve unrelated code.

### 6. Regression test
- Verify the fix works (run the reproduction command again).
- Run existing tests in the same module to ensure nothing else broke.
- Ask user to run broader test suite if available.

## Output format (after each step)
`[DIAGNOSE] Step N/6 done: <summary>`

## Escalation
Two failure types are tracked separately:

**Type A — User not responding:**
→ Apply core rule `[BLOCKED]` (Section 8, rule 7): after 2 consecutive unanswered requests, prompt user.

**Type B — Command still failing after fix attempt:**
- **After 1 failure** → try a different approach (different reproduction command, different instrumentation).
- **After 2 failures** → stop and escalate:
  `[DIAGNOSE] Stuck at step <N>. Please provide more details or fix manually.`