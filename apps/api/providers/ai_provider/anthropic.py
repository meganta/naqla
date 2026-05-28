import anthropic

from providers.ai_provider.base import AIMessage, AIProvider, AIResponse


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model_name = model

    async def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AIResponse:
        anthropic_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        kwargs = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await self.client.messages.create(**kwargs)
        text = response.content[0].text if response.content else ""
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        return AIResponse(
            text=text, tokens_used=tokens_used, model=self.model_name, provider="anthropic"
        )

    async def stream(self, messages: list[AIMessage], system_prompt: str | None = None):
        anthropic_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        kwargs = {"model": self.model_name, "max_tokens": 1000, "messages": anthropic_messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Anthropic embeddings not yet supported")

    async def transcribe(self, audio_url: str, language: str = "ar") -> str:
        raise NotImplementedError("Anthropic transcription not yet implemented")
