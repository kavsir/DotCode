# Lessons Learned from Open Source AI Coding Agents

This document summarizes key insights from three influential open‑source projects and how DotCode intends to apply them across its development roadmap.

## Reference Projects

| Project | Focus | Key Strengths |
|---------|-------|----------------|
| **mattpocock/skills** | Task‑specific workflows | `/grill`, `/caveman`, `/diagnose`, `/tdd` – user‑invoked expert modes |
| **lsdefine/GenericAgent** | Minimal agent core | 9 atomic tools, L3 Skill Layer (SOP reuse), aggressive context compression, 3‑level failure escalation |
| **affaan-m/everything-claude-code** | Production‑scale agent harness | 47 agents, 181 skills, 79 commands, hooks, continuous learning (instincts), AgentShield security |

## 1. What DotCode Already Does Well (vs. These Projects)

| Principle | DotCode Implementation |
|-----------|------------------------|
| **Input Triage** | 7 scenario‑based triggers with severity ordering (H, I, E, G, …) – more structured than skills' ad‑hoc commands. |
| **Token Efficiency** | Zero yapping, `--read` preloading, caveman mode (`@caveman`) – on par with GenericAgent’s compression. |
| **Surgical Changes** | Single intention per patch, patch isolation rules, rollback comments – stronger than all three. |
| **Safety** | Dangerous ops double confirmation, core module protection, security rules concrete – comparable to AgentShield’s philosophy. |
| **Architect Mode** | Plan‑first, diff‑second with estimation – clean separation of concerns. |

## 2. Concepts to Adopt in Future Phases

### Phase 2 (Runtime – `runtime/`)

| Concept | Source | DotCode Action |
|---------|--------|----------------|
| **3‑level failure escalation** | GenericAgent | Extend `retry_manager.py`: Level 1 = local fix (same strategy), Level 2 = strategy shift (read more files, search web), Level 3 = user intervention. |
| **Hooks (event‑driven automation)** | ECC | Add `hooks/` directory with scripts for `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`. Useful for auto‑logging, safety checks, state persistence. |
| **Context compression (FIFO + truncation)** | GenericAgent | Implement in `context_manager.py`: truncate tool output after 500 lines, keep last 10 messages, deduplicate repeated file reads. |

### Phase 3 (Tools – `tools/`)

| Concept | Source | DotCode Action |
|---------|--------|----------------|
| **9 atomic tools (read, write, patch, run, web, ask, checkpoint, learn)** | GenericAgent | Start with these 9 tools in `tools/`. Avoid bloating. Add more only when usage patterns justify. |
| **Checkpoint / resume** | GenericAgent, ECC | Implement `update_working_checkpoint` tool to save session state (SQLite or JSON). Allow resume after context limit or crash. |

### Phase 4 (Memory – `memory/`)

| Concept | Source | DotCode Action |
|---------|--------|----------------|
| **L3 Skill Layer (SOP storage & retrieval)** | GenericAgent | Build `memory/skills/`. Each skill = markdown file with trigger patterns, steps, commands, verification. Auto‑save when a task succeeds (`@learn` or automatic). |
| **Continuous learning (instincts with confidence)** | ECC | Extend skill layer: after each success, increment confidence; after failure, decrement. Surface high‑confidence skills to context without manual load. |
| **Selective rule/skill loading via manifest** | ECC | Create `skills.manifest.json` or `rules.manifest.json` for projects to declare which skills/rules to preload. Reduce token cost. |

### Phase 5 (Evaluation – `evaluation/`)

| Concept | Source | DotCode Action |
|---------|--------|----------------|
| **Grader types & pass@k metrics** | ECC | Add multiple grader strategies (exact match, regex, LLM as judge). Track pass@1, pass@3 for bug fixes. |
| **Checkpoint vs continuous evals** | ECC | Allow evaluation to run at every verification (continuous) or only at task boundaries (checkpoint). |

### Phase 7 (Safety – `safety/`)

| Concept | Source | DotCode Action |
|---------|--------|----------------|
| **AgentShield‑like scanner** | ECC | Build `safety/scanner.py` to scan diffs for hardcoded secrets, dangerous shell commands, permission misconfigs before applying. |
| **Hook‑based permission checks** | ECC | Use hooks (Phase 2) to intercept and validate every tool call against safety policies. |

### Phase 8 (Autonomous Loop – `loop/`)

| Concept | Source | DotCode Action |
|---------|--------|----------------|
| **Multi‑agent orchestration (planner → coder → reviewer → runner)** | ECC | Model the `multi_agent/` directory after ECC’s subagent design. Each agent has its own model, tools, and prompt. |
| **Parallelization via Git worktrees** | ECC | Allow multiple agents to work on different branches simultaneously using `git worktree`. |
| **Code Sovereignty protocol (external models for draft)** | ECC | For complex tasks, allow an external model (e.g., Gemini, Codex) to generate a prototype, then Claude/DeepSeek refines. |

## 3. What DotCode Will NOT Adopt (or Will Defer)

| Concept | Reason |
|---------|--------|
| **47 subagents from start** | Too heavy for GĐ1–8; will implement multi‑agent only in GĐ9 after runtime is stable. |
| **181 pre‑built skills** | DotCode prefers letting skills emerge from project‑specific successes (organic learning). |
| **Separate commands (e.g., `/plan`, `/tdd`)** | DotCode uses `@` triggers instead of slash commands for simplicity. May reconsider if user demand grows. |
| **Rust control‑plane** | DotCode stays Python for accessibility and easy hacking. |

## 4. Immediate Next Steps for DotCode (GĐ1 Complete)

- [x] Core rules with 7 scenarios + grill/caveman/diagnose modes.
- [x] Specialized rules (`rules.d/`).
- [x] Documentation: `HOW_TO_WRITE_RULE.md`, `KARPATHY_PRINCIPLES.md`.
- [ ] **Update `.system-map.md`** to reflect new rule files.
- [ ] **Test `@grill`, `@caveman`, `@diagnose`** with real prompts.

## 5. Roadmap Integration

| Giai đoạn | Sẽ tích hợp bài học từ |
|-----------|------------------------|
| GĐ2 (Runtime) | GenericAgent (3‑level failure, context compression), ECC (hooks) |
| GĐ3 (Tools) | GenericAgent (9 atomic tools, checkpoint) |
| GĐ4 (Memory) | GenericAgent (L3 Skill Layer), ECC (continuous learning, manifest) |
| GĐ5 (Evaluation) | ECC (graders, pass@k) |
| GĐ6 (Observability) | ECC (session persistence, logging hooks) |
| GĐ7 (Safety) | ECC (AgentShield) |
| GĐ8 (Autonomous Loop) | GenericAgent (loop guards), ECC (parallel worktrees) |
| GĐ9 (Multi‑Agent) | ECC (subagent orchestration, Code Sovereignty) |

---

*Last updated: 2026‑05‑15*  
*Maintainer: DotCore*