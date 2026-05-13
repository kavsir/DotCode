# DotCode

Autonomous Coding Agent — hệ thống AI tự động hiểu code, sửa lỗi, verify và hoàn thành task mà không cần can thiệp thủ công.

> **Trạng thái hiện tại:** Giai đoạn 1 — Foundation

---

## Yêu cầu

- Python 3.11+
- [Aider](https://aider.chat) (`pip install aider-chat`)
- DeepSeek API Key — lấy tại [platform.deepseek.com](https://platform.deepseek.com/api_keys)

---

## Cài đặt

**1. Clone project**
```bash
https://github.com/kavsir/DotCode.git
```

**2. Set API Key** *(1 lần duy nhất)*
```bash
setx DEEPSEEK_API_KEY sk-xxxxxxxxxxxxxxxx
```

**3. Chạy installer** *(1 lần duy nhất)*
```
install.bat
```

Installer tự động kiểm tra Python, cài Aider nếu chưa có, và thêm DotCode vào PATH.

---

## Sử dụng

Mở terminal tại bất kỳ project nào, gõ:
```
AI
```

Agent khởi động, đọc rules từ `agent/rules.md`, lưu history tại thư mục project đang làm việc.

---

## Cấu trúc

```
DotCode/
├── agent/                  # [GĐ 1] Foundation — đang active
│   ├── rules.md            # Coding rules cho AI
│   └── .system-map.md      # Source of truth
├── docs/                   # Tài liệu hệ thống
│   ├── update.md           # Roadmap
│   └── structure.md        # Cấu trúc thư mục
├── runtime/                # [GĐ 2] Agent Runtime
├── tools/                  # [GĐ 3] Tool Ecosystem
├── memory/                 # [GĐ 4] Context Engineering
├── evaluation/             # [GĐ 5] Evaluation System
├── observability/          # [GĐ 6] Logging & Tracing
├── safety/                 # [GĐ 7] Safety Layer
├── loop/                   # [GĐ 8] Autonomous Loop
└── multi_agent/            # [GĐ 9] Multi-Agent
```

---

## Roadmap

| Giai đoạn | Nội dung | Status |
|---|---|---|
| GĐ 1 | Foundation — rules, system map | ✅ Active |
| GĐ 2 | Single Agent Runtime | 🔨 Next |
| GĐ 3 | Tool Ecosystem | ⏳ |
| GĐ 4 | Context Engineering | ⏳ |
| GĐ 5 | Evaluation System | ⏳ |
| GĐ 6 | Observability | ⏳ |
| GĐ 7 | Safety Layer | ⏳ |
| GĐ 8 | Autonomous Loop | ⏳ |
| GĐ 9 | Multi-Agent | 🚫 Build last |

Chi tiết từng giai đoạn xem tại [`docs/update.md`](docs/update.md).

---

## License

MIT
