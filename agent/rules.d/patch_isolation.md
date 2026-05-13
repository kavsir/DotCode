# Patch Isolation Rules
*Loaded when: multiple patch intentions detected in one request.*

Each patch = ONE semantic intention only:
- `bugfix` — fix broken behavior
- `feature` — add new capability
- `refactor` — restructure without behavior change
- `config` — configuration/env change
- `docs` — documentation update

**Rules:**
- Never mix two intentions in one diff. Split into separate patches.
- Each patch gets its own verification step before the next begins.
- Label each patch clearly: `[PATCH 1/3 — bugfix]`, `[PATCH 2/3 — refactor]`…
- If user asks for bugfix + refactor in same request → do bugfix first, verify, then ask: "Bugfix done. Proceed with refactor? [y/n]"
- Do not combine formatting changes with logic changes.
