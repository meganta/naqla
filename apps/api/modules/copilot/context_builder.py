import json
from dataclasses import dataclass, field

from modules.ingestion.models import KnowledgeChunk, TenantSettings
from providers.ai_provider.base import SourceScope

# Methodology templates
METHODOLOGY_TEMPLATES = {
    "exam-focused": {
        "style": "تركيز على الأسئلة الامتحانية والنماذج المتوقعة",
        "depth": "متوسط — تغطية شاملة للمحاور الامتحانية",
        "tone": "منظم وواضح",
        "particle_strategy": ["exam_question", "revision_note", "summary"],
    },
    "weak-student-support": {
        "style": "تبسيط المفاهيم مع أمثلة كثيرة وتدرج في الشرح",
        "depth": "تفصيلي — خطوة بخطوة",
        "tone": "تشجيعي وصبور",
        "particle_strategy": ["step_by_step", "example", "practice"],
    },
    "fast-revision": {
        "style": "ملخصات سريعة ونقاط محورية",
        "depth": "سطحي — تركيز على الأهم",
        "tone": "موجز ومباشر",
        "particle_strategy": ["summary", "flashcard", "key_points"],
    },
    "step-by-step": {
        "style": "شرح تدريجي مع ربط المفاهيم ببعضها",
        "depth": "تفصيلي — بناء معرفي متراكم",
        "tone": "أكاديمي وواضح",
        "particle_strategy": ["explanation", "example", "practice"],
    },
    "skill-mastery": {
        "style": "التركيز على اكتساب المهارة من خلال التدريب المتكرر",
        "depth": "تطبيقي",
        "tone": "تدريبي وتقييمي",
        "particle_strategy": ["practice", "drill", "assessment"],
    },
    "memorization": {
        "style": "تكرار وتثبيت المعلومات بأساليب متنوعة",
        "depth": "تركيز على الحفظ والاسترجاع",
        "tone": "منظم ومتكرر",
        "particle_strategy": ["flashcard", "summary", "quiz"],
    },
}

DEFAULT_METHODOLOGY = {
    "template": "step-by-step",
    "style": "شرح خطوة بخطوة مع أمثلة من المنهج المصري",
    "depth": "متوسط إلى تفصيلي — مناسب لمستويات مختلفة",
    "student_level": "مختلط — طلاب المرحلة الثانوية",
    "tone": "ودي وأكاديمي في آن واحد",
    "particle_strategy": ["explanation", "example", "exam_question"],
}


@dataclass
class ChunkContext:
    chunk_id: str
    source_id: str
    source_title: str
    source_type: str
    content_text: str
    chunk_index: int
    source_url: str | None = None
    video_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    language: str | None = None


@dataclass
class TenantContextPackage:
    tenant_id: str
    tenant_name: str
    tenant_slug: str
    teacher_id: str
    teacher_name: str
    teacher_role: str
    subject: str
    grade_level: str
    curriculum_country: str
    curriculum_name: str
    school_name: str | None
    academic_year: str | None
    teaching_language: str
    student_level: str
    copilot_tone: str
    copilot_response_language: str
    methodology: dict
    source_scope: str
    task_type: str
    retrieved_chunks: list[ChunkContext] = field(default_factory=list)
    is_profile_complete: bool = False
    missing_fields: list[str] = field(default_factory=list)


def _build_chunk_context(chunk: KnowledgeChunk, source_title: str) -> ChunkContext:
    extra = {}
    if chunk.extra_meta:
        try:
            extra = json.loads(chunk.extra_meta)
        except Exception:
            pass
    return ChunkContext(
        chunk_id=chunk.id,
        source_id=chunk.source_id,
        source_title=source_title,
        source_type=chunk.source_type_tag or "unknown",
        content_text=chunk.content_text,
        chunk_index=chunk.chunk_index,
        source_url=extra.get("source_url"),
        video_id=extra.get("video_id"),
        start_time=extra.get("start_time"),
        end_time=extra.get("end_time"),
        language=extra.get("language"),
    )


def _build_methodology(settings: TenantSettings) -> dict:
    template_key = settings.methodology_template or "step-by-step"
    template = METHODOLOGY_TEMPLATES.get(template_key, {})
    return {
        "template": template_key,
        "style": settings.teaching_style or template.get("style", DEFAULT_METHODOLOGY["style"]),
        "depth": settings.explanation_depth or template.get("depth", DEFAULT_METHODOLOGY["depth"]),
        "student_level": settings.student_level or DEFAULT_METHODOLOGY["student_level"],
        "tone": settings.copilot_tone or template.get("tone", DEFAULT_METHODOLOGY["tone"]),
        "particle_strategy": template.get(
            "particle_strategy", DEFAULT_METHODOLOGY["particle_strategy"]
        ),
    }


def build_tenant_context(
    tenant_id: str,
    tenant_name: str,
    tenant_slug: str,
    teacher_id: str,
    teacher_name: str,
    teacher_role: str,
    settings: TenantSettings,
    source_scope: SourceScope,
    task_type: str,
    chunks: list[KnowledgeChunk],
    source_titles: dict[str, str],
) -> TenantContextPackage:
    missing = []
    if not settings.subject:
        missing.append("subject")
    if not settings.grade_level:
        missing.append("grade_level")
    if not settings.curriculum_country:
        missing.append("curriculum_country")

    chunk_contexts = [
        _build_chunk_context(c, source_titles.get(c.source_id, "مصدر غير معروف"))
        for c in chunks
    ]

    return TenantContextPackage(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
        teacher_id=teacher_id,
        teacher_name=teacher_name,
        teacher_role=teacher_role,
        subject=settings.subject or "اللغة العربية",
        grade_level=settings.grade_level or "المرحلة الثانوية",
        curriculum_country=settings.curriculum_country or "مصر",
        curriculum_name=settings.curriculum_name or "المنهج المصري الرسمي",
        school_name=settings.school_name,
        academic_year=settings.academic_year,
        teaching_language=settings.teaching_language or "العربية",
        student_level=settings.student_level or "مختلط",
        copilot_tone=settings.copilot_tone or "ودي وأكاديمي",
        copilot_response_language=settings.copilot_response_language or "العربية",
        methodology=_build_methodology(settings),
        source_scope=source_scope.value,
        task_type=task_type,
        retrieved_chunks=chunk_contexts,
        is_profile_complete=len(missing) == 0,
        missing_fields=missing,
    )
