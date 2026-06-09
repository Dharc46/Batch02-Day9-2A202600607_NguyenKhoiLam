"""Shared LLM factory for all agents.

Supports OpenRouter and local Ollama through OpenAI-compatible APIs.
Select the backend with LLM_PROVIDER=openrouter or LLM_PROVIDER=ollama.
"""

import os

from langchain_openai import ChatOpenAI

from common.env import load_project_env


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client for the configured provider."""
    load_project_env()
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    if provider == "ollama":
        return ChatOpenAI(
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "300"))),
        )

    if provider != "openrouter":
        raise ValueError("LLM_PROVIDER must be either 'openrouter' or 'ollama'.")

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "300"))),
    )
