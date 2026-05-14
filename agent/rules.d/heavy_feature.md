# Heavy Feature Rules
*Apply when: estimated change >300 lines OR touches ≥3 files.*

- Output Architect plan only first (≤10 bullets). Ask: "This is a significant change. Proceed? [y/n]"
- If user says no → stop. No code.
- Before starting, check current branch: `git branch --show-current`.
  If on main/master, suggest: `git checkout -b feat/<name>`.
- Break into sub-tasks, one file at a time. Verify each before proceeding.
- After each sub-task, run a broader verification (e.g., `pytest` for the whole module, not just the changed file). Ask user to run it if automated not possible.
- Do not proceed to next file until current file passes verification.
- If any sub-task fails verification → stop entire feature. Ask user: "Sub-task failed. Rollback all changes so far or fix manually? [rollback/fix]"
- If total scope expands beyond original estimate mid-task → stop and re-confirm with user.