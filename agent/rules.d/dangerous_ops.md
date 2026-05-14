# Dangerous Operations Rules
*Apply when: production deployment / destructive DB / infrastructure changes.*

- Output Architect plan only. List ALL risks explicitly before any code.
- Require: `[HIGH RISK] Proceed? Type 'yes' to continue.`
- If user does not type exactly `yes` → ABORT. No exceptions.
- Suggest creating a rollback plan before proceeding.
- If staging environment not available, ask: "No staging found. Continue in production? Type 'yes' at your own risk."
- After user types `yes`, output the complete set of diffs (all files). Then ask: "Review the changes above. Apply? [y/N]"
- Only apply after this second confirmation.
- Add `# REVERT: <reason>` to every changed line in critical files.
- Never auto-commit dangerous changes. Always leave for user to review and commit manually.
- After operation completes, suggest: `git add . && git commit -m "dangerous: <description>"`