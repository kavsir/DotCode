# Database & Migration Rules
*Apply when: SQL / ORM / migration detected.*

- Destructive actions (`DROP`, `TRUNCATE`, `ALTER TABLE DROP COLUMN`, schema migration without rollback) require explicit user confirmation even in dev.
- For irreversible migrations, require user to type `I UNDERSTAND THE RISK` before proceeding.
- Never edit an already applied migration. Create a new migration instead.
- Before schema changes: suggest user backup or work on a copy.
- Parameterized SQL only (`?` / `%s`). Never string concatenation.
- For ORM code (SQLAlchemy, Django, Peewee): prefer ORM's parameterized methods over raw SQL unless explicitly requested.
- Always ensure transactions are committed or rolled back. Use context managers (`with` statement) when available.
- Never leave database connections open after operation — use connection pools or close explicitly.
- Add `# REVERT: <reason>` comment next to any destructive schema change.