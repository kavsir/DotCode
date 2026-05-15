# Changelog
*Load on demand: trigger = user asks about history, or agent needs to verify past API changes.*
*Never load at startup. Append one row per session when function signatures or module structure changes.*

---

## How to use

**Agent:** When changing a function signature, class name, or public API:
1. Apply the change.
2. Append a row to this file in the same response.
3. Update `system-map-core.md` Module Map if the file's status changed.

**Format for new row:**
```
| YYYY-MM-DD | <file> | <what changed — one line> | <why — one line> |
```

---

## Log

| Date | File | Change | Reason |
|------|------|--------|--------|
| 2025-xx-xx | `agent/system-map-core.md` | Init — split from system-map.md | Tiered context refactor |
| 2025-xx-xx | `agent/rules-core.md` | Init — split from rules.md | Tiered context refactor |
| 2025-xx-xx | `agent/rules-extended.md` | Init — split from rules.md | Tiered context refactor |
| 2025-xx-xx | `agent/rules.d/sandbox.md` | Init — new file | Shell safety layer |
| 2025-xx-xx | `agent/lesson-log.md` | Init — new file | Bug pattern knowledge base |
| 2025-xx-xx | `AI.bat` | Reduced --read from 12 to 3 files | Tiered context refactor |