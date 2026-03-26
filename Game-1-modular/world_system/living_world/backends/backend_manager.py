"""BackendManager — unified LLM backend abstraction for all AI systems.

Provides a single entry point for all LLM inference in the Living World.
Supports multiple backend types (Ollama, Claude, Mock) with automatic
fallback chains and per-task routing.

The crafting system (llm_item_generator.py) retains its own direct API calls
for backward compatibility. This manager is for NEW systems: NPC dialogue,
quest generation, faction narratives, lore, etc.

Usage:
    manager = BackendManager.get_instance()
    manager.initialize()  # Loads backend-config.json

    result = manager.generate(
        task="dialogue",
        system_prompt="You are a gruff blacksmith...",
        user_prompt="The player asks about iron swords.",
    )
"""

from __future__ import annotations

import json
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple


# ── Abstract Backend Interface ────────────────────────────────────────

class ModelBackend(ABC):
    """Abstract interface for LLM inference backends."""

    @abstractmethod
    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 temperature: float = 0.4,
                 max_tokens: int = 2000) -> Tuple[str, Optional[str]]:
        """Generate a text response.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User/context prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            Tuple of (response_text, error_string_or_None).
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is ready for use."""

    @abstractmethod
    def get_info(self) -> Dict[str, str]:
        """Return backend metadata (name, model, type)."""


# ── Ollama Backend ────────────────────────────────────────────────────

class OllamaBackend(ModelBackend):
    """Local Ollama server backend for offline LLM inference."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "llama3.1:8b",
                 timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._available: Optional[bool] = None

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.4,
                 max_tokens: int = 2000) -> Tuple[str, Optional[str]]:
        try:
            import urllib.request
            import urllib.error

            payload = json.dumps({
                "model": self.model,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", ""), None

        except Exception as e:
            return "", f"Ollama error: {e}"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0):
                self._available = True
        except Exception:
            self._available = False
        return self._available

    def get_info(self) -> Dict[str, str]:
        return {
            "name": "ollama",
            "model": self.model,
            "type": "local",
            "base_url": self.base_url,
        }


# ── Claude Backend ────────────────────────────────────────────────────

class ClaudeBackend(ModelBackend):
    """Anthropic Claude API backend.

    Mirrors the pattern from systems/llm_item_generator.py but with
    the abstract ModelBackend interface.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514",
                 timeout: float = 30.0,
                 max_tokens: int = 2000,
                 top_p: float = 0.95):
        self.model = model
        self.timeout = timeout
        self.max_tokens_default = max_tokens
        self.top_p = top_p
        self._client = None
        self._api_key: Optional[str] = None

    def _resolve_api_key(self) -> Optional[str]:
        """Resolve API key from environment or .env file."""
        if self._api_key:
            return self._api_key

        # Check environment variable
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            self._api_key = key
            return key

        # Check .env file in project root
        for candidate in ["Game-1-modular/.env", ".env"]:
            env_path = os.path.join(os.getcwd(), candidate)
            if os.path.exists(env_path):
                try:
                    with open(env_path) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("ANTHROPIC_API_KEY="):
                                key = line.split("=", 1)[1].strip().strip("\"'")
                                if key:
                                    self._api_key = key
                                    return key
                except Exception:
                    pass
        return None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                api_key = self._resolve_api_key()
                if not api_key:
                    raise ValueError("No ANTHROPIC_API_KEY found")
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._client

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.4,
                 max_tokens: int = 2000) -> Tuple[str, Optional[str]]:
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens_default,
                temperature=temperature,
                top_p=self.top_p,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text, None
        except Exception as e:
            return "", f"Claude API error: {e}"

    def is_available(self) -> bool:
        return self._resolve_api_key() is not None

    def get_info(self) -> Dict[str, str]:
        return {
            "name": "claude",
            "model": self.model,
            "type": "api",
            "has_key": str(self._resolve_api_key() is not None),
        }


# ── Mock Backend ──────────────────────────────────────────────────────

