# Lesson Log
*Load on demand: trigger = `@diagnose` OR same error pattern encountered twice.*
*Never load at startup. Append one row after every completed diagnose session.*

---

## How to use

**Agent:** After every `[DIAGNOSE] Step 6/6 done`, check this file:
1. Search `Bug Pattern` column for similar pattern.
2. If found → mention it before starting diagnosis: `[LESSON] Similar bug seen before: <row>. Check <Fix> first.`
3. If not found → append a new row after fix is confirmed.

**Format for new row:**
```
| YYYY-MM-DD | path/to/file.py | <pattern in 5 words> | <one sentence> | <one sentence> | <one sentence> |
```

---

## Log

| Date | File | Bug Pattern | Root Cause | Fix Applied | Avoid Next Time |
|------|------|-------------|-----------|-------------|-----------------|
| — | — | No entries yet | — | — | — |

---

## Common Pattern Index
*Update this index when a pattern appears 2+ times.*

| Pattern | Files affected | Times seen |
|---------|---------------|------------|
| — | — | — |