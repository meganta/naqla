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
        "If the chunks do not contain sufficient information, you MUST start your response "
        "with the Arabic phrase: '⚠️ لم أجد إجابة كافية في قاعدة معرفتك.' "
        "Then you may add general knowledge but MUST prefix EVERY sentence with [معلومة عامة]. "
        "Never write a full answer without this warning when chunks are insufficient. "
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


def build_style_profile_section(profile: dict) -> str:
    """
    Convert a Teacher Style Profile dict into a system prompt section.
    Instructs the AI to mirror the teacher's communication and teaching style.
    """
    if not profile:
        return ""

    lines = ["## Teacher Style Profile (Mirror This Style)"]

    # Tone
    tone = profile.get("tone", {})
    if tone and tone.get("confidence", 0) >= 50:
        primary = tone.get("primary", "")
        secondary = tone.get("secondary", [])
        sec_str = f" with {', '.join(secondary)} elements" if secondary else ""
        lines.append(f"- **Tone:** {primary}{sec_str}")

    # Language style
    lang = profile.get("language_style", {})
    if lang and lang.get("confidence", 0) >= 50:
        dialect = lang.get("dialect", "")
        complexity = lang.get("vocabulary_complexity", "")
        slang = lang.get("uses_dialect_slang", False)
        if dialect:
            lines.append(f"- **Language:** {dialect} Arabic, {complexity} vocabulary")
        if slang:
            lines.append(
                "- Use natural Egyptian colloquial expressions where appropriate"
            )

    # Common phrases
    phrases = profile.get("common_phrases", [])
    high_freq = [p["phrase"] for p in phrases if p.get("frequency") == "high"]
    if high_freq:
        lines.append(f"- **Common phrases to use:** {' / '.join(high_freq[:3])}")

    # Explanation style
    exp = profile.get("explanation_style", {})
    if exp and exp.get("confidence", 0) >= 50:
        primary_style = exp.get("primary_style", "")
        if primary_style:
            lines.append(f"- **Explanation style:** {primary_style}")

    # Teaching methodology
    meth = profile.get("teaching_methodology", {})
    if meth and meth.get("confidence", 0) >= 50:
        flow = meth.get("lesson_flow", "")
        if flow:
            lines.append(f"- **Answer flow:** {flow}")

    # Teaching habits
    habits = profile.get("teaching_habits", {})
    if habits and habits.get("confidence", 0) >= 50:
        if habits.get("uses_repetition"):
            lines.append("- Repeat and reinforce key points")
        if habits.get("anticipates_student_mistakes"):
            lines.append("- Proactively mention common mistakes students make")
        emphasis = habits.get("emphasis", "")
        if emphasis == "understanding":
            lines.append("- Emphasize deep understanding over memorization")
        detail = habits.get("preferred_detail_level", "")
        if detail:
            lines.append(f"- Detail level: {detail}")

    # Student interaction
    interaction = profile.get("student_interaction", {})
    if interaction and interaction.get("confidence", 0) >= 50:
        style = interaction.get("primary_style", "")
        if style == "guide-discovery":
            lines.append(
                "- Guide students to discover answers rather than stating them directly"
            )

    # Exam orientation
    exam = profile.get("exam_orientation", {})
    if exam and exam.get("is_exam_focused") and exam.get("confidence", 0) >= 50:
        focus_areas = exam.get("ranked_focus_areas", [])[:2]
        if focus_areas:
            lines.append(
                f"- Exam-focused: highlight {' and '.join(focus_areas)}"
            )

    if len(lines) == 1:  # only header, no content
        return ""

    lines.append(
        "- Always sound like THIS teacher, not a generic AI assistant"
    )
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
            "These chunks are colloquial Arabic transcripts from the teacher's videos. "
            "They contain real educational content in spoken form.\n"
            "Your instructions:\n"
            "1. Read each chunk and identify content relevant to the question.\n"
            "2. Rewrite ONLY what is in the chunk into clear formal Arabic — "
            "do NOT add any information not present in the chunk text.\n"
            "3. Stay strictly faithful to the chunk — same concepts, same points, "
            "just reformatted. If a concept is not in the chunk, do not include it.\n"
            "4. Cite every chunk you used with source title, timestamp and video link.\n"
            "5. Only if chunks contain ZERO relevant content, say so and answer "
            "from general knowledge labeling each statement with [معلومة عامة].\n\n"
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
        "- When citing a video chunk, you MUST use this exact format — both lines together:\n"
        "  📍 **[Video Title]** — from `MM:SS` to `MM:SS`\n"
        "  [▶️ شاهد المقطع](https://www.youtube.com/watch?v=VIDEO_ID&t=SECONDS)\n"
        "  Never show a timestamp without its link.\n"
        "  Never show a link without its timestamp.\n"
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

    # Inject teacher style profile if available
    if hasattr(ctx, "style_profile") and ctx.style_profile:
        style_section = build_style_profile_section(ctx.style_profile)
        if style_section:
            sections.insert(3, style_section)  # after methodology section

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
