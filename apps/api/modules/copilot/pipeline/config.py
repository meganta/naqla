"""
Copilot pipeline configuration.
All tunable values in one place — change here, affects whole pipeline.
"""
from dataclasses import dataclass, field
from typing import Literal

SourceScopeMode = Literal[
    "teacher_kb_only",
    "curriculum_only",
    "teacher_kb_plus_curriculum",
    "all_sources",
]

QuestionType = Literal[
    "definition",
    "explanation",
    "comparison",
    "exercise_solving",
    "summarization",
    "lesson_planning",
    "exam_question",
    "source_specific",
    "unknown",
]

ConfidenceLevel = Literal["high", "medium", "low", "insufficient"]


@dataclass
class RetrievalConfig:
    candidate_limit: int = 40          # initial candidates before reranking
    final_chunks: int = 8              # max chunks sent to LLM
    max_chunks_per_source: int = 3     # dedup cap per source
    embedding_model: str = "text-embedding-3-small"

    # Thresholds by question type (cosine distance — lower = more similar)
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "definition":       0.65,
        "explanation":      0.70,
        "comparison":       0.70,
        "exercise_solving": 0.62,
        "summarization":    0.75,
        "lesson_planning":  0.78,
        "exam_question":    0.70,
        "source_specific":  0.60,
        "unknown":          0.70,
    })

    def threshold_for(self, question_type: str) -> float:
        return self.thresholds.get(question_type, 0.70)


@dataclass
class GenerationConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2000


@dataclass
class PipelineConfig:
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    debug_mode: bool = False
    default_scope: SourceScopeMode = "teacher_kb_only"
    # Minimum evidence chunks required per question type
    min_evidence: dict[str, int] = field(default_factory=lambda: {
        "definition":       1,
        "explanation":      1,
        "comparison":       2,
        "exercise_solving": 1,
        "summarization":    2,
        "lesson_planning":  1,
        "exam_question":    1,
        "source_specific":  1,
        "unknown":          1,
    })

    def min_evidence_for(self, question_type: str) -> int:
        return self.min_evidence.get(question_type, 1)


# Singleton default config
DEFAULT_CONFIG = PipelineConfig()
