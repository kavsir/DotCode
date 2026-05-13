# Heavy Feature Rules
*Loaded when: estimated change >300 lines OR touches ≥3 files.*

- Output Architect plan only first (≤10 bullets). Ask: "This is a significant change. Proceed? [y/n]"
- If user says no → stop. No code.
- Break into sub-tasks, one file at a time. Verify each before proceeding.
- Do not proceed to next file until current file passes verification.
- If total scope expands beyond original estimate mid-task → stop and re-confirm with user.
- Suggest creating a feature branch before starting: `git checkout -b feat/<name>`
