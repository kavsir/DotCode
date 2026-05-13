# Database & Migration Rules
*Loaded when: SQL / ORM / migration detected.*

- Destructive actions (`DROP`, `TRUNCATE`, `ALTER TABLE DROP COLUMN`, schema migration without rollback) require explicit user confirmation even in dev.
- Never edit an already applied migration. Create a new migration instead.
- Before schema changes: suggest user backup or work on a copy.
- Parameterized SQL only (`?` / `%s`). Never string concatenation.
- Add `# REVERT: <reason>` comment next to any destructive schema change.
