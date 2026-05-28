from providers.ai_provider.base import AIProvider
from providers.ai_provider.gemini import GeminiProvider


def build_provider(provider: str, model: str, api_key: str) -> AIProvider:
    match provider:
        case "gemini":
            return GeminiProvider(api_key=api_key, model=model)
        case _:
            raise ValueError(f"Unknown AI provider: {provider}")
