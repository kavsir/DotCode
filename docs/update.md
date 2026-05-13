# AUTONOMOUS CODING AGENT ROADMAP
*Kim chỉ nam phát triển hệ thống AI Coding Runtime*

---

## 1. Tầm nhìn cuối cùng

Mục tiêu không phải `AI Chatbot` mà là `Autonomous Software Engineer` — một hệ thống có khả năng:

```
Nhận mục tiêu → Hiểu project → Lập kế hoạch → Viết code → Chạy thử → Bắt lỗi → Tự sửa → Hoàn thành task
```

---

## 2. Triết lý cốt lõi

- **Sai lầm phổ biến:** Làm nhiều agent hơn
- **Hướng đúng:** Làm runtime ổn định hơn

---

## 3. Kiến trúc phát triển

```
LLM → Runtime → Tools → Memory → Evaluation → Observability → Autonomous Loop → Multi-Agent
```

---

## 4. Thứ tự ưu tiên thật sự

| Priority | Thành phần | Vì sao |
|---|---|---|
| P0 | Single Runtime | nền móng |
| P1 | Self-Healing Loop | agent thật sự |
| P2 | Context Engineering | hiểu project |
| P3 | Evaluation | verify fix |
| P4 | Observability | debug system |
| P5 | Safety | tránh phá project |
| P6 | Multi-Agent | mở rộng |

---

## 5. Giai đoạn 1 — Foundation
*Mức độ: Beginner → Intermediate · Ưu tiên: CỰC CAO · Độ khó: TRUNG BÌNH*

**Mục tiêu:** Tạo coding agent cơ bản.

**Thành phần:**
- **LLM Layer:** DeepSeek · Aider · Prompt Rules · Diff Editing
- **Rule System** (`rules.md`): coding policy · output format · architecture behavior · patch rules
- **Project Memory** (`.system-map.md`): source of truth · module mapping · dependency tracking

**Kết quả cần đạt:** AI có thể hiểu code · sửa code nhỏ · tạo diff · đọc project map

**Sai lầm cần tránh:** prompt quá dài · rewrite nguyên file · không có project map · không kiểm soát context

---

## 6. Giai đoạn 2 — Single Agent Runtime
*Mức độ: Intermediate · Ưu tiên: CAO NHẤT · Độ khó: KHÓ*

**Mục tiêu:** Tạo runtime thật sự — đây là phần **QUAN TRỌNG NHẤT**. Runtime là hệ điều hành của Agent.

**Thành phần cần build:**
```
runtime/
├── task.py
├── states.py
├── executor.py
├── retry_manager.py
├── scheduler.py
└── context_manager.py
```

**Runtime cần quản lý:**

| Thành phần | Vai trò |
|---|---|
| task state | trạng thái |
| retries | retry |
| timeout | chống treo |
| loop detection | chống loop |
| execution flow | luồng chạy |
| checkpoints | resume |

**State Machine đề xuất:**
```
CREATED → PLANNING → CODING → RUNNING → SUCCESS
                                  ↓
                               FAILED → PATCHING → RETRYING → ABORTED
```

**Kết quả cần đạt:** AI có thể quản lý task · retry khi lỗi · chạy workflow ổn định

**Sai lầm cần tránh:** làm multi-agent quá sớm · không có state machine · không có retry logic · loop vô hạn

---

## 7. Giai đoạn 3 — Tool Ecosystem
*Mức độ: Intermediate → Advanced · Ưu tiên: RẤT CAO · Độ khó: KHÓ*

**Mục tiêu:** Cho AI khả năng hành động.

**Tool Layer:**
```
tools/
├── terminal/    ← QUAN TRỌNG NHẤT (biến AI Assistant → AI Worker)
├── editor/
├── git/
├── filesystem/
├── browser/
├── tests/
└── diagnostics/
```

**Vòng lặp cốt lõi:** `READ ERROR → ANALYZE → PATCH → RUN AGAIN`

**Kết quả cần đạt:** AI có thể chạy project · bắt terminal error · sửa lỗi · retry tự động

**Sai lầm cần tránh:** cho AI toàn quyền shell · không sandbox · không timeout · command nguy hiểm

---

## 8. Giai đoạn 4 — Context Engineering
*Mức độ: Advanced · Ưu tiên: CAO · Độ khó: RẤT KHÓ*

**Mục tiêu:** Cho AI hiểu project lớn. Đây là thứ quyết định coding quality — không phải prompt.

