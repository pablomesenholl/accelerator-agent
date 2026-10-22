"""Validated, provider-aware settings for the standalone LiteLLM adapter."""
from dataclasses import dataclass, field
import math
import os
from collections.abc import Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ModelConfig:
    model: str = "ollama_chat/qwen2.5-coder:3b"
    api_base: str | None = field(default=None, repr=False)
    api_key: str | None = field(default=None, repr=False)
    timeout: float = 300
    max_tokens: int = 2048
    context: int = 16384
    reasoning: str | None = None

    @property
    def is_ollama(self) -> bool:
        return self.model.split("/", 1)[0] in {"ollama", "ollama_chat"}

    def __post_init__(self):
        if (not isinstance(self.model, str) or not self.model.strip()
                or any(c.isspace() for c in self.model)
                or self.model.startswith("/") or self.model.endswith("/")):
            raise ValueError("ACCELERATOR_AGENT_MODEL must be a nonempty LiteLLM model name without whitespace")
        for name, value in (("TIMEOUT", self.timeout), ("MAX_TOKENS", self.max_tokens),
                            ("CONTEXT", self.context)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"ACCELERATOR_AGENT_{name} must be a finite positive number")
        for name, value in (("MAX_TOKENS", self.max_tokens), ("CONTEXT", self.context)):
            if not isinstance(value, int):
                raise ValueError(f"ACCELERATOR_AGENT_{name} must be a positive integer")
        if self.reasoning not in {None, "none", "minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("ACCELERATOR_AGENT_REASONING must be none, minimal, low, medium, high, or xhigh")
        if self.api_key is not None and (not isinstance(self.api_key, str) or not self.api_key.strip()):
            raise ValueError("ACCELERATOR_AGENT_API_KEY must be nonempty when set")
        if self.api_base is not None:
            try:
                url = urlsplit(self.api_base)
                valid = (url.scheme in {"http", "https"} and url.hostname
                         and not url.username and not url.password and not url.query
                         and not url.fragment and not any(c.isspace() for c in self.api_base))
                url.port  # Validate an explicitly supplied port too.
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise ValueError("Model API base must be an HTTP(S) URL without credentials, query, or fragment")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ModelConfig":
        env = os.environ if env is None else env
        model = env.get("ACCELERATOR_AGENT_MODEL", "ollama_chat/qwen2.5-coder:3b")
        ollama = model.split("/", 1)[0] in {"ollama", "ollama_chat"}

        def number(name, default, convert):
            try:
                return convert(env.get(name, default))
            except (ValueError, TypeError):
                raise ValueError(f"{name} must be a positive {'integer' if convert is int else 'number'}") from None

        return cls(
            model=model,
            api_base=env.get("ACCELERATOR_AGENT_API_BASE",
                             env.get("OLLAMA_API_BASE", "http://localhost:11434") if ollama else None),
            api_key=env.get("ACCELERATOR_AGENT_API_KEY"),
            timeout=number("ACCELERATOR_AGENT_TIMEOUT", "300", float),
            max_tokens=number("ACCELERATOR_AGENT_MAX_TOKENS", "2048", int),
            context=number("ACCELERATOR_AGENT_CONTEXT", "16384", int),
            reasoning=env.get("ACCELERATOR_AGENT_REASONING", "none" if ollama else None),
        )

    def adapter_kwargs(self) -> dict:
        settings = dict(model=self.model, temperature=0, timeout=self.timeout,
                        max_tokens=self.max_tokens, num_retries=0)
        if self.api_base is not None:
            settings["api_base"] = self.api_base
        if self.api_key is not None:
            settings["api_key"] = self.api_key
        if self.is_ollama:
            settings["num_ctx"] = self.context
            settings["reasoning_effort"] = self.reasoning or "none"
        elif self.reasoning is not None:
            settings["reasoning_effort"] = self.reasoning
        return settings

    def summary(self) -> dict:
        """Allowlisted settings only; endpoints and credential values stay private."""
        return dict(model=self.model, ollama=self.is_ollama,
                    api_base_configured=self.api_base is not None,
                    api_key_configured=self.api_key is not None,
                    timeout=self.timeout, max_tokens=self.max_tokens,
                    context=self.context if self.is_ollama else None,
                    reasoning=self.reasoning or ("none" if self.is_ollama else None),
                    num_retries=0)


def create_model(config: ModelConfig | None = None):
    # Validate before importing/constructing the provider adapter.
    settings = config if config is not None else ModelConfig.from_env()
    from google.adk.models.lite_llm import LiteLlm
    return LiteLlm(**settings.adapter_kwargs())
