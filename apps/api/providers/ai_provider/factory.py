from providers.ai_provider.base import AIProvider


def build_provider(provider: str, model: str, api_key: str) -> AIProvider:
    match provider:
        case "openai":
            from providers.ai_provider.openai import OpenAIProvider
            return OpenAIProvider(api_key=api_key, model=model)
        case "gemini":
            from providers.ai_provider.gemini import GeminiProvider
            return GeminiProvider(api_key=api_key, model=model)
        case "anthropic":
            from providers.ai_provider.anthropic import AnthropicProvider
            return AnthropicProvider(api_key=api_key, model=model)
        case _:
            raise ValueError(f"Unknown AI provider: {provider}")
