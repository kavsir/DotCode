"""
Intent Agent - Sử dụng LLM để phân loại ý định người dùng.
Linh hoạt với mọi ngôn ngữ, không phụ thuộc regex cứng.
"""

import re
from typing import Tuple

from dotcode.llm_client import DotCodeLLM


class IntentAgent:
    def __init__(self, model_name: str = "deepseek-chat"):
        self.model_name = model_name

    def is_ambiguous(self, text: str) -> bool:
        """Phát hiện input quá ngắn hoặc không rõ ràng."""
        if not text or not text.strip():
            return True
        return False

    def classify(self, text: str) -> Tuple[str, float]:
        """
        Phân loại intent dùng LLM (chính) + rule-based fallback.

        Returns:
            Tuple[str, float]: (intent, confidence)
        """
        if not text:
            return "ambiguous", 1.0

        # Kiểm tra input mơ hồ
        if self.is_ambiguous(text):
            return "ambiguous", 1.0

        # Gọi LLM để phân loại
        llm_intent, llm_confidence = self._llm_classify(text)
        if llm_intent != "unknown" and llm_confidence > 0.5:
            return llm_intent, llm_confidence

        # Fallback về rule-based nếu LLM không khả dụng
        return self._rule_based_fallback(text)

    def _llm_classify(self, text: str) -> Tuple[str, float]:
        """Dùng LLM để phân loại intent."""
        prompt = f"""Classify the user input into exactly one of these intents:
- question: asking about code (what, why, how, explain, describe...)
- search: searching for code (find, locate, list, search, where...)
- command: requesting a code change (add, fix, create, refactor, update...)
- architecture: asking about project structure (modules, architecture, overview, components...)
- ambiguous: too short or unclear to classify

User input: "{text}"

Respond with exactly one word (question, search, command, architecture, ambiguous)."""

        try:
            llm = DotCodeLLM.get_instance()
            response_text = llm.complete(
                prompt=prompt,
                tier="fast",
                max_tokens=10,
                temperature=0.0,
            )
            if response_text:
                intent = response_text.strip().lower()
                # Chuẩn hóa intent
                valid_intents = ["question", "search", "command", "architecture", "ambiguous"]
                if intent in valid_intents:
                    return intent, 0.85  # LLM có độ tin cậy cao
        except Exception:
            pass

        return "unknown", 0.0

    def _rule_based_fallback(self, text: str) -> Tuple[str, float]:
        """Fallback regex khi LLM không khả dụng."""
        text_lower = text.lower().strip()

        # Pattern rõ ràng cho search
        if re.match(r"^\s*(tìm|search|find|liệt\s+kê|list|show|tìm\s+kiếm)\s", text_lower):
            return "search", 0.8

        # Pattern rõ ràng cho command
        if re.match(
            r"^\s*(thêm|add|tạo|create|sửa|fix|đổi|rename|delete|xóa|update|cập\s+nhật)\s",
            text_lower,
        ):
            return "command", 0.8

        # Pattern cho câu hỏi kiến trúc
        if re.match(
            r"^\s*có\s+(những|bao\s+nhiêu)\s+(module|phần|thành\s+phần|file|class|function)",
            text_lower,
        ):
            return "question", 0.8

        # Pattern cho câu hỏi "X có liên quan đến Y không?"
        if re.search(r"có\s+liên\s+quan\s+(đến|tới|với)", text_lower):
            return "search", 0.8

        # Pattern cho câu hỏi
        if text.rstrip().endswith("?") or re.match(
            (
                r"^(làm sao|tại sao|giải"
                r" thích|how|why|what|explain|hàm\s+\w+\s+làm\s+gì|class\s+\w+\s+có\s+tác\s+dụng|cho\s+tôi\s+biết)"
            ),
            text_lower,
        ):
            return "question", 0.7

        # Pattern cho câu hỏi "hàm X làm gì?" hoặc "function X làm gì?"
        if re.search(
            r"(hàm|function|method|class)\s+\w+\s+(làm\s+gì|có\s+tác\s+dụng\s+gì|dùng\s+để\s+làm\s+gì)",
            text_lower,
        ):
            return "question", 0.8

        # Pattern cho câu hỏi mở về dự án (bắt đầu bằng "có những", "liệt kê")
        if re.match(r"^\s*(có\s+những|liệt\s+kê|kể\s+tên|cho\s+biết|nêu\s+ra)", text_lower):
            return "question", 0.8

        # Mặc định: nếu input dài hơn 5 từ → question
        if len(text.strip().split()) > 5:
            return "question", 0.5

        if re.search(
            r"(luồng|xử\s+lý|quy\s+trình|flow|process|cách\s+thức|how\s+does|how\s+do)",
            text_lower,
        ):
            return "question", 0.8

        return "command", 0.5
