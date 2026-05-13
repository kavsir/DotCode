# Cross-file Bug Fix Rules
*Loaded when: error spans more than 1 file.*

Follow this sequence exactly:

**Step 1 (Read):** Analyze all files in error trace. Find true root cause. Do not touch anything yet.

**Step 2 (Scope):**
```
Bug location : <file>, <function>, line ~N
Root cause   : <one sentence>
Files affected: <list in fix order>
```

**Step 3 (Diff):** One diff per file, in strict dependency order. No unrelated changes.

**Step 4 (Check):** Verify imports and signatures match across all affected files.

**Hard rules:**
- Fix touches >3 files → STOP, ask confirmation before proceeding.
- Never fix symptoms in caller if root cause is in callee.
- One bug = one patch set. Do not bundle unrelated fixes.
