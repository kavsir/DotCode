# system-map-core.md
*Always load. ~30 lines. Detail in lesson-log.md and changelog.md.*

---

## Project Info

```
Name  : Agent_Code
Stage : GĐ 1 — Foundation
Stack : Python 3.11 · Aider · DeepSeek
Entry : AI.bat
```

---

## Active Goal
*Update manually when starting a new task.*

```
Task    : —
Stage   : GĐ 1
File    : —
Success : —
Blocked : —
```

**Rule:** Before every action, read Active Goal. If the action does not serve it → flag before proceeding.

---

## Module Map

| File | Purpose | Status |
|------|---------|--------|
| `agent/rules-core.md` | Core coding policy | ✅ Active |
| `agent/rules-extended.md` | Extended rules, load on demand | ✅ Active |
| `agent/rules.d/sandbox.md` | Shell command safety | ✅ Active |
| `agent/system-map-core.md` | Source of truth (this file) | ✅ Active |
| `agent/lesson-log.md` | Bug patterns & lessons learned | ✅ Active |
| `agent/changelog.md` | Module change history | ✅ Active |

---

## Shared Constants

| Name | Value | Used By |
|------|-------|---------|
| `MAX_FILE_LINES` | `200` | All modules |
| `MAX_DIR_DEPTH` | `2` | All directory traversal |
| `AGENT_DIR` | `D:\Agent_Code` | `AI.bat` |

---

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| File | `snake_case.py` | `retry_manager.py` |
| Class | `PascalCase` | `RetryManager` |
| Function | `snake_case` | `run_command()` |
| Constant | `UPPER_SNAKE` | `MAX_RETRIES` |
| Branch | `feat/` `fix/` `refactor/` | `feat/runtime-executor` |