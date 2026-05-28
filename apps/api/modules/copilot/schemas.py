from pydantic import BaseModel

from providers.ai_provider.base import SourceScope


class ChatMessage(BaseModel):
    role: str
    content: str


class CopilotRequest(BaseModel):
    messages: list[ChatMessage]
    scope: SourceScope = SourceScope.TEACHER_KB
    max_tokens: int = 1000
    temperature: float = 0.7


class CopilotResponse(BaseModel):
    text: str
    tokens_used: int
    model: str
    provider: str
    source_scope: str
    context_chunks_used: int
