# How to Write a New Rule for DotCode

This guide explains how to create a new rule file (`.md`) for DotCode's autonomous agent.

---

## 1. Rule Types

| Type | Location | When it applies |
|------|----------|-----------------|
| Core rule | `agent/rules.md` | Every session, always active. |
| Specialized rule | `agent/rules.d/*.md` | Preloaded via `--read`, applied when context matches (trigger keyword, file pattern, or user command). |

This guide focuses on **specialized rules** (in `rules.d/`).

---

## 2. Rule File Structure

Every rule file must follow this template:

```
<Rule Name – Short Description>
Apply when: <condition>

Behavior
<bullet point 1>

<bullet point 2>

Specific instructions (optional)
<detailed steps or constraints>
Output format (if needed)
<expected output pattern>
```

**Required elements:**

- **Title** (single `#`) – describes the rule's purpose.
- **Apply when** – clear condition (e.g., user input starts with `@grill`, `async def` detected in code, error spans multiple files).
- **Behavior** – concrete actions the AI must take.

---

## 3. Trigger Conditions

Triggers can be:

| Trigger type | Example |
|---|---|
| User command | `@grill`, `/caveman` |
| Code pattern | `async def` / `await`, `import pandas` |
| Error context | error spans multiple files |
| Request characteristic | >300 lines, >=3 files |
| Severity keyword | `all/every/perfect`, `never fail` |

---

## 4. Severity Levels

When creating a rule that will be added to the Input Triage table, assign severity:

| Severity | Use for |
|---|---|
| Critical | User-invoked mode switches (`@grill`), core module safety, missing libraries |
| High | Impossible requests, destructive operations |
| Medium | Long prompts, missing error info, multi-task |
| Low | Vague prompts, repeated prompts |

---

## 5. Writing the Behavior

**Good practices:**

- Use imperative sentences: *"Ask the user..."*, *"Load file..."*, *"Do not proceed until..."*
- Be specific: *"Ask exactly ONE sentence"* is better than *"Ask the user."*
- Define exit conditions: e.g., *"until user says 'proceed' or 'enough'."*
- Override core behavior explicitly: say *"Overrides core section X when context matches."*

**Example behavior section:**

```
Behavior
Override all other rules about minimal output.

Ask relentless, specific questions until the task is fully clarified.

Do not propose code until user says "proceed".

Output a summary before exiting.
```

---

## 6. Adding the Trigger to `rules.md`

For **user-invoked triggers** (e.g., `@grill`), add a row to the **Input Triage table** in `agent/rules.md`:

| # | Sev | Trigger | Action |
|---|-----|---------|--------|
| Z | Critical | Input starts with `@yourcommand` | Load `rules.d/yourfile.md`. \<describe action\>. |

For **context-based triggers** (e.g., detecting async code), add a row to the **Specialized Rules table** in section 9 of `rules.md`:

| Context detected | Apply rules from |
|---|---|
| Your condition here | `rules.d/yourfile.md` (overrides core section X if needed) |

---

## 7. Example: A Complete Rule File

**File:** `rules.d/example.md`

```markdown
# Example Rule – Ask before writing files
Apply when: user request contains "write to /etc" or "modify system file"

Behavior
Stop immediately. Do not generate any diff.

Output: [WARNING] System file modification detected. This requires sudo and may break your OS.

Ask: "Are you absolutely sure? Type 'yes, I understand the risk' to proceed."

Only proceed if user types the exact confirmation string.

If user declines, ABORT the task entirely.
```

Then in `rules.md` section 9, add:

| Request contains "write to /etc" | `rules.d/example.md` (overrides core diff generation) |
|---|---|

---

## 8. Testing a New Rule

1. Add the `.md` file to `agent/rules.d/`.
2. Update `AI.bat` to include `--read "%AGENT_DIR%\agent\rules.d\yourfile.md"`.
3. Update `rules.md` with the trigger (Input Triage or Specialized Rules table).
4. Run a test with a matching input and observe AI behavior.

**If the rule is not triggered, check:**

- Trigger condition spelling/capitalization in `rules.md`.
- That the file is listed in `AI.bat --read`.
- That `%AGENT_DIR%` resolves correctly.

---

## 9. Common Pitfalls

| Pitfall | Fix |
|---|---|
| Rule too long (>200 lines) | Split into multiple smaller rules or use bullet points. |
| Trigger condition ambiguous | Use exact keywords, regex patterns, or user commands. |
| Forgetting to override core behavior | Explicitly state *"overrides core section X"*. |
| No exit condition | Define when the rule stops applying (e.g., *"until user says enough"*). |
| Rule conflicts with another rule | Use severity ordering in Input Triage; for specialized rules, last match wins. |

---

## 10. When to Create a New Rule

**Create a new rule when:**

- You notice the same mistake happening repeatedly.
- A specific type of task requires a unique workflow.
- A safety condition needs enforcement (e.g., dangerous commands).
- A user-invoked mode would improve productivity (e.g., `@grill`, `@caveman`).

**Do not create a rule for:**

- One-off instructions – use normal conversation.
- Something already covered by core rules or existing specialized rules.

---

## 11. Reference

- Core rules: `agent/rules.md`
- Existing specialized rules: `agent/rules.d/`
- Karpathy principles: `docs/KARPATHY_PRINCIPLES.md`
- Roadmap: `docs/update.md`