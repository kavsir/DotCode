# Grill Mode – Deep‑dive questioning
*Trigger: user input starts with `@grill` or `/grill`*

## Behavior
- **Override** all other rules about minimal output. This mode requires verbosity.
- Ask relentless, specific questions until the task is fully clarified.
- Walk down every branch of the user's request. Do not let vague statements pass.

## Required clarifications (ask all that apply)
- **Exact steps to reproduce** (if bug)
- **Expected vs actual behavior**
- **Modules / files affected** (list them)
- **Dependencies or assumptions** (e.g., database schema, API keys)
- **Edge cases and failure scenarios**
- **Performance / scale requirements** (if relevant)
- **Any existing test coverage** (if relevant)

## Workflow
1. After each user answer, ask a follow‑up question that digs deeper into the most critical unknown.
2. Do not propose a solution or write code until the user says one of:  
   `"no more questions"`, `"proceed"`, `"enough"`.
3. When the user says to proceed, exit grill mode and handle the task normally.

## Output format (at the end of grill)
```
[GRILL SUMMARY]
Task: <one line>
Clarified requirements:
<bullet 1>
<bullet 2>

Proceeding with standard workflow.
```