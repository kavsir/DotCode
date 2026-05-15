# Sandbox Rules
*Apply when: any shell command, script execution, or file system operation is suggested.*

---

## Command Classification

Before suggesting any shell command, classify it and label it explicitly:

| Label | Meaning | Examples |
|-------|---------|---------|
| `[SAFE]` | Read-only, no side effects | `ls`, `cat`, `git status`, `python --version` |
| `[DESTRUCTIVE]` | Deletes or overwrites data | `rm`, `git reset --hard`, `DROP TABLE`, `> file` |
| `[NETWORK]` | Makes outbound connections | `curl`, `wget`, `pip install`, `git clone` |
| `[ELEVATED]` | Requires admin / modifies system | `chmod`, `chown`, `reg add`, `setx`, `runas` |
| `[MIXED]` | Combines 2+ risk types | `curl https://... | bash` → NETWORK + ELEVATED |

A command may carry multiple labels: `[DESTRUCTIVE][ELEVATED]`.

---

## Required Output Format

For every suggested shell command, output in this format:

```
Command : <full command, no truncation>
Args    : <explain each flag/argument in one line>
Risk    : [SAFE] / [DESTRUCTIVE] / [NETWORK] / [ELEVATED] / [MIXED]
Effect  : <one sentence — what this does to the system>
Confirm : Run this command? [y/N]
```

Never suggest a command without this block. Never abbreviate the command.

---

## Hard Blocks — Never Suggest Under Any Circumstances

The following patterns are unconditionally blocked. If the task requires them, stop and ask the user to run manually with full awareness:

```
rm -rf /          # wipe root
rm -rf *          # wipe current directory
curl * | sh       # remote code execution
curl * | bash     # remote code execution
wget * | bash     # remote code execution
wget * | sh       # remote code execution
chmod 777         # world-writable
chmod -R 777      # recursive world-writable
> /dev/sda        # wipe disk
dd if=* of=/dev/* # disk write
:(){ :|:& };:     # fork bomb
```

If user explicitly asks for one of these → output:
```
[SANDBOX] Blocked pattern detected. This command can cause irreversible system damage.
If you understand the risk and want to proceed manually, copy-paste the command yourself.
I will not suggest it.
```

---

## Pipeline Commands — Extra Caution

Any command chaining execution (`|`, `&&`, `;`, `$(...)`, `` ` `` ) must:
1. Be broken down step by step — explain what each segment does.
2. Carry the highest risk label of any segment in the chain.
3. Require explicit confirm before suggesting.

Example — `git add . && git commit -m "msg" && git push`:
```
Command : git add . && git commit -m "msg" && git push
Args    : add all changes → commit with message → push to remote
Risk    : [NETWORK]
Effect  : Stages all files, creates commit, uploads to remote repository
Confirm : Run this command? [y/N]
```

---

## Environment Mutation Rules

Commands that modify persistent system state (env vars, PATH, registry, startup scripts) require extra confirmation:

- **setx / reg add / export in .bashrc/.zshrc:** Label `[ELEVATED]`. Explain which key/value is changed and why it persists after reboot.
- **pip install / npm install -g:** Label `[NETWORK]`. List package name and version. Warn if installing globally vs virtualenv.
- **`install.bat` or any installer script:** Treat as `[ELEVATED][NETWORK]`. Show full content before running.

---

## Dry-Run Preference

When a command supports dry-run or preview mode, always suggest that first:

| Command | Dry-run flag |
|---------|-------------|
| `rsync` | `--dry-run` |
| `git clean` | `-n` |
| `ansible-playbook` | `--check` |
| `terraform` | `plan` before `apply` |
| `alembic upgrade` | `--sql` (shows SQL only) |

Output: `[SANDBOX] Dry-run available. Run preview first? [y/N]`

---

## Logging

For every command that is executed (user confirmed `y`), suggest appending to a local audit log:

```bat
:: Windows
echo %DATE% %TIME% — <command> >> Aider\.command-log.txt

# Unix
echo "$(date) — <command>" >> .agent/command-log.txt
```

This is optional but recommended — gives user a rollback reference if something goes wrong.

---

## Scope

These rules apply to:
- Shell commands in diffs or instructions
- Commands in verification steps (Section 8, `rules.md`)
- Commands in rollback/recovery steps (`dangerous_ops.md`)
- Installer scripts (`install.bat`, `setup.sh`, etc.)

These rules do **not** block:
- Code that runs inside the user's application (application-level shell calls are governed by `security.md`)
- Read-only introspection: `git log`, `git diff`, `ls`, `cat`