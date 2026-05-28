import google.generativeai as genai

from providers.ai_provider.base import AIMessage, AIProvider, AIResponse


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    async def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AIResponse:
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [system_prompt]})
            contents.append({"role": "model", "parts": ["فهمت. سأتبع هذه التعليمات."]})
        for msg in messages:
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [msg.content]})

        response = self.model.generate_content(
            contents,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        text = response.text or ""
        tokens_used = response.usage_metadata.total_token_count if response.usage_metadata else 0
        return AIResponse(
            text=text, tokens_used=tokens_used, model=self.model_name, provider="gemini"
        )

    async def stream(self, messages: list[AIMessage], system_prompt: str | None = None):
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [system_prompt]})
            contents.append({"role": "model", "parts": ["فهمت."]})
        for msg in messages:
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [msg.content]})
        response = self.model.generate_content(contents, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def embed(self, text: str) -> list[float]:
        result = genai.embed_content(model="models/embedding-001", content=text)
        return result["embedding"]

    async def transcribe(self, audio_url: str, language: str = "ar") -> str:
        raise NotImplementedError("Gemini transcription not yet implemented")
