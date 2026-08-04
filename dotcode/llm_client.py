"""
DotCode LLM Client - Centralized LLM gateway for all DotCode modules.
Uses litellm to support 100+ LLM providers with a single unified interface.
"""

import os
import threading
from typing import Optional, Dict, List, Tuple

import litellm


# ===== Provider Configuration =====
# Ordered by priority: first available key wins in auto-detect mode
PROVIDER_CONFIGS = [
    {
        "name": "deepseek",
        "env_key": "DEEPSEEK_API_KEY",
        "api_base": "https://api.deepseek.com",
        "models": {
            "fast": "openai/deepseek-v4-flash",
            "main": "openai/deepseek-v4-flash",
            "strong": "openai/deepseek-v4-pro",
        },
        "extra_body": {"thinking": {"type": "enabled"}},
        "reasoning_effort": "high",
    },
]

# Ollama fallback (no API key needed)
OLLAMA_CONFIG = {
    "name": "ollama",
    "env_key": None,
    "models": {
        "fast": "ollama/llama3.1:8b",
        "main": "ollama/llama3.1:8b",
        "strong": "ollama/llama3.1:8b",
    },
}


class DotCodeLLM:
    """
    Centralized LLM client for DotCode.

    Modes:
    - auto:   System auto-detects the best available provider and selects
              models based on task complexity (via ModelRouter).
    - manual: User explicitly sets a model name. All requests use that model.

    Usage:
        llm = DotCodeLLM.get_instance()
        response = llm.complete("Classify this intent: ...")
        response = llm.complete("Summarize this code", tier="strong")
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._mode = "auto"  # "auto" or "manual"
        self._manual_model: Optional[str] = None
        self._provider: Optional[Dict] = None
        self._available_providers: List[Dict] = []

        # Suppress litellm verbose logging and drop unsupported params automatically
        litellm.suppress_debug_info = True
        litellm.drop_params = True

        # Detect available providers
        self._detect_providers()

    @classmethod
    def get_instance(cls) -> "DotCodeLLM":
        """Singleton access."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None

    # ===== Provider Detection =====

    def _detect_providers(self):
        """Scan environment for available API keys."""
        self._available_providers = []

        for config in PROVIDER_CONFIGS:
            key = os.getenv(config["env_key"], "")
            if key and key.strip():
                self._available_providers.append(config)

        # Always add Ollama as last fallback
        self._available_providers.append(OLLAMA_CONFIG)

        # Primary provider = first available
        self._provider = self._available_providers[0] if self._available_providers else OLLAMA_CONFIG

    def refresh_providers(self):
        """Re-scan environment variables (call after user sets new keys)."""
        self._detect_providers()

    # ===== Mode Control =====

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        """Switch between 'auto' and 'manual' mode."""
        if mode not in ("auto", "manual"):
            raise ValueError(f"Invalid mode: {mode}. Use 'auto' or 'manual'.")
        self._mode = mode

    def set_manual_model(self, model_name: str):
        """Set a specific model for manual mode. Automatically switches to manual mode."""
        self._manual_model = model_name
        self._mode = "manual"

    def set_auto_mode(self):
        """Switch back to auto mode."""
        self._mode = "auto"
        self._manual_model = None

    # ===== Model Resolution =====

    @property
    def provider_name(self) -> str:
        """Current primary provider name."""
        return self._provider["name"] if self._provider else "ollama"

    @property
    def available_providers(self) -> List[str]:
        """List of detected provider names."""
        return [p["name"] for p in self._available_providers]

    def get_model(self, tier: str = "fast") -> str:
        """
        Resolve the model name to use.

        Args:
            tier: "fast" (cheap/quick), "main" (balanced), "strong" (most capable)

        Returns:
            Model name string compatible with litellm.
        """
        if self._mode == "manual" and self._manual_model:
            return self._manual_model

        # Environment variable overrides (DOTCODE_MODEL_SIMPLE, MODERATE, COMPLEX)
        env_overrides = {
            "fast": os.getenv("DOTCODE_MODEL_SIMPLE"),
            "main": os.getenv("DOTCODE_MODEL_MODERATE"),
            "strong": os.getenv("DOTCODE_MODEL_COMPLEX"),
        }
        if tier in env_overrides and env_overrides[tier]:
            return env_overrides[tier]

        # Auto mode: use provider's tier mapping
        if tier not in ("fast", "main", "strong"):
            tier = "fast"

        return self._provider["models"].get(tier, self._provider["models"]["fast"])

    # ===== Core Completion =====

    def complete(
        self,
        prompt: str,
        tier: str = "fast",
        model: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.0,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a completion request to the LLM.

        This is the ONLY function that should be used for LLM calls across
        all DotCode modules (intent_agent, dst, graphrag, etc.).

        Args:
            prompt: The user/task prompt.
            tier: Model tier ("fast", "main", "strong"). Ignored in manual mode.
            model: Override model name (ignores tier and mode).
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.
            system_prompt: Optional system prompt.

        Returns:
            The LLM response text, or empty string on failure.
        """
        resolved_model = model if model else self.get_model(tier)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        extra_kwargs = {}
        if self._provider:
            if "api_base" in self._provider:
                extra_kwargs["api_base"] = self._provider["api_base"]
            if "extra_body" in self._provider:
                extra_kwargs["extra_body"] = self._provider["extra_body"]
            if "reasoning_effort" in self._provider:
                extra_kwargs["reasoning_effort"] = self._provider["reasoning_effort"]
            env_key = self._provider.get("env_key")
            if env_key and os.getenv(env_key):
                extra_kwargs["api_key"] = os.getenv(env_key)

        # For reasoning models (e.g. deepseek-v4-pro / flash), ensure max_tokens allows thinking + response
        if "deepseek" in resolved_model or "reasoning" in resolved_model:
            max_tokens = max(max_tokens, 800)

        try:
            response = litellm.completion(
                model=resolved_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **extra_kwargs,
            )
            msg = response.choices[0].message
            content = (msg.content or "").strip()
            if not content and hasattr(msg, "reasoning_content") and msg.reasoning_content:
                content = msg.reasoning_content.strip()
            return content
        except Exception as e:
            # If the selected model fails, try fallback providers
            if not model:  # Don't fallback if user explicitly chose a model
                return self._fallback_complete(messages, max_tokens, temperature, resolved_model)
            return ""

    def _fallback_complete(
        self,
        messages: list,
        max_tokens: int,
        temperature: float,
        failed_model: str,
    ) -> str:
        """Try other available providers if the primary one fails."""
        for provider in self._available_providers:
            fallback_model = provider["models"]["fast"]
            if fallback_model == failed_model:
                continue
            try:
                fallback_kwargs = {}
                if "api_base" in provider:
                    fallback_kwargs["api_base"] = provider["api_base"]
                if "extra_body" in provider:
                    fallback_kwargs["extra_body"] = provider["extra_body"]
                if "reasoning_effort" in provider:
                    fallback_kwargs["reasoning_effort"] = provider["reasoning_effort"]
                env_key = provider.get("env_key")
                if env_key and os.getenv(env_key):
                    fallback_kwargs["api_key"] = os.getenv(env_key)

                response = litellm.completion(
                    model=fallback_model,
                    messages=messages,
                    max_tokens=max(max_tokens, 300),
                    temperature=temperature,
                    **fallback_kwargs,
                )
                msg = response.choices[0].message
                content = (msg.content or "").strip()
                if not content and hasattr(msg, "reasoning_content") and msg.reasoning_content:
                    content = msg.reasoning_content.strip()
                return content
            except Exception:
                continue
        return ""

    # ===== Embeddings =====

    def get_embedding_model(self) -> str:
        """Get the best available embedding model based on the active provider."""
        if not self._provider:
            return "local"
        
        provider_name = self._provider["name"]
        if provider_name == "openai":
            return "text-embedding-3-small"
        elif provider_name == "deepseek":
            return "local" # DeepSeek doesn't have a public embedding API via litellm out of the box
        elif provider_name == "gemini":
            return "models/text-embedding-004"
        elif provider_name == "anthropic":
            return "local" # Voyage AI is recommended, but requires separate key
        elif provider_name == "ollama":
            return "local"
            
        return "local"

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for a list of texts using the cloud provider.
        Returns a list of float vectors.
        """
        model = self.get_embedding_model()
        if model == "local":
            raise ValueError("Cloud embedding not available for current provider.")
            
        response = litellm.embedding(model=model, input=texts)
        return [item["embedding"] for item in response.data]

    # ===== Status & Info =====

    def get_status(self) -> Dict:
        """Return current configuration status for display."""
        return {
            "mode": self._mode,
            "provider": self.provider_name,
            "manual_model": self._manual_model,
            "available_providers": self.available_providers,
            "models": {
                "fast": self.get_model("fast"),
                "main": self.get_model("main"),
                "strong": self.get_model("strong"),
            },
        }

    def format_status(self) -> str:
        """Human-readable status string."""
        status = self.get_status()
        lines = [
            f"[DotCode LLM Status]",
            f"   Mode: {'Auto' if status['mode'] == 'auto' else 'Manual'}",
            f"   Provider: {status['provider'].upper()}",
        ]
        if status["mode"] == "manual":
            lines.append(f"   Model: {status['manual_model']}")
        else:
            lines.append(f"   Fast:   {status['models']['fast']}")
            lines.append(f"   Main:   {status['models']['main']}")
            lines.append(f"   Strong: {status['models']['strong']}")

        lines.append(f"   Available: {', '.join(status['available_providers'])}")
        return "\n".join(lines)


class HybridEmbedder:
    """Wrapper that tries Cloud Embeddings first, falls back to local CPU if not available."""
    def __init__(self, local_model_name: str = "BAAI/bge-m3", hf_token: Optional[str] = None):
        self.local_model_name = local_model_name
        self.hf_token = hf_token
        self._local_model = None
        self.llm = DotCodeLLM.get_instance()

    def encode(self, texts: List[str], normalize_embeddings: bool = True):
        import numpy as np
        # Try cloud embedding first
        cloud_model = self.llm.get_embedding_model()
        if cloud_model != "local":
            try:
                vectors = self.llm.embed(texts)
                return np.array(vectors)
            except Exception as e:
                print(f"⚠️ Cloud embedding failed ({e}), falling back to local CPU...")

        # Fallback to local
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(
                self.local_model_name, token=self.hf_token, trust_remote_code=True
            )
        return self._local_model.encode(texts, normalize_embeddings=normalize_embeddings)
