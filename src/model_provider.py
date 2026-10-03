from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    provider: str
    model_name: str
    temperature: float = 0.0
    api_key: str | None = None
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    # ponytail: minimal alias map; extend when new aliases are encountered
    aliases = {
        "google": "gemini",
        "google-genai": "gemini",
        "anthorpic": "anthropic",
        "claude": "anthropic",
    }
    cleaned = value.strip().lower()
    return aliases.get(cleaned, cleaned)


def build_chat_model(config: ProviderConfig):
    # ponytail: dynamic lazy imports per provider; avoid loading all SDKs at startup
    provider = normalize_provider(config.provider)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model_name, temperature=config.temperature, api_key=config.api_key)
    if provider == "custom":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model_name, temperature=config.temperature, api_key=config.api_key or "custom", base_url=config.base_url)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=config.model_name, temperature=config.temperature, google_api_key=config.api_key)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=config.model_name, temperature=config.temperature, api_key=config.api_key)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=config.model_name, temperature=config.temperature, base_url=config.base_url)
    if provider == "openrouter":
        from langchain_openrouter import ChatOpenRouter
        return ChatOpenRouter(model=config.model_name, temperature=config.temperature, api_key=config.api_key)
    raise ValueError(f"Unsupported provider: {config.provider}")

