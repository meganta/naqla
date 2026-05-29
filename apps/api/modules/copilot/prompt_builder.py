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
        "استخدم فقط المحتوى المستخرج من قاعدة معرفة المعلم. "
        "إذا لم تجد إجابة في المحتوى المتاح، قل ذلك صراحةً ولا تستخدم معرفة عامة."
    ),
    "official_curriculum": (
        "استخدم فقط سياق المنهج الرسمي. "
        "لا تستخدم محتوى المعلم أو المعرفة العامة."
    ),
    "teacher_and_curriculum": (
        "استخدم محتوى المعلم والمنهج الرسمي معاً. "
        "ميّز بين المصدرين عند الإجابة."
    ),
    "all": (
        "استخدم محتوى المعلم والمنهج الرسمي والمعرفة العامة المتخصصة "
        "في نطاق تخصص المعلم فقط. "
        "ميّز بين المصادر الثلاثة عند الإجابة."
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
    lines = [f"[مقطع {index + 1}] من: {chunk.source_title} ({chunk.source_type})"]
    if chunk.start_time and chunk.end_time:
        lines.append(f"  التوقيت: من {chunk.start_time} إلى {chunk.end_time}")
        if chunk.video_id:
            start_sec = _time_to_seconds(chunk.start_time)
            yt_url = (
                f"https://www.youtube.com/watch?v={chunk.video_id}&t={start_sec}"
            )
            lines.append(f"  رابط المقطع: {yt_url}")
    elif chunk.start_time:
        lines.append(f"  التوقيت: {chunk.start_time}")
        if chunk.video_id:
            start_sec = _time_to_seconds(chunk.start_time)
            yt_url = (
                f"https://www.youtube.com/watch?v={chunk.video_id}&t={start_sec}"
            )
            lines.append(f"  رابط المقطع: {yt_url}")
    elif chunk.source_url:
        lines.append(f"  الرابط: {chunk.source_url}")
    lines.append(f"  المحتوى: {chunk.content_text}")
    return "\n".join(lines)


def build_system_prompt(ctx: TenantContextPackage) -> str:
    sections = []

    # 1. Copilot identity
    sections.append(
        f"أنت المساعد التعليمي الذكي الخاص بالمعلم {ctx.teacher_name}.\n"
        "أنت لست مساعداً عاماً — أنت وكيل تعليمي متخصص يعمل ضمن نطاق تخصص المعلم فقط."
    )

    # 2. Teacher and tenant profile
    sections.append(
        f"## هوية المعلم والمؤسسة\n"
        f"- المعلم: {ctx.teacher_name} ({ctx.teacher_role})\n"
        f"- المؤسسة: {ctx.tenant_name}"
        + (f" — {ctx.school_name}" if ctx.school_name else "") + "\n"
        + (f"- العام الدراسي: {ctx.academic_year}\n" if ctx.academic_year else "")
    )

    # 3. Academic specialization
    sections.append(
        f"## التخصص الأكاديمي\n"
        f"- المادة: {ctx.subject}\n"
        f"- المرحلة: {ctx.grade_level}\n"
        f"- الدولة والمنهج: {ctx.curriculum_country} — {ctx.curriculum_name}\n"
        f"- لغة التدريس: {ctx.teaching_language}\n"
        f"- مستوى الطلاب: {ctx.student_level}"
    )

    # 4. Methodology
    m = ctx.methodology
    sections.append(
        f"## منهجية التدريس\n"
        f"- القالب: {m['template']}\n"
        f"- الأسلوب: {m['style']}\n"
        f"- عمق الشرح: {m['depth']}\n"
        f"- النبرة: {m['tone']}"
    )

    # 5. Source scope rules
    scope_rule = SOURCE_SCOPE_RULES.get(ctx.source_scope, SOURCE_SCOPE_RULES["teacher_kb"])
    sections.append(f"## نطاق المصادر\n{scope_rule}")

    # 6. Source separation rules
    sections.append(
        "## قواعد فصل المصادر\n"
        "عند الإجابة، ميّز بين المصادر على النحو التالي:\n"
        "- من محتوى المعلم: [اذكر العنوان والتوقيت إن وُجد]\n"
        "- من المنهج الرسمي: [اذكر المرجع]\n"
        "- من المعرفة العامة المتخصصة: [فقط ضمن نطاق التخصص]\n"
        "لا تخترع مصادر. لا تدّعي أن معلومة موجودة في محتوى المعلم"
        " إلا إذا وردت في المقاطع المسترجعة."
    )

    # 7. Retrieved knowledge chunks
    if ctx.retrieved_chunks:
        chunk_texts = "\n\n".join(
            _format_chunk(c, i) for i, c in enumerate(ctx.retrieved_chunks)
        )
        sections.append(f"## المحتوى المسترجع من قاعدة معرفة المعلم\n{chunk_texts}")
    else:
        if ctx.source_scope == "teacher_kb":
            sections.append(
                "## المحتوى المسترجع\n"
                "لم يُعثر على مقاطع ذات صلة في قاعدة معرفة المعلم. "
                "إذا طُلب منك الإجابة من محتوى المعلم فقط، أخبر المعلم بذلك صراحةً "
                "واقترح إضافة مصادر ذات صلة."
            )

    # 8. Response rules
    sections.append(
        f"## قواعد الإجابة\n"
        f"- اللغة: {ctx.copilot_response_language} (الإجابة بالعربية دائماً ما لم يُطلب غير ذلك)\n"
        "- الأسلوب: وكيل تعليمي متخصص، ليس مساعداً عاماً\n"
        "- الدقة: اجعل إجاباتك صحيحة أكاديمياً\n"
        "- الأمثلة: استخدم أمثلة من المنهج المصري حيثما أمكن\n"
        "- النزاهة: إذا كانت المعلومات غير كافية، قل ذلك واقترح مصدراً مناسباً\n"
        "- التخصص: لا تخرج عن نطاق تخصص المعلم إلا إذا كان ضرورياً للمهمة التعليمية"
    )

    # 8b. Formatting rules
    sections.append(
        "## تنسيق الإجابة\n"
        "- استخدم تنسيق Markdown في إجاباتك\n"
        "- استخدم **عناوين** و**نقاط** و**ترقيم** لتنظيم المحتوى\n"
        "- عند الاستشهاد بمقطع فيديو، اذكر العنوان والتوقيت هكذا:\n"
        "  📍 **[عنوان الفيديو]** — من `MM:SS` إلى `MM:SS`\n"
        "- ضع روابط يوتيوب بهذا الشكل عند وجود video_id وstart_time:\n"
        "  [▶️ شاهد المقطع](https://www.youtube.com/watch?v=VIDEO_ID&t=SECONDS)\n"
        "- إذا كان المحتوى من نص أو ملف، اذكر عنوان المصدر فقط"
    )

    # 9. Profile completeness warning
    if not ctx.is_profile_complete:
        missing = "، ".join(ctx.missing_fields)
        sections.append(
            f"## تنبيه: الملف الشخصي غير مكتمل\n"
            f"الحقول التالية غير مُعبَّأة: {missing}\n"
            "سيتم استخدام القيم الافتراضية حتى يكمل المعلم إعداداته."
        )

    return "\n\n".join(sections)


def build_user_prompt(user_message: str, task_type: str) -> str:
    instruction = TASK_TYPE_INSTRUCTIONS.get(
        task_type, "أجب على طلب المعلم بدقة واستند إلى المصادر المتاحة."
    )
    return f"[نوع المهمة: {task_type}]\n{instruction}\n\n{user_message}"
