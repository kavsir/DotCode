"""
Model Router - Tự động chọn LLM dựa trên độ phức tạp của task.
Hỗ trợ DeepSeek V4 (flash/pro), GPT-4o-mini, và local models.
Bao gồm SafeModelRouter với cơ chế an toàn khi chuyển model.
"""

import os
import re
from enum import Enum
from typing import Optional, Tuple


class TaskComplexity(Enum):
    SIMPLE = "simple"  # Format code, thêm comment, sửa lỗi nhỏ
    MODERATE = "moderate"  # Thêm function, refactor nhỏ
    COMPLEX = "complex"  # Multi-file changes, architect, debug sâu


class ModelRouter:
    def __init__(self):
        # Cấu hình model cho từng mức độ phức tạp
        self.model_map = {
            TaskComplexity.SIMPLE: os.getenv("DOTCODE_MODEL_SIMPLE", "deepseek/deepseek-v4-flash"),
            TaskComplexity.MODERATE: os.getenv("DOTCODE_MODEL_MODERATE", "deepseek/deepseek-chat"),
            TaskComplexity.COMPLEX: os.getenv("DOTCODE_MODEL_COMPLEX", "deepseek/deepseek-v4-pro"),
        }

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
        complexity = self.classify_task(message, context_tokens)
        return self.model_map[complexity]

    def get_complexity(self, message: str, context_tokens: int = 0) -> TaskComplexity:
        return self.classify_task(message, context_tokens)

    def get_all_models(self) -> dict:
        return {k.value: v for k, v in self.model_map.items()}


class SafeModelRouter(ModelRouter):
    """
    Model Router an toàn, chỉ chuyển model trong điều kiện phù hợp.
    """

    def __init__(self):
        super().__init__()
        self.current_model = None
        self.cache_warmed = False

    def should_switch_model(self, intent: str, context_tokens: int) -> bool:
        if intent == "command":
            return False

        if self.cache_warmed:
            return False

        if context_tokens > 2000:
            return False

        return True

    def get_safe_model(self, message: str, intent: str, context_tokens: int = 0) -> str:
        if intent in ("question", "search") and context_tokens < 10000:
            return self.model_map[TaskComplexity.SIMPLE]

        if self.should_switch_model(intent, context_tokens):
            complexity = self.classify_task(message, context_tokens)
            selected = self.model_map[complexity]
        else:
            selected = self.model_map[TaskComplexity.COMPLEX]

        self.current_model = selected
        return selected
