from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class SourceScope(str, Enum):
    TEACHER_KB = "teacher_kb"
    OFFICIAL_CURRICULUM = "official_curriculum"
    TEACHER_AND_CURRICULUM = "teacher_and_curriculum"
    ALL = "all"


@dataclass
class AIMessage:
    role: str
    content: str


@dataclass
class AIResponse:
    text: str
    tokens_used: int
    model: str
    provider: str
    source_scope: str | None = None


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AIResponse: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[AIMessage],
        system_prompt: str | None = None,
    ): ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def transcribe(self, audio_url: str, language: str = "ar") -> str: ...
