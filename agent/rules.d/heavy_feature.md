# Heavy Feature Rules
*Apply when: estimated diff size >300 lines (additions + deletions combined) OR touches ≥3 files.*

## Pre-apply Checkpoint (mandatory)

Before writing any code, agent MUST output and wait for confirmation:

```
[CHECKPOINT] Large change detected. Before starting:
1. Run: git commit -m "checkpoint: before <feature-name>"
2. Confirm: type 'checkpoint-done' to continue.
```

- User does not type `checkpoint-done` → do not proceed.
- Checkpoint is per-feature, not per-file. One checkpoint at the start covers the whole feature.

## Feature Flow

- Output Architect plan first (≤10 bullets). Ask: "This is a significant change. Proceed? [y/n]"
- If user says no → stop. No code.
- Check current branch: `git branch --show-current`.
  - If on `main`/`master` → suggest: `git checkout -b feat/<name>`
  - If user declines → add `[WARN] Working directly on main/master.` and proceed.
- Break into sub-tasks, one file at a time. Verify each before proceeding.
- After each sub-task, run broader verification (`pytest` for whole module). Ask user to run if automated not possible.
- Do not proceed to next file until current file passes verification.

## Sub-task Failure

If any sub-task fails verification → stop entire feature. Output immediately:

```
[ROLLBACK] Sub-task failed. Options:
1. rollback — revert all changes so far: git reset --hard HEAD  (or per-file: git checkout -- <file>)
2. fix      — attempt manual fix, then re-run verification
Type 'rollback' or 'fix':
```

- User types `rollback` → output exact rollback commands for every file changed so far, in reverse order.
- User types `fix` → wait for user fix, then re-run verification once. If still failing → force rollback.

## Scope Expansion

If total scope expands beyond original estimate mid-task → stop immediately:

```
[SCOPE CHANGE] Original estimate: ~N files. Current: ~M files.
Re-confirm before continuing? [y/n]
```