# Dangerous Operations Rules
*Apply when: production deployment / destructive DB / infrastructure changes.*

## Pre-apply Checkpoint (mandatory — not optional)

Before any diff is applied, agent MUST output this block and wait for confirmation:

```
[CHECKPOINT] Before applying changes:
1. Run: git stash   (or)   git commit -m "checkpoint: before <task>"
2. Confirm checkpoint done: type 'checkpoint-done' to continue.
```

- If user does not type exactly `checkpoint-done` → ABORT. Do not proceed.
- If user says "no git" or "not using git" → ask: "How will you recover if this change breaks things? Describe your backup plan." Wait for answer before continuing.
- Checkpoint must come BEFORE the `yes` confirmation flow below.

## Operation Flow

1. Output Architect plan only. List ALL risks explicitly before any code.
2. Require: `[HIGH RISK] Proceed? Type 'yes' to continue.`
   - User does not type exactly `yes` → ABORT. No exceptions.
3. If staging not available → ask: "No staging found. Continue in production? Type 'yes' at your own risk."
4. After `yes` → output complete set of diffs (all files). Then ask:
   `Review the changes above. Type 'apply' to execute.`
5. Apply only after `apply` confirmation.
6. Add `# REVERT: <reason>` to every changed line in critical files.
7. Never auto-commit. Leave for user to review and commit manually.
8. After operation completes, suggest: `git add . && git commit -m "dangerous: <description>"`

## Post-apply Verification (mandatory)

After applying, immediately output:

```
[POST-APPLY] Verify the system is healthy:
1. Run your verification command: <suggest one specific command>
2. If healthy → commit: git add . && git commit -m "dangerous: <task>"
3. If broken  → rollback immediately: git stash pop   (or)   git reset --hard HEAD
```

- If user reports broken after apply → output rollback command immediately. Do not attempt another fix first.
- After rollback, confirm: "Please verify system is back to baseline before retrying."