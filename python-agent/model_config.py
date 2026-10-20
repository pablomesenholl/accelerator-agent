"""Local model configuration; no cloud credentials required."""
import os

from google.adk.models.lite_llm import LiteLlm


def create_model() -> LiteLlm:
    return LiteLlm(
        model=os.getenv("ACCELERATOR_AGENT_MODEL", "ollama_chat/qwen3.5:4b-q4_K_M"),
        api_base=os.getenv("OLLAMA_API_BASE", "http://localhost:11434"),
        temperature=0,
        timeout=float(os.getenv("ACCELERATOR_AGENT_TIMEOUT", "300")),
        max_tokens=int(os.getenv("ACCELERATOR_AGENT_MAX_TOKENS", "2048")),
        num_ctx=int(os.getenv("ACCELERATOR_AGENT_CONTEXT", "16384")),
        num_retries=0,
        reasoning_effort=os.getenv("ACCELERATOR_AGENT_REASONING", "none"),
    )
