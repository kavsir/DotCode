"""
Context Pruner - Cắt giảm ngữ cảnh không cần thiết trước khi gửi LLM.
Giúp giảm token đầu vào và chi phí API.
"""

import re
from typing import Dict, List


class ContextPruner:
    def __init__(self, max_input_tokens: int = 8000, keep_last_n: int = 3):
        self.max_input_tokens = max_input_tokens
        self.keep_last_n = keep_last_n  # Luôn giữ N tin nhắn cuối cùng

    def prune_messages(self, messages: List[Dict], current_query: str) -> List[Dict]:
        """
        Cắt giảm lịch sử hội thoại, giữ lại những tin nhắn liên quan nhất.

        Args:
            messages: Danh sách messages hiện tại
            current_query: Câu hỏi/yêu cầu hiện tại của người dùng

        Returns:
            Danh sách messages đã được cắt giảm
        """
        if len(messages) <= self.keep_last_n:
            return messages

        # Trích xuất từ khóa từ câu hỏi hiện tại
        keywords = set(re.findall(r"\w+", current_query.lower()))

        # Tính điểm liên quan cho từng message
        scored_messages = []
        for i, msg in enumerate(messages[: -self.keep_last_n]):  # Không tính N tin cuối
            content = msg.get("content", "").lower()
            score = sum(1 for kw in keywords if kw in content)
            scored_messages.append((i, score, msg))

        # Sắp xếp theo điểm liên quan giảm dần
        scored_messages.sort(key=lambda x: x[1], reverse=True)

        # Giữ lại các messages có điểm cao nhất, cộng với N tin cuối
        kept_indices = set()
        for i, score, msg in scored_messages[: max(5, self.keep_last_n)]:
            kept_indices.add(i)

        # Luôn giữ N tin cuối cùng
        for i in range(len(messages) - self.keep_last_n, len(messages)):
            kept_indices.add(i)

        # Tạo danh sách messages đã cắt giảm
        pruned = [msg for i, msg in enumerate(messages) if i in kept_indices]

        return pruned

    def estimate_tokens(self, messages: List[Dict]) -> int:
        """Ước lượng số token của danh sách messages."""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return int(total_chars * 0.4)  # Ước lượng thô: 1 token ≈ 2.5 ký tự
