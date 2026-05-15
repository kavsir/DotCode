# Aider Limits & Recovery
*Apply when: Aider appears stuck, unresponsive, or spinning on directory/file scan.*
*Part of Tier 2 — load via `/add rules.d/aider-limits.md` when needed.*

---

## Directory Traversal Limit

- Max traversal depth: `MAX_DIR_DEPTH = 2` (from system-map-core.md constants).
- If a task requires scanning deeper than 2 levels → STOP immediately.

```
[AIDER-LIMIT] Directory too deep for auto-scan (>2 levels).
Please provide the file list manually:
  Option 1: /add <specific files you want me to work on>
  Option 2: Paste the output of: dir /s /b *.py   (Windows)
                              or: find . -name "*.py"  (Unix)
```

- Never attempt recursive scan of the whole project tree.
- Never use glob patterns that match >20 files at once without user confirmation.

---

## Aider Stuck Recovery

Signs that Aider is stuck: no output for >30s, repeated identical messages, loop without progress.

**Step 1 — Break the loop:**
```
[AIDER-STUCK] No progress detected. Stopping current operation.
Press Ctrl+C to interrupt if Aider is unresponsive.
```

**Step 2 — Reduce scope:**
- Drop all files from context: `/drop`
- Add back only the specific file needed: `/add <file>`
- Retry with a smaller, more specific request.

**Step 3 — If still stuck:**
```
[AIDER-STUCK] Cannot proceed with current context.
Options:
1. Restart AI.bat with a fresh session
2. Manually edit <file> at line ~N based on the plan above
3. Provide a minimal reproduction of the problem
```

---

## Context Size Warning

If Aider warns about context size or token limit:
1. `/drop` all files not directly needed for current sub-task.
2. Work on one file at a time.
3. For files >200 lines: ask user to paste only the relevant function/class.

---

## Long-term fix (GĐ2)

Current dependency on Aider is a known limitation of GĐ1.
GĐ2 (Single Agent Runtime) will replace Aider with a custom executor.
Until then, these rules are the mitigation layer.