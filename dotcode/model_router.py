"""
Model Router - Tự động chọn LLM dựa trên độ phức tạp của task.
Hỗ trợ đa nhà cung cấp (DeepSeek, OpenAI, Anthropic, Gemini, Groq, Ollama).
Bao gồm SafeModelRouter với cơ chế an toàn khi chuyển model.
"""

import re
from enum import Enum
from typing import Optional

from dotcode.llm_client import DotCodeLLM


class TaskComplexity(Enum):
    SIMPLE = "simple"  # Format code, thêm comment, sửa lỗi nhỏ
    MODERATE = "moderate"  # Thêm function, refactor nhỏ
    COMPLEX = "complex"  # Multi-file changes, architect, debug sâu


# Mapping từ TaskComplexity sang LLM tier
COMPLEXITY_TO_TIER = {
    TaskComplexity.SIMPLE: "fast",
    TaskComplexity.MODERATE: "main",
    TaskComplexity.COMPLEX: "strong",
}


class ModelRouter:
    def __init__(self):
        self.llm = DotCodeLLM.get_instance()

        # Ngưỡng token để phân loại
        self.simple_max_tokens = 500
        self.moderate_max_tokens = 2000

    def classify_task(self, message: str, context_tokens: int = 0) -> TaskComplexity:
        message_lower = message.lower()

        complex_keywords = [
            "refactor",
            "architect",
            "multi-file",
            "debug sâu",
            "tái cấu trúc",
            "kiến trúc",
            "nhiều file",
            "gỡ lỗi sâu",
            "redesign",
            "restructure",
            "overhaul",
            "migrate",
            "tối ưu hóa toàn bộ",
            "viết lại",
            "rewrite",
        ]
        for keyword in complex_keywords:
            if keyword in message_lower:
                return TaskComplexity.COMPLEX

        simple_keywords = [
            "comment",
            "format",
            "add docstring",
            "add type hint",
            "thêm comment",
            "định dạng",
            "thêm docstring",
            "thêm type hint",
            "rename variable",
            "đổi tên biến",
            "sửa lỗi chính tả",
            "fix typo",
            "thêm dòng trống",
            "sắp xếp import",
            "sort imports",
        ]
        for keyword in simple_keywords:
            if keyword in message_lower:
                return TaskComplexity.SIMPLE

        if context_tokens > self.moderate_max_tokens:
            return TaskComplexity.COMPLEX
        elif context_tokens > self.simple_max_tokens:
            return TaskComplexity.MODERATE
        else:
            if len(message.split()) < 20:
                return TaskComplexity.SIMPLE
            return TaskComplexity.MODERATE

    def get_model_for_task(self, message: str, context_tokens: int = 0) -> str:
        """Get model name based on task complexity. Respects auto/manual mode."""
        if self.llm.mode == "manual":
            return self.llm.get_model()

        complexity = self.classify_task(message, context_tokens)
        tier = COMPLEXITY_TO_TIER[complexity]
        return self.llm.get_model(tier)

    def get_complexity(self, message: str, context_tokens: int = 0) -> TaskComplexity:
        return self.classify_task(message, context_tokens)

    def get_all_models(self) -> dict:
        """Return current model mapping for all tiers."""
        return {
            "fast": self.llm.get_model("fast"),
            "main": self.llm.get_model("main"),
            "strong": self.llm.get_model("strong"),
        }


class SafeModelRouter(ModelRouter):
    """
    Model Router an toàn, chỉ chuyển model trong điều kiện phù hợp.
    """

    def __init__(self):
        super().__init__()
        self.current_model = None
        self.cache_warmed = False

    def should_switch_model(self, intent: str, context_tokens: int) -> bool:
        # Manual mode: never auto-switch
        if self.llm.mode == "manual":
            return False

        if intent == "command":
            return False

        if self.cache_warmed:
            return False

        if context_tokens > 2000:
            return False

        return True

    def get_safe_model(self, message: str, intent: str, context_tokens: int = 0) -> str:
        """Get the appropriate model, respecting safety constraints and mode."""
        # Manual mode: always use user's chosen model
        if self.llm.mode == "manual":
            self.current_model = self.llm.get_model()
            return self.current_model

        # Auto mode logic
        if intent in ("question", "search") and context_tokens < 10000:
            return self.llm.get_model("fast")

        if self.should_switch_model(intent, context_tokens):
            complexity = self.classify_task(message, context_tokens)
            tier = COMPLEXITY_TO_TIER[complexity]
            selected = self.llm.get_model(tier)
        else:
            selected = self.llm.get_model("strong")

        self.current_model = selected
        return selected
