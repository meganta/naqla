from openai import AsyncOpenAI

from providers.ai_provider.base import AIMessage, AIProvider, AIResponse


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model

    async def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AIResponse:
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=openai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        return AIResponse(
            text=text, tokens_used=tokens_used, model=self.model_name, provider="openai"
        )

    async def stream(self, messages: list[AIMessage], system_prompt: str | None = None):
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})
        response = await self.client.chat.completions.create(
            model=self.model_name, messages=openai_messages, stream=True
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding

    async def transcribe(self, audio_url: str, language: str = "ar") -> str:
        raise NotImplementedError("OpenAI transcription not yet implemented")
