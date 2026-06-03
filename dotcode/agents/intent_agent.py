"""
Intent Agent - Sử dụng embedding đa ngữ để phân loại ý định người dùng.
Không phụ thuộc regex cứng, hoạt động với mọi ngôn ngữ.
"""

import os
import re
import numpy as np
from typing import Tuple, Optional
from sentence_transformers import SentenceTransformer
from huggingface_hub import login

class IntentAgent:
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        hf_token = os.getenv("HF_TOKEN")
        
        # Đăng nhập Hugging Face trước khi tạo model
        if hf_token:
            try:
                login(token=hf_token, add_to_git_credential=False)
            except Exception:
                pass
        
        # Tạo model
        self._model = SentenceTransformer(
            self.model_name,
            token=hf_token,
            trust_remote_code=True
        )
        self._prototypes = {
            "question": [
                "hàm này làm gì",
                "giải thích chức năng của function",
                "class này có tác dụng gì",
                "tại sao lại dùng cách này",
                "làm sao để sử dụng",
                "có bao nhiêu method",
                "cho tôi biết về",
                "what does this function do",
                "explain how this works",
                "tell me about this class",
                "how many functions are there",
                "what is the purpose of",
                "describe the logic of",
                "cách hoạt động của",
                "mô tả chức năng của",
                "hàm X làm gì",
            ],
            "search": [
                "tìm hàm",
                "tìm tất cả các class",
                "search for function",
                "find all references",
                "where is this defined",
                "liệt kê tất cả",
                "list all functions",
                "show me the definition",
                "tìm kiếm trong codebase",
                "find occurrences of",
                "locate the implementation",
                "tìm những file liên quan",
            ],
            "command": [
                "thêm docstring cho class",
                "đổi tên hàm",
                "tạo file mới",
                "sửa lỗi",
                "tối ưu code",
                "refactor this function",
                "add a new method",
                "delete the file",
                "update the implementation",
                "viết unit test cho",
                "cập nhật logic xử lý",
                "thay đổi kiểu dữ liệu",
                "merge two functions",
            ],
            "ambiguous": [
                "book",
                "lend",
                "sửa",
                "xóa",
                "file",
                "code",
                "hàm",
                "class",
            ],
        }
        
        self._prototype_embeddings = None
    
    @property
    def model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self._model
    
    def _ensure_prototypes(self):
        """Tạo embedding cho tất cả prototype nếu chưa có."""
        if self._prototype_embeddings is not None:
            return
        
        self._prototype_embeddings = {}
        for intent, examples in self._prototypes.items():
            embeddings = self.model.encode(examples, normalize_embeddings=True)
            self._prototype_embeddings[intent] = embeddings
    
    def _semantic_similarity(self, text: str, intent: str) -> float:
        """Tính độ tương đồng ngữ nghĩa giữa text và prototype của intent."""
        self._ensure_prototypes()
        
        # Encode input
        input_emb = self.model.encode([text], normalize_embeddings=True)[0]
        
        # Tính cosine similarity với tất cả prototype của intent
        prototypes = self._prototype_embeddings[intent]
        similarities = np.dot(prototypes, input_emb)  # Đã normalize nên dot = cosine
        
        return float(similarities.max())
    
    def is_ambiguous(self, text: str) -> bool:
        """Phát hiện input quá ngắn hoặc không rõ ràng."""
        if not text:
            return True
        
        words = text.strip().split()
        
        # Input quá ngắn (1-2 từ) và không có từ khóa hỏi → ambiguous
        if len(words) <= 2:
            question_indicators = [
                "?", "ai", "gì", "nào", "sao", "đâu", "làm sao", "tại sao",
                "what", "how", "why", "where", "when", "which", "who",
                "tìm", "kiếm", "search", "find", "list", "show", "liệt kê",
                "thêm", "add", "tạo", "create", "sửa", "fix", "đổi", "xóa"
            ]
            text_lower = text.lower()
            has_indicator = any(indicator in text_lower for indicator in question_indicators)
            
            if not has_indicator:
                return True
        
        return False
    
    def classify(self, text: str, use_embedding: bool = True, use_llm: bool = True) -> Tuple[str, float]:
        """
        Phân loại intent dùng embedding + LLM + rule-based.
        
        Returns:
            Tuple[str, float]: (intent, confidence)
        """
        if not text:
            return "ambiguous", 1.0
        
        # Kiểm tra input mơ hồ
        if self.is_ambiguous(text):
            return "ambiguous", 1.0
        
        # Tầng 1: Embedding similarity (nhanh, rẻ)
        if use_embedding:
            try:
                scores = {}
                for intent in self._prototypes:
                    scores[intent] = self._semantic_similarity(text, intent)
                
                best_intent = max(scores, key=scores.get)
                best_score = scores[best_intent]
                
                if best_score > 0.7:
                    return best_intent, best_score
                
                # Nếu embedding không tự tin và input ngắn → ambiguous
                if best_score < 0.65 and len(text.strip().split()) <= 3:
                    return "ambiguous", 0.5
                
                # Nếu embedding khá tự tin → trả về
                if best_score > 0.5:
                    return best_intent, best_score
            except Exception:
                pass
        
        # Tầng 2: LLM classification (chính xác, linh hoạt)
        if use_llm:
            llm_intent, llm_confidence = self._llm_classify(text)
            if llm_intent != "unknown" and llm_confidence > 0.5:
                return llm_intent, llm_confidence
        
        # Tầng 3: Rule-based fallback
        return self._rule_based_fallback(text)
    
    def _rule_based_fallback(self, text: str) -> Tuple[str, float]:
        """Fallback regex khi embedding không khả dụng."""
        text_lower = text.lower().strip()
        
        # Pattern rõ ràng cho search
        if re.match(r"^\s*(tìm|search|find|liệt\s+kê|list|show)\s", text_lower):
            return "search", 0.8
        
        # Pattern rõ ràng cho command
        if re.match(r"^\s*(thêm|add|tạo|create|sửa|fix|đổi|rename|delete|xóa|update)\s", text_lower):
            return "command", 0.8
        
        # Pattern cho question
        if text.rstrip().endswith("?") or re.match(r"^(làm sao|tại sao|giải thích|how|why|what|explain)", text_lower):
            return "question", 0.7
        
        # Mặc định: command (giữ nguyên hành vi Aider)
        return "command", 0.5
    
    def _llm_classify(self, text: str) -> Tuple[str, float]:
        """Dùng LLM để phân loại intent khi embedding không tự tin."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return "unknown", 0.0
        
        prompt = f"""Classify the user input into one of these intents:
    - question: asking about code (what, why, how, explain, describe...)
    - search: searching for code (find, locate, list, search, where...)
    - command: requesting a code change (add, fix, create, refactor, update...)
    - architecture: asking about project structure (modules, architecture, overview, components...)
    - ambiguous: too short or unclear to classify

    User input: "{text}"

    Respond with exactly one word (question, search, command, architecture, ambiguous)."""
        
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0.0
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                intent = data["choices"][0]["message"]["content"].strip().lower()
                # Chuẩn hóa intent
                valid_intents = ["question", "search", "command", "architecture", "ambiguous"]
                if intent in valid_intents:
                    return intent, 0.85  # LLM có độ tin cậy cao
        except Exception:
            pass
        
        return "unknown", 0.0