class MockBackend(ModelBackend):
    """Deterministic template-based backend for testing and graceful fallback.

    Extracts keywords from the prompt to select a response template.
    Always succeeds — the game never crashes due to AI failure.
    """

    TEMPLATES = {
        "dialogue": (
            '{"dialogue": "Hmm, interesting question. '
            'I have been thinking about that myself lately.", '
            '"emotion": "thoughtful", "disposition_change": 0.0}'
        ),
        "quest": (
            '{"quest_id": "generated_quest", "title": "A Task At Hand", '
            '"description": "There is work to be done.", '
            '"objectives": [{"type": "gather", "target": "iron_ore", "count": 5}], '
            '"rewards": {"exp": 100, "reputation": 0.05}}'
        ),
        "lore": (
            '{"text": "The ancient lands hold many secrets, '
            'whispered through the winds of time."}'
        ),
        "faction": (
            '{"narrative": "Your reputation precedes you. '
            'The people take notice of your deeds."}'
        ),
        "greeting": (
            '{"dialogue": "Welcome, traveler. What brings you here today?", '
            '"emotion": "neutral", "disposition_change": 0.0}'
        ),
    }

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.4,
                 max_tokens: int = 2000) -> Tuple[str, Optional[str]]:
        # Keyword matching to select template
        combined = (system_prompt + " " + user_prompt).lower()
        for keyword, template in self.TEMPLATES.items():
            if keyword in combined:
                return template, None
        # Default fallback
        return self.TEMPLATES["dialogue"], None

    def is_available(self) -> bool:
        return True

    def get_info(self) -> Dict[str, str]:
        return {"name": "mock", "model": "template", "type": "mock"}


# ── Rate Limiter ──────────────────────────────────────────────────────

@dataclass
class _RateLimitState:
    """Per-backend rate limiting state."""
    max_concurrent: int = 1
    cooldown_ms: int = 0
    _active_count: int = 0
    _last_call_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self) -> bool:
        """Try to acquire a slot. Returns True if allowed."""
        with self._lock:
            now = time.time()
            cooldown_sec = self.cooldown_ms / 1000.0
            if now - self._last_call_time < cooldown_sec:
                return False
            if self._active_count >= self.max_concurrent:
                return False
            self._active_count += 1
            self._last_call_time = now
            return True

    def release(self) -> None:
        with self._lock:
            self._active_count = max(0, self._active_count - 1)


# ── Backend Manager ───────────────────────────────────────────────────

