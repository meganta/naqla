from typing import Any

from pydantic import BaseModel

from providers.ai_provider.base import SourceScope


class ChatMessage(BaseModel):
    role: str
    content: str


class CopilotRequest(BaseModel):
    messages: list[ChatMessage]
    scope: SourceScope = SourceScope.TEACHER_KB
    task_type: str = "answer_question"
    max_tokens: int = 2000
    temperature: float = 0.7
    debug: bool = False


class SourceUsed(BaseModel):
    source_id: str
    source_title: str
    source_type: str
    chunk_count: int
    page_numbers: list[int] = []


class ConfidenceInfo(BaseModel):
    level: str          # high | medium | low | insufficient
    score: float
    reason: str


class CopilotDebugInfo(BaseModel):
    original_query: str
    normalized_query: str
    question_type: str
    retrieved_candidates_count: int
    selected_chunks_count: int


class CopilotResponse(BaseModel):
    text: str
    tokens_used: int
    model: str
    provider: str
    source_scope: str
    context_chunks_used: int
    insufficient_context: bool = False
    is_profile_complete: bool = True
    missing_profile_fields: list[str] = []
    sources_used: list[SourceUsed] = []
    evidence: list[Any] = []
    question_type: str = "unknown"
    confidence: ConfidenceInfo | None = None
    debug: CopilotDebugInfo | None = None
