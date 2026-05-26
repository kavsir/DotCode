import re

# Các mẫu câu hỏi phổ biến trong tiếng Việt và tiếng Anh
QUESTION_PATTERNS = [
    # Tiếng Việt
    r"(là gì|như thế nào|tại sao|khi nào|ở đâu|ai là|hàm nào|class nào|file nào)",
    r"(có bao nhiêu|những (gì|hàm|class|file|module|thư viện))",
    r"(giải thích|mô tả|tóm tắt|phân tích|đánh giá)",
    r"(hỏi|thắc mắc|cho hỏi)",
    r"\b(what|how|why|when|where|who|which|explain|describe|summarize|analyze)\b",
    r"\b(is|are|does|do|can|could|would|should|will)\b.*\?$",
    # Câu hỏi kết thúc bằng dấu hỏi
    r"\?$",
    r"(\bhàm\b.*\bgọi\b.*\bnào\b)",
    r"(\bfile\b.*\blàm gì\b)",
]

def classify_intent(message: str) -> str:
    """Phân loại ý định của người dùng: 'ask' hoặc 'edit'."""
    message_lower = message.lower().strip()
    
    # Kiểm tra nếu message giống câu hỏi
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, message_lower):
            return "ask"
    
    # Mặc định là yêu cầu sửa code
    return "edit"