# AUTONOMOUS CODING AGENT — Project Structure

```
Agent_Code/
│
├── .aider.conf.yml               # Aider config (model, format, cache...)
├── .aiderignore                  # Files Aider không được đọc
├── .gitignore                    # Exclude runtime data & cache
├── AI.bat                        # Entry point — khởi động agent
│
├── docs/
│   ├── update.md                 # Roadmap & vision
│   ├── structure.md              # File này
│   └── architecture.md          # Kiến trúc tổng thể
│
├── agent/                        # [GĐ 1] Foundation
│   ├── rules.md                  # Coding rules cho AI
│   └── .system-map.md            # Source of truth — map toàn bộ project
│
├── runtime/                      # [GĐ 2] Single Agent Runtime
│   ├── task.py                   # Task definition & lifecycle
│   ├── states.py                 # State machine: CREATED→SUCCESS/ABORTED
│   ├── executor.py               # Chạy task, gọi tools
│   ├── retry_manager.py          # Retry logic, backoff, max attempts
│   ├── scheduler.py              # Queue & schedule tasks
│   └── context_manager.py        # Quản lý context window, file loading
│
├── tools/                        # [GĐ 3] Tool Ecosystem
│   ├── terminal/
│   │   ├── runner.py             # Chạy shell command, capture output
│   │   └── error_parser.py       # Parse stderr → structured error
│   ├── editor/
│   │   └── diff_apply.py         # Apply diff patch vào file
│   ├── git/
│   │   └── git_tool.py           # commit, branch, status
│   ├── filesystem/
│   │   └── fs_tool.py            # read, write, list, search files
│   ├── tests/
│   │   └── test_runner.py        # Chạy pytest, capture result
│   └── diagnostics/
│       └── linter.py             # Chạy flake8/ruff, trả về issues
│
├── memory/                       # [GĐ 4] Context Engineering
│   ├── retriever.py              # Tìm file liên quan theo query
│   ├── embedder.py               # Tạo vector cho code chunks
│   ├── symbol_index.py           # Index function/class names
│   ├── store.py                  # Lưu & query embeddings
│   └── .index/                   # ← gitignore — data tự sinh khi chạy
│
├── evaluation/                   # [GĐ 5] Evaluation System
│   ├── eval_runner.py            # Chạy test suite sau mỗi patch
│   ├── patch_validator.py        # Validate diff trước khi apply
│   ├── bench.py                  # Đo quality của fix
│   └── regression_check.py       # So sánh trước/sau patch
│
├── observability/                # [GĐ 6] Logging & Tracing
│   ├── tracer.py                 # Trace từng bước agent chạy
│   ├── metrics.py                # Token usage, latency, retry count
│   ├── dashboard.py              # Visualize metrics
│   └── logs/                     # ← gitignore — data tự sinh khi chạy
│
├── safety/                       # [GĐ 7] Safety Layer
│   ├── sandbox.py                # Chạy code trong môi trường isolated
│   ├── permission_check.py       # Kiểm tra quyền trước khi action
│   ├── filter.py                 # Blacklist dangerous shell commands
│   └── policies.md               # Danh sách rule an toàn bằng text
│
├── loop/                         # [GĐ 8] Autonomous Loop
│   ├── agent_loop.py             # Main loop: goal→plan→edit→run→retry
│   ├── planner.py                # Nhận goal, tạo plan
│   ├── self_healer.py            # Phát hiện lỗi, tự patch
│   └── loop_guard.py             # Phát hiện infinite loop, abort
│
└── multi_agent/                  # [GĐ 9] Multi-Agent — CHƯA BUILD
    ├── planner_agent.py
    ├── coder_agent.py
    ├── runner_agent.py
    ├── reviewer_agent.py
    └── researcher_agent.py
```

---

## Build Order

| Giai đoạn | Folder | Status |
|---|---|---|
| GĐ 1 — Foundation | `agent/` | ✅ Đang dùng |
| GĐ 2 — Runtime | `runtime/` | 🔨 Build tiếp theo |
| GĐ 3 — Tools | `tools/` | ⏳ |
| GĐ 4 — Context | `memory/` | ⏳ |
| GĐ 5 — Evaluation | `evaluation/` | ⏳ |
| GĐ 6 — Observability | `observability/` | ⏳ |
| GĐ 7 — Safety | `safety/` | ⏳ |
| GĐ 8 — Autonomous Loop | `loop/` | ⏳ |
| GĐ 9 — Multi-Agent | `multi_agent/` | 🚫 Chưa build |

---

## Nguyên tắc cấu trúc

- Mỗi folder = 1 giai đoạn, độc lập với nhau
- Chỉ commit code & config — không commit runtime data
- `memory/.index/` và `observability/logs/` tự sinh khi chạy, agent tự rebuild nếu xóa
- Flatten sub-folder cho đến khi file thực sự nhiều mới tách

---

## .gitignore

```
# Runtime data
memory/.index/
observability/logs/

# Aider per-machine
.aider.input.history*
.aider.chat.history*
.aider.tags.cache.v3/

# Python
__pycache__/
*.pyc
.venv/
```
