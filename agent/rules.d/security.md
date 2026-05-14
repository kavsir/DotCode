# Security Rules
*Apply when: auth / payment / secrets / encryption detected.*

- Never hardcode credentials, tokens, or API keys. Use env vars or vaults.
- Never log or print secrets, tokens, keys, or PII — even in debug mode. If debugging needed, suggest redacting secrets before logging.
- No `shell=True` in subprocess. Use list arguments.
- Validate all external input (files, network, user) with explicit type/range checks. Always trim and validate length to avoid DoS.
- No `chmod 777`. No writes to system dirs without confirmation.
- For password hashing, use `bcrypt` or `argon2`. Never `MD5` or `SHA1`.
- For auth/payment code, add comments: `# TRUST: <boundary>` and `# VALIDATE: <input>`.
- Explicitly list risks in Architect plan: "Risk: may lock out all users."
- Require `[HIGH RISK] Proceed? Type 'yes' to continue.` before any auth/payment diff.