class BackendManager:
    """Singleton manager for all LLM backends.

    Handles backend instantiation, task routing, fallback chains,
    and rate limiting. Loads configuration from backend-config.json.
    """

    _instance: ClassVar[Optional[BackendManager]] = None

    def __init__(self):
        self._backends: Dict[str, ModelBackend] = {}
        self._task_routing: Dict[str, str] = {}
        self._fallback_chain: List[str] = ["ollama", "claude", "mock"]
        self._rate_limits: Dict[str, _RateLimitState] = {}
        self._defaults: Dict[str, Any] = {
            "temperature": 0.4,
            "max_tokens": 2000,
        }
        self._initialized: bool = False
        self._config: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> BackendManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, config_path: Optional[str] = None) -> None:
        """Load configuration and instantiate backends.

        Args:
            config_path: Path to backend-config.json. If None, searches
                        in AI-Config.JSON/ relative to Game-1-modular/.
        """
        if self._initialized:
            return

        # Find config file
        if config_path and os.path.exists(config_path):
            cfg_path = config_path
        else:
            # Search relative to this module
            module_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
            cfg_path = os.path.join(
                project_root, "world_system", "config", "backend-config.json"
            )

        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                self._config = json.load(f)
            print(f"[BackendManager] Loaded config from {cfg_path}")
        else:
            print("[BackendManager] No config found — using defaults")
            self._config = {}

        self._setup_backends()
        self._setup_routing()
        self._setup_rate_limits()
        self._initialized = True

        # Log availability
        for name, backend in self._backends.items():
            avail = backend.is_available()
            print(f"[BackendManager] {name}: {'available' if avail else 'unavailable'}")

    def _setup_backends(self) -> None:
        """Instantiate backend objects from config."""
        backends_cfg = self._config.get("backends", {})

        # Ollama
        ollama_cfg = backends_cfg.get("ollama", {})
        if ollama_cfg.get("enabled", True):
            self._backends["ollama"] = OllamaBackend(
                base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
                model=ollama_cfg.get("default_model", "llama3.1:8b"),
                timeout=ollama_cfg.get("timeout_seconds", 30.0),
            )

        # Claude
        claude_cfg = backends_cfg.get("claude", {})
        if claude_cfg.get("enabled", True):
            self._backends["claude"] = ClaudeBackend(
                model=claude_cfg.get("model", "claude-sonnet-4-20250514"),
                timeout=claude_cfg.get("timeout_seconds", 30.0),
                max_tokens=claude_cfg.get("max_tokens", 2000),
                top_p=claude_cfg.get("top_p", 0.95),
            )

        # Mock (always available)
        mock_cfg = backends_cfg.get("mock", {})
        if mock_cfg.get("enabled", True):
            self._backends["mock"] = MockBackend()

    def _setup_routing(self) -> None:
        """Set up task-to-backend routing."""
        routing_cfg = self._config.get("task_routing", {})
        for task, cfg in routing_cfg.items():
            self._task_routing[task] = cfg.get("primary", "ollama")

        self._fallback_chain = self._config.get(
            "fallback_chain", ["ollama", "claude", "mock"]
        )
        self._defaults = self._config.get("defaults", self._defaults)

    def _setup_rate_limits(self) -> None:
        """Configure per-backend rate limits."""
        limits_cfg = self._config.get("rate_limits", {})
        for name in self._backends:
            cfg = limits_cfg.get(name, {})
            self._rate_limits[name] = _RateLimitState(
                max_concurrent=cfg.get("max_concurrent", 5),
                cooldown_ms=cfg.get("cooldown_ms", 0),
            )

    # ── Public API ────────────────────────────────────────────────────

    def get_backend(self, name: str) -> Optional[ModelBackend]:
        """Get a specific backend by name."""
        return self._backends.get(name)

    def generate(self, task: str, system_prompt: str, user_prompt: str,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 backend_override: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """Generate text using the appropriate backend for a task.

        Routes to the configured primary backend for this task type,
        falling back through the chain on failure.

        Args:
            task: Task type (e.g. "dialogue", "quests", "lore").
            system_prompt: System instructions.
            user_prompt: Context/user prompt.
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.
            backend_override: Force a specific backend (bypasses routing).

        Returns:
            Tuple of (response_text, error_string_or_None).
            On total failure, returns ("", error_description).
        """
        if not self._initialized:
            self.initialize()

        temp = temperature if temperature is not None else self._defaults.get("temperature", 0.4)
        tokens = max_tokens if max_tokens is not None else self._defaults.get("max_tokens", 2000)

        # Determine backend order
        if backend_override and backend_override in self._backends:
            chain = [backend_override]
        else:
            primary = self._task_routing.get(task, self._fallback_chain[0])
            # Build chain: primary first, then fallbacks (skip duplicates)
            chain = [primary]
            for name in self._fallback_chain:
                if name not in chain:
                    chain.append(name)

        errors = []
        for name in chain:
            backend = self._backends.get(name)
            if not backend:
                continue
            if not backend.is_available():
                errors.append(f"{name}: unavailable")
                continue

            # Rate limiting
            limiter = self._rate_limits.get(name)
            if limiter and not limiter.acquire():
                errors.append(f"{name}: rate limited")
                continue

            try:
                text, err = backend.generate(
                    system_prompt, user_prompt,
                    temperature=temp, max_tokens=tokens,
                )
                if err:
                    errors.append(f"{name}: {err}")
                    continue
                return text, None
            except Exception as e:
                errors.append(f"{name}: {e}")
            finally:
                if limiter:
                    limiter.release()

        return "", f"All backends failed: {'; '.join(errors)}"

    def generate_async(self, task: str, system_prompt: str, user_prompt: str,
                       callback=None, **kwargs) -> threading.Thread:
        """Run generation in a background thread.

        Args:
            task: Task type for routing.
            system_prompt: System instructions.
            user_prompt: Context prompt.
            callback: Optional callable(result_text, error) called on completion.
            **kwargs: Passed to generate().

        Returns:
            The background Thread (already started).
        """
        def _run():
            text, err = self.generate(task, system_prompt, user_prompt, **kwargs)
            if callback:
                try:
                    callback(text, err)
                except Exception as e:
                    print(f"[BackendManager] Callback error: {e}")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread

    @property
    def available_backends(self) -> List[str]:
        """List names of currently available backends."""
        return [
            name for name, backend in self._backends.items()
            if backend.is_available()
        ]

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "backends": {
                name: {
                    "available": backend.is_available(),
                    "info": backend.get_info(),
                }
                for name, backend in self._backends.items()
            },
            "task_routing": dict(self._task_routing),
            "fallback_chain": list(self._fallback_chain),
        }


def get_backend_manager() -> BackendManager:
    """Module-level accessor following project singleton pattern."""
    return BackendManager.get_instance()
