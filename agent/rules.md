# AI Coding Rules

## Core behavior
- Minimal output. Code changes only, no commentary unless asked.
- Edit format: always `diff` / `udiff`. Never rewrite whole file unless structure changed >50%.
- Respond in English. Understand Vietnamese input.
- Priority: correctness → security → performance → style.
- If ambiguous, ask ONE clarifying question. Do not guess intent.
- Do not make assumptions about external libraries; stick strictly to standard library features or libraries explicitly present in the files.

## Architect mode
- **Architect step**: concise plan only, ≤10 bullets. No code.
- **Editor step**: emit the diff immediately after the plan. No explanation, no repetition of the plan.
- Only touch files relevant to the task.
- Never rewrite a file just to reformat or rename variables.
- CRITICAL: Refer ONLY to files that actually exist in the repository map. Do not invent placeholder files or suggest non-existent directories.

## Context Management & Files
- **Pre-check**: Before requesting any files, the AI MUST consult `.system-map.md` to identify the minimum necessary files for the task.
- **Request Format**: If required files are not in chat context:
  1. List all needed files and ask for confirmation:
     ```
     Need files:
     [1] path/to/file1.py
     [2] path/to/file2.py
     [3] path/to/file3.py
     Add all? [y] yes  [n] cancel  [e] pick manually
     ```
  2. If user replies `y` → emit all `/add` commands immediately:
     ```
     /add path/to/file1.py
     /add path/to/file2.py
     /add path/to/file3.py
     ```
  3. If user replies `e` → re-list files numbered, user picks by number, then emit only selected `/add` commands.
  4. If user replies `n` → stop. Do not proceed.
- **Efficiency**: Never ask for files that are already listed in the current chat session. Use `Read-only` mode for reference files (like maps or docs) to save tokens.
- **File Split**: Split into separate files when any file exceeds ~200 lines.
- **Cleanup**: Remove dead code, unused imports, stale comments in every diff.
- **No Over-engineering**: No abstractions not explicitly requested. No tests unless asked.

## Dependency & Package Management
- **No Guessing**: Never write code using external libraries not listed in `requirements.txt` or `.system-map.md`.
- **Requirements Update**: If a task requires a new third-party library:
  1. The AI must first propose adding the package (with version) to `requirements.txt`.
  2. The AI must explicitly instruct the user to run the install command (e.g., `pip install -r requirements.txt`).
- **API Reference**: If using a newly released library/API, ask the user for a quick syntax markdown or check `.system-map.md` for exact usage examples before writing code.

## Knowledge Mapping (.system-map.md)
- **Role**: This file is the "Source of Truth" for project architecture, listing module responsibilities, key functions, shared variables, and project-wide standards.
- **Initialization**: If `.system-map.md` does not exist, the AI must propose creating it after the first architectural plan.
- **Auto-Update**: Any change to function signatures, classes, or shared variables MUST be mirrored in `.system-map.md` in the same diff block.
- **Consistency**: Always check `.system-map.md` before naming new variables or functions to ensure project-wide consistency.

## Interaction Rules
- **Context Expansion**: If a task requires logic from files not currently in the chat, the AI must explicitly list them using the `/add <path>` format at the beginning of the response.
- **Modification Policy**: The AI is encouraged to suggest edits (`diff`) to existing files whenever necessary to fulfill the goal.
- **Deletion Safety**: NEVER propose deleting entire files or large blocks of functional code without asking for explicit user confirmation.
- **Binary Files**: Never attempt to read or edit binary files like .pkl, .pyc, or model weights.

## Communication Efficiency
- **No Recaps**: Never summarize what the user just said or what you are about to do.
- **Direct Action**: Move straight from "Architect step" to "Editor step" automatically.
- **Token Saving**: Use concise technical English for internal logic and plan steps.

## Output format
- Diffs: file path header in every hunk.
- Code review: [LINE N][critical|warn|info] issue -> fix.
- New files: 2-line comment header (purpose + main deps).
- Never add TODO / FIXME unless asked.
- Never repeat the user's question. Never explain diff syntax.

## Cross-file bug fix — surgical edit workflow
Follow this sequence exactly when an error spans multiple files:

**Step 1 — Read, don't touch**
Read all files in the error trace. Find the source file.

**Step 2 — Declare scope**
Before any diff, output:
Bug location : <file>, <function/block>, line ~N
Root cause   : <one sentence>
Files affected: <list in fix order>

**Step 3 — Surgical diff**
- One diff per file, in dependency order. No unrelated changes.

**Step 4 — Compatibility check**
Verify imports and signatures match across all affected files.

**Hard rules**
- If fix touches >3 files -> stop, ask for confirmation.
- CRITICAL: When creating new files, you MUST provide the full file content in a single diff block so Aider can write it immediately.
