"""
Context Pruner - Cắt giảm ngữ cảnh không cần thiết trước khi gửi LLM.
Sử dụng Semantic Pruning (Vector Search) để giữ lại những tin nhắn liên quan nhất
và `litellm.token_counter` để tính toán chính xác token.
"""

import math
from typing import Dict, List, Optional
import numpy as np
import litellm
import logging

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class ContextPruner:
    def __init__(self, max_input_tokens: int = 8000, keep_last_n: int = 3, embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Khởi tạo Semantic Context Pruner.
        Args:
            max_input_tokens: Giới hạn token tối đa (chưa được áp dụng triệt để ở version này, nhưng dùng để strict trim).
            keep_last_n: Luôn giữ lại N tin nhắn cuối cùng để đảm bảo tính liền mạch.
            embedding_model: Model dùng để nhúng (embed) các đoạn chat. Mặc định là model nhỏ siêu tốc.
        """
        self.max_input_tokens = max_input_tokens
        self.keep_last_n = keep_last_n
        self.model_name = embedding_model
        
        self._embedder = None
        self.logger = logging.getLogger(__name__)

    def _get_embedder(self):
        """Tải mô hình embedding dạng lazy-load để không làm chậm lúc khởi động."""
        if not HAS_SENTENCE_TRANSFORMERS:
            return None
        
        if self._embedder is None:
            self.logger.info(f"Loading semantic pruner model: {self.model_name}...")
            # Tắt thanh tiến trình của transformers nếu cần
            import os
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            from dotcode.llm_client import HybridEmbedder
            self._embedder = HybridEmbedder(self.model_name)
            self.logger.info("Semantic pruner model loaded.")
        return self._embedder

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Tính toán khoảng cách Cosine Similarity giữa 2 vector."""
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def prune_messages(self, messages: List[Dict], current_query: str) -> List[Dict]:
        """
        Cắt giảm lịch sử hội thoại bằng phương pháp so khớp ngữ nghĩa.
        
        Quy trình:
        1. Nếu tin nhắn ít hơn keep_last_n -> Giữ nguyên.
        2. Nếu thiếu thư viện nhúng -> Fallback về cắt theo token (strict sliding window).
        3. Embed câu hỏi hiện tại và các tin nhắn cũ.
        4. Tính Cosine Similarity, chọn top K tin nhắn cao điểm nhất + N tin nhắn cuối.
        """
        if len(messages) <= self.keep_last_n:
            return messages

        embedder = self._get_embedder()
        
        # --- FALLBACK: Nếu không có thư viện, dùng sliding window cơ bản ---
        if embedder is None:
            self.logger.warning("sentence_transformers not found. Using strict sliding window fallback.")
            return messages[-self.keep_last_n:]

        # --- SEMANTIC PRUNING ---
        try:
            # 1. Embed current query
            query_emb = embedder.encode(current_query)

            # 2. Embed all historical messages (except the last N)
            scored_messages = []
            historical_msgs = messages[:-self.keep_last_n]
            
            for i, msg in enumerate(historical_msgs):
                # Gộp role và content để tăng ngữ cảnh
                content = msg.get("content", "").strip()
                if not content:
                    continue
                
                # Chỉ cắt 500 ký tự đầu tiên để embed (tránh tốn thời gian cho mã nguồn dài)
                snippet = content[:500] 
                msg_emb = embedder.encode(snippet)
                
                score = self._cosine_similarity(query_emb, msg_emb)
                
                # Ưu tiên tin nhắn gần đây hơn một chút (Time-weighted decay)
                # Công thức: boost nhẹ theo index, tin nhắn càng gần hiện tại càng có lợi
                time_boost = (i / len(historical_msgs)) * 0.1 
                final_score = score + time_boost
                
                scored_messages.append((i, final_score, msg))

            # 3. Sắp xếp theo điểm liên quan giảm dần
            scored_messages.sort(key=lambda x: x[1], reverse=True)

            # 4. Giữ lại top messages (tối đa 5 tin nhắn liên quan nhất từ quá khứ)
            kept_indices = set()
            for i, score, msg in scored_messages[: max(5, self.keep_last_n)]:
                kept_indices.add(i)

            # Luôn giữ N tin nhắn cuối cùng (tính từ toàn bộ danh sách)
            for i in range(len(messages) - self.keep_last_n, len(messages)):
                kept_indices.add(i)

            # 5. Xây dựng danh sách pruned dựa trên index gốc để giữ nguyên thứ tự thời gian
            pruned = [msg for i, msg in enumerate(messages) if i in kept_indices]

            self.logger.debug(f"Semantic Pruner: Pruned from {len(messages)} to {len(pruned)} messages.")
            return pruned

        except Exception as e:
            self.logger.error(f"Semantic pruning failed: {str(e)}. Falling back to simple slide.")
            return messages[-self.keep_last_n:]

    def estimate_tokens(self, messages: List[Dict], model: str = "gpt-4o-mini") -> int:
        """
        Sử dụng litellm để đếm số token chính xác thay vì ước lượng thô bằng ký tự.
        Fallback về ước lượng ký tự nếu litellm báo lỗi (VD: thiếu thư viện tiktoken).
        """
        try:
            # litellm token counter tự động xử lý list[dict]
            return litellm.token_counter(model=model, messages=messages)
        except Exception as e:
            self.logger.warning(f"litellm.token_counter failed ({e}), falling back to rough estimation.")
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            return int(total_chars / 3.5)  # 1 token ≈ 3.5 ký tự (tiếng Anh và Code)
