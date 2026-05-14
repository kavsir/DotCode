# Karpathy Principles for Coding Agents

## Source
Based on Andrej Karpathy's observations on LLM coding pitfalls (X post, 2025) and the `CLAUDE.md` guidelines by Forrest Chang.

## The Four Principles

### 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you wrote 200 lines and it could be 50, rewrite it.

**The test:** Would a senior engineer say this is overcomplicated?

### 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

**The test:** Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**

Transform imperative tasks into verifiable goals:

| Instead of... | Transform to... |
|--------------|-----------------|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

For multi-step tasks, state a brief plan with verification checks.

**Key insight from Karpathy:** "LLMs are exceptionally good at looping until they meet specific goals... Don't tell it what to do, give it success criteria and watch it go."

---

## How DotCode Implements and Extends These Principles

DotCode does not merely include these principles as text. It embeds them into an executable rule system with concrete mechanisms:

| Principle | Original (CLAUDE.md) | DotCode Enhancement |
|-----------|---------------------|---------------------|
| **Think Before Coding** | Textual guideline | Integrated into Input Triage (7 scenarios) with severity order. Forces explicit clarification (B, C, D triggers) before any action. |
| **Simplicity First** | Textual guideline | Enforced via "Rewrite threshold" (diff vs full rewrite), "No over-engineering" in core rules, and token optimization (lazy-load specialized rules). |
| **Surgical Changes** | Textual guideline | Backed by "Cleanup only your own mess" (Section 4), "Patch isolation" (Section 6), and specialized `patch_isolation.md` with semantic intention labeling. |
| **Goal-Driven Execution** | Textual guideline | Implemented as "Verification & Failure Budget" (Section 8) with one auto-fix, rollback, fatigue prevention. Cross-file bug fix includes reproduction step (Step 1b). |

### DotCode's Unique Additions

- **Input Triage (7 Scenarios)** – Prevents wrong assumptions by classifying ambiguity before reasoning.
- **Memory Tiering & Conflict Resolution** – Manages context priority and overrides for core violations.
- **Specialized Rules (rules.d/)** – Lazy-loaded via `--read` to save tokens, each overriding core when context matches.
- **Failure Budget & Fatigue Prevention** – Stops infinite retry loops, a common LLM failure mode.
- **Semantic Patch Isolation** – Forces one intention per diff, with labeling and rollback for patch sequences.
- **Dangerous Operations Double Confirmation** – Requires `yes` then diff review before applying.

### Why This Matters

The original `CLAUDE.md` is a static behavioral guideline. DotCode transforms it into a **runtime-enforced rule system** that actually modifies agent behavior through:

- Conditional execution paths (Path A–E)
- Quantitative thresholds (300 lines, 2 requests, 80% similarity)
- Concrete actions (ask, ABORT, split, verify, rollback)
- Override semantics (specialized > core)

This moves from "suggestion" to "governance" – critical for autonomous agents.

---

## Reference Examples

For concrete before/after examples of each principle, see `EXAMPLES.md` (provided separately). Key takeaways from those examples:

- **Hidden assumptions** (export user data) → DotCode's Trigger B and C would ask clarifying questions.
- **Over-abstraction** (discount strategy pattern) → DotCode's Simplicity First + rewrite threshold would reject it.
- **Drive-by refactoring** (empty email fix) → DotCode's Surgical Changes + cleanup rules prevent it.
- **Vague goals** ("fix authentication") → DotCode's Goal-Driven Execution forces test-first verification.

---

## Conclusion

DotCode is not just a copy of Karpathy's principles. It is a **production-ready implementation** that operationalizes those principles through a structured, token-efficient, and context-aware rule system. The principles provide the "why"; DotCode provides the "how" with concrete, enforceable rules.