# Security Rules
*Loaded when: auth / payment / secrets / encryption detected.*

- Never hardcode credentials, tokens, or API keys. Use env vars or vaults.
- No `shell=True` in subprocess. Use list arguments.
- Validate all external input (files, network, user) with explicit type/range checks.
- No `chmod 777`. No writes to system dirs without confirmation.
- For auth/payment code, add comments: `# TRUST: <boundary>` and `# VALIDATE: <input>`.
- Explicitly list risks in Architect plan: "Risk: may lock out all users."
- Require `[HIGH RISK] Proceed? Type 'yes' to continue.` before any auth/payment diff.
