from modules.copilot.context_builder import ChunkContext, TenantContextPackage

TASK_TYPE_INSTRUCTIONS = {
    "answer_question": "أجب على سؤال المعلم بدقة واستند إلى المصادر المتاحة.",
    "summarize_source": "لخص المحتوى المقدم بأسلوب واضح ومنظم.",
    "explain_concept": "اشرح المفهوم المطلوب بالتفصيل مع أمثلة مناسبة.",
    "generate_examples": "أنشئ أمثلة تطبيقية على المفهوم أو القاعدة المطلوبة.",
    "generate_exam_questions": (
        "أنشئ أسئلة امتحانية متنوعة المستويات مع النماذج والإجابات."
    ),
    "improve_teacher_content": "حسّن المحتوى المقدم من المعلم مع الحفاظ على أسلوبه.",
    "rewrite_explanation": "أعد صياغة الشرح بأسلوب أوضح وأكثر تناسباً مع مستوى الطلاب.",
    "create_revision_notes": "أنشئ ملاحظات مراجعة موجزة وشاملة.",
    "generate_particle_later": "جهّز محتوى تعليمياً منظماً سيُستخدم لاحقاً في بناء الجسيمات.",
}

SOURCE_SCOPE_RULES = {
    "teacher_kb": (
        "Use ONLY the retrieved chunks from the teacher knowledge base. "
        "If the chunks contain a direct answer, use it and cite the source. "
        "If the chunks do not contain sufficient information, explicitly tell the teacher first, "
        "then you may supplement with your general expertise — but label every such statement "
        "with [معلومة عامة] so the teacher knows it did not come from their content. "
        "Never present general knowledge as if it came from the teacher's materials."
    ),
    "official_curriculum": (
        "Use ONLY the official curriculum context. "
        "Do not use the teacher's content or general knowledge."
    ),
    "teacher_and_curriculum": (
        "Use both the teacher's content and the official curriculum. "
        "Clearly distinguish between the two sources in your answer."
    ),
    "all": (
        "Use the teacher's content, the official curriculum, and your\n"
        "specialized general knowledge "
        "within the teacher's subject domain only. "
        "Clearly distinguish between all three sources in your answer."
    ),
}


def _time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS or MM:SS to seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        pass
    return 0


def _format_chunk(chunk: ChunkContext, index: int) -> str:
    lines = [f"[Chunk {index + 1}] Source: {chunk.source_title} ({chunk.source_type})"]
    if chunk.start_time and chunk.end_time:
        lines.append(f"  Timestamp: {chunk.start_time} → {chunk.end_time}")
        if chunk.video_id:
            start_sec = _time_to_seconds(chunk.start_time)
            yt_url = (
                f"https://www.youtube.com/watch?v={chunk.video_id}&t={start_sec}"
            )
            lines.append(f"  Video URL: {yt_url}")
    elif chunk.start_time:
        lines.append(f"  Timestamp: {chunk.start_time}")
        if chunk.video_id:
            start_sec = _time_to_seconds(chunk.start_time)
            yt_url = (
                f"https://www.youtube.com/watch?v={chunk.video_id}&t={start_sec}"
            )
            lines.append(f"  Video URL: {yt_url}")
    elif chunk.source_url:
        lines.append(f"  URL: {chunk.source_url}")
    lines.append(f"  Content: {chunk.content_text}")
    return "\n".join(lines)


