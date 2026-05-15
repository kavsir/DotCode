# Patch Isolation Rules
*Apply when: request contains 2+ of these verbs: fix · refactor · add · update · rename.*

Each patch = ONE semantic intention only:
- `bugfix` — fix broken behavior
- `feature` — add new capability
- `refactor` — restructure without behavior change
- `rename` — identifier or file rename + all import/reference updates (no logic change)
- `config` — configuration/env change
- `docs` — documentation update

**Rules:**
- Never mix two intentions in one diff. Split into separate patches.
- Each patch gets its own verification step before the next begins.
- Label each patch clearly: `[PATCH 1/3 — bugfix]`, `[PATCH 2/3 — refactor]`…
- If user asks for bugfix + refactor → do bugfix first, verify, then ask: "Bugfix done. Proceed with refactor? [y/n]"
- Do not combine formatting changes with logic changes.
- If a patch in the sequence fails verification → stop the sequence. Ask: "Patch N failed. Revert previous patches or fix manually? [revert/fix]"
- If two intentions are intertwined and **cannot** be cleanly separated → output:
  `[WARNING] Mixed intentions but cannot separate cleanly. Proceed with single patch? [y/N]`
  If yes → add comment: `# MIXED: bugfix+refactor per user approval`.
  - **Intertwined example:** Fixing a null-check bug requires extracting a helper function that also restructures the caller — splitting would leave both sides broken mid-patch.
- If user insists on mixing despite ability to separate → confirm, then add: `# OVERRIDE: user requested mixed patch`.

**Note on `rename`:** Renaming an identifier or file typically requires updating imports across multiple files. This counts as a single `rename` patch — do not split per-file. Complete all reference updates atomically, then verify once.