**Thành phần cần build:** repository map · dependency graph · symbol indexing · semantic retrieval · code summarization

```
memory/
├── retrieval/
├── embeddings/
├── symbol_graph/
└── vector_store/
```

**Kết quả cần đạt:** AI có thể tìm đúng file · hiểu dependency · retrieve context thông minh · xử lý project lớn

**Sai lầm cần tránh:** nhét cả repo vào context · retrieval không ranking · context overflow · mất consistency

---

## 9. Giai đoạn 5 — Evaluation System
*Mức độ: Advanced · Ưu tiên: CAO · Độ khó: RẤT KHÓ*

**Mục tiêu:** Verify fix thật sự hoạt động. Đây là thứ phân biệt AI toy và production AI.

**Pipeline:** `Patch → Run Tests → Lint → Type Check → Execute → Validate`

```
evaluation/
├── tests/
├── validators/
├── benchmarks/
└── regression/
```

**Kết quả cần đạt:** AI có thể tự verify patch · detect regression · reject bad fixes

**Sai lầm cần tránh:** tin vào LLM reasoning · không có benchmark · không regression testing

---

## 10. Giai đoạn 6 — Observability
*Mức độ: Advanced · Ưu tiên: TRUNG BÌNH · Độ khó: KHÓ*

**Mục tiêu:** Debug toàn bộ hệ thống agent. Không có observability = không thể debug agent.

**Cần log:** prompt · tool calls · retrieved files · patches · terminal output · token usage · latency · failures

```
observability/
├── logs/
├── traces/
├── metrics/
└── analytics/
```

**Kết quả cần đạt:** AI có thể trace workflow · debug failures · monitor runtime

**Sai lầm cần tránh:** không trace prompt · không log patch · không lưu terminal history

---

## 11. Giai đoạn 7 — Safety Layer
*Mức độ: Advanced · Ưu tiên: TRUNG BÌNH · Độ khó: KHÓ*

**Mục tiêu:** Bảo vệ project khỏi autonomous mistakes.

**Nguy cơ:** overwrite project · delete files · infinite loops · dangerous shell commands

```
safety/
├── sandbox/
├── permissions/
├── policies/
└── command_filters/
```

**Kết quả cần đạt:** AI không thể phá project · chạy command nguy hiểm · truy cập trái phép

**Sai lầm cần tránh:** cho shell unrestricted · không permission layer · không path restrictions

---

## 12. Giai đoạn 8 — Autonomous Loop
*Mức độ: Expert · Ưu tiên: RẤT CAO · Độ khó: RẤT KHÓ*

**Mục tiêu:** Cho hệ thống tự vận hành ổn định.

**Flow cuối cùng:** `Goal → Plan → Edit → Run → Analyze → Retry → Success`

**Kết quả cần đạt:** AI có thể tự hoàn thành task · tự debug · tự retry · tự optimize patch

**Sai lầm cần tránh:** autonomous quá sớm · không verification · không loop detection

---

## 13. Giai đoạn 9 — Multi-Agent System
*Mức độ: Expert · Ưu tiên: THẤP · Độ khó: CỰC KHÓ*

**QUAN TRỌNG: Không build quá sớm.** Chỉ có ý nghĩa khi runtime ổn định · retrieval tốt · evaluation tốt · observability hoàn chỉnh.

**Vai trò đề xuất:**

| Agent | Vai trò |
|---|---|
| Planner | chia task |
| Coder | sửa code |
| Runner | execute |
| Reviewer | review patch |
| Researcher | đọc docs |

**Kết quả cần đạt:** xử lý task phức tạp · parallel workflows · self-review · collaborative execution

**Sai lầm cần tránh:** fake multi-agent · roleplay agents · swarm hype · context chaos

---

## 14. Kiến trúc cuối cùng

```
USER → UI/TERMINAL → AGENT RUNTIME → TOOLS → MEMORY → EVALUATION → OBSERVABILITY → SAFETY → LLM
```

---

## 15. Kim chỉ nam phát triển

**Đừng tập trung vào:** nhiều prompt · nhiều agent · hype workflows

**Hãy tập trung vào:**
```
Runtime Stability + Context Engineering + Execution Reliability + Verification
```

---

## 16–17. Tư duy & Mục tiêu sau cùng

AI Coding System mạnh thật sự không phải `LLM mạnh hơn` mà là `Runtime tốt hơn`.

AI không chỉ "viết code" mà: **hiểu project · tự sửa lỗi · tự verify · tự retry · hoàn thành task**
