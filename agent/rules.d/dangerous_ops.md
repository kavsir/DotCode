# Dangerous Operations Rules
*Loaded when: production deployment / destructive DB / infrastructure changes.*

- Output Architect plan only. List ALL risks explicitly before any code.
- Require: `[HIGH RISK] Proceed? Type 'yes' to continue.`
- If user does not type exactly `yes` → ABORT. No exceptions.
- Suggest creating a rollback plan before proceeding.
- Add `# REVERT: <reason>` to every changed line in critical files.
- Never auto-commit dangerous changes. Always leave for user to review and commit manually.
- If change affects production infrastructure → suggest staging environment test first.