def build_system_prompt(ctx: TenantContextPackage) -> str:
    sections = []

    # 1. Identity
    sections.append(
        f"You are an intelligent educational assistant for teacher {ctx.teacher_name}. "
        f"You are NOT a general-purpose assistant. You are a specialized educational agent "
        f"operating strictly within the teacher's subject domain."
    )

    # 2. Teacher profile
    school_part = f" — {ctx.school_name}" if ctx.school_name else ""
    year_part = f"\n- Academic year: {ctx.academic_year}" if ctx.academic_year else ""
    sections.append(
        f"## Teacher & Institution Profile\n"
        f"- Teacher: {ctx.teacher_name} ({ctx.teacher_role})\n"
        f"- Institution: {ctx.tenant_name}{school_part}{year_part}"
    )

    # 3. Academic context
    sections.append(
        f"## Academic Context\n"
        f"- Subject: {ctx.subject}\n"
        f"- Grade level: {ctx.grade_level}\n"
        f"- Country & curriculum: {ctx.curriculum_country} — {ctx.curriculum_name}\n"
        f"- Teaching language: {ctx.teaching_language}\n"
        f"- Student level: {ctx.student_level}"
    )

    # 4. Methodology
    m = ctx.methodology
    sections.append(
        f"## Teaching Methodology\n"
        f"- Template: {m['template']}\n"
        f"- Style: {m['style']}\n"
        f"- Depth: {m['depth']}\n"
        f"- Tone: {m['tone']}"
    )

    # 5. Source scope
    scope_rule = SOURCE_SCOPE_RULES.get(ctx.source_scope, SOURCE_SCOPE_RULES["teacher_kb"])
    sections.append(f"## Source Scope\n{scope_rule}")

    # 6. Citation integrity — non-negotiable
    sections.append(
        "## Citation Rules — Non-Negotiable\n"
        "1. Only cite a video chunk if its content DIRECTLY contains the information "
        "you are stating in your answer — not merely because it is on the same topic.\n"
        "2. Never fabricate timestamps or URLs. Use only the timestamp and URL provided "
        "in the chunk metadata.\n"
        "3. If you used information from a chunk, cite it by name and timestamp.\n"
        "4. If NO chunk contains the required information, do NOT include any video link "
        "in your answer.\n"
        "5. Never present general knowledge as sourced from the teacher's content.\n"
        "6. Label every piece of general knowledge with [معلومة عامة]."
    )

    # 7. Retrieved chunks
    if ctx.retrieved_chunks:
        chunk_texts = "\n\n".join(
            _format_chunk(c, i) for i, c in enumerate(ctx.retrieved_chunks)
        )
        sections.append(
            "## Retrieved Knowledge Chunks\n"
            "Read all chunks and use them to inform your answer.\n"
            "- Use every chunk that is relevant to the question.\n"
            "- You MUST cite every chunk you used: include source title, "
            "timestamp, and video link at the end of your answer.\n"
            "- Skip only chunks that are completely unrelated to the question.\n"
            "- If NO chunk is relevant → tell the teacher, "
            "then answer from general knowledge and label each statement with [معلومة عامة].\n\n"
            f"{chunk_texts}"
        )
    else:
        sections.append(
            "## Retrieved Knowledge Chunks\n"
            "No relevant chunks were found in the teacher's knowledge base.\n"
            "Inform the teacher, then answer from your general expertise\n"
            "within the subject domain. "
            "Label every statement with [معلومة عامة]."
        )

    # 8. Response rules
    sections.append(
        f"## Response Rules\n"
        f"- Language: Always respond in {ctx.copilot_response_language} "
        f"unless explicitly asked otherwise\n"
        f"- Style: Specialized educational agent, not a general assistant\n"
        f"- Accuracy: Ensure academic correctness\n"
        f"- Examples: Use examples from the {ctx.curriculum_country} curriculum "
        f"({ctx.curriculum_name}) where applicable\n"
        f"- Integrity: If information is insufficient, say so and suggest adding "
        f"relevant sources to the knowledge base\n"
        f"- Scope: Stay within the teacher's subject domain unless strictly necessary"
    )

    # 9. Formatting rules
    sections.append(
        "## Response Formatting\n"
        "- Use Markdown formatting\n"
        "- Use headings, bullet points, and numbered lists to organize content\n"
        "- When citing a video chunk you actually used, format it as:\n"
        "  📍 **[Video Title]** — from `MM:SS` to `MM:SS`\n"
        "- Include a YouTube link ONLY if the chunk was a direct source:\n"
        "  [▶️ شاهد المقطع](https://www.youtube.com/watch?v=VIDEO_ID&t=SECONDS)\n"
        "- For text/file sources, mention the source title only\n"
        "- Mark all general knowledge statements with [معلومة عامة]"
    )

    # 10. Profile completeness warning
    if not ctx.is_profile_complete:
        missing = "، ".join(ctx.missing_fields)
        sections.append(
            f"## Warning: Incomplete Teacher Profile\n"
            f"The following fields are missing: {missing}\n"
            "Default values will be used until the teacher completes their profile settings."
        )

    return "\n\n".join(sections)


def build_user_prompt(user_message: str, task_type: str) -> str:
    instruction = TASK_TYPE_INSTRUCTIONS.get(
        task_type, "أجب على طلب المعلم بدقة واستند إلى المصادر المتاحة."
    )
    citation_reminder = (
        "Important citation reminder:\n"
        "- Only cite chunks whose content DIRECTLY supports what you are saying.\n"
        "- Do NOT include a video link unless that chunk's text was a direct source "
        "for a specific statement in your answer.\n"
        "- Label every statement from general knowledge with [معلومة عامة]."
    )
    return (
        f"[Task type: {task_type}]\n"
        f"{instruction}\n\n"
        f"{citation_reminder}\n\n"
        f"Teacher's question: {user_message}"
    )
