"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { generateTeacherProfile, getTeacherProfile } from "@/lib/api-client";

interface ProfileData {
  tone?: { primary?: string; secondary?: string[]; confidence?: number };
  language_style?: { dialect?: string; vocabulary_complexity?: string; uses_dialect_slang?: boolean };
  common_phrases?: { phrase: string; frequency: string; context: string }[];
  explanation_style?: { primary_style?: string; ranked_styles?: string[]; confidence?: number };
  teaching_methodology?: { typically_starts_with?: string; lesson_flow?: string; detected_patterns?: string[]; confidence?: number };
  difficulty_handling?: { approach?: string; uses_prerequisites?: boolean; repeats_concepts?: boolean; provides_multiple_examples?: boolean };
  student_interaction?: { primary_style?: string; detected_behaviors?: string[]; confidence?: number };
  exam_orientation?: { is_exam_focused?: boolean; ranked_focus_areas?: string[]; confidence?: number };
  teaching_habits?: { preferred_detail_level?: string; uses_repetition?: boolean; anticipates_student_mistakes?: boolean; emphasis?: string; encourages_critical_thinking?: boolean; confidence?: number };
  metadata?: { chunks_analyzed?: number; sources_analyzed?: number; source_type_distribution?: Record<string, number> };
}

function ConfidenceBadge({ value }: { value?: number }) {
  if (!value) return null;
  const color = value >= 80 ? "bg-green-100 text-green-800" : value >= 60 ? "bg-yellow-100 text-yellow-800" : "bg-gray-100 text-gray-600";
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{value}%</span>;
}

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
        <span>{icon}</span>{title}
      </h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | boolean | null }) {
  if (value === undefined || value === null) return null;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="text-xs font-medium text-gray-800 text-left">
        {typeof value === "boolean" ? (value ? "✓ نعم" : "✗ لا") : value}
      </span>
    </div>
  );
}

export default function TeachingStylePage() {
  const { token } = useAuth();
  const [status, setStatus] = useState<string | null>(null);
  const [version, setVersion] = useState<number>(0);
  const [chunksAnalyzed, setChunksAnalyzed] = useState(0);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [generating, setGenerating] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchProfile = async (includeProfile = true) => {
    if (!token) return;
    try {
      const data = await getTeacherProfile(token, includeProfile);
      setStatus(data.status);
      setVersion(data.version);
      setChunksAnalyzed(data.chunks_analyzed);
      setGeneratedAt(data.generated_at);
      if (data.profile) setProfile(data.profile as ProfileData);
      return data.status;
    } catch {
      setStatus(null);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [token]);

  useEffect(() => {
    if (status !== "processing") return;
    setPolling(true);
    const interval = setInterval(async () => {
      const s = await fetchProfile(true);
      if (s !== "processing") {
        setPolling(false);
        clearInterval(interval);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [status]);

  const handleGenerate = async () => {
    if (!token) return;
    setGenerating(true);
    try {
      await generateTeacherProfile(token);
      setStatus("processing");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div dir="rtl" className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">البصمة التعليمية</h1>
            <p className="text-sm text-gray-500 mt-1">
              تحليل ذكي لأسلوبك التدريسي المستخرج من قاعدة معرفتك
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || status === "processing"}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg
              hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
          >
            {generating || status === "processing" ? (
              <>
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                </svg>
                جاري التحليل...
              </>
            ) : (
              <>{status ? "🔄 إعادة التحليل" : "✨ تحليل أسلوبي"}</>
            )}
          </button>
        </div>

        {/* Status bar */}
        {status && (
          <div className={`rounded-lg px-4 py-3 mb-6 text-sm flex items-center justify-between ${
            status === "completed" ? "bg-green-50 border border-green-200" :
            status === "processing" ? "bg-blue-50 border border-blue-200" :
            "bg-red-50 border border-red-200"
          }`}>
            <span className={
              status === "completed" ? "text-green-800" :
              status === "processing" ? "text-blue-800" : "text-red-800"
            }>
              {status === "completed" && `✓ تم التحليل — الإصدار ${version} — ${chunksAnalyzed} قطعة محللة`}
              {status === "processing" && "⏳ جاري تحليل قاعدة المعرفة... قد يستغرق 2-3 دقائق"}
              {status === "failed" && "✗ فشل التحليل — يرجى المحاولة مجدداً"}
            </span>
            {generatedAt && status === "completed" && (
              <span className="text-gray-400 text-xs">
                {new Date(generatedAt).toLocaleDateString("ar-EG")}
              </span>
            )}
          </div>
        )}

        {!status && !generating && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-8 text-center">
            <div className="text-4xl mb-3">🧠</div>
            <h3 className="text-base font-semibold text-indigo-900 mb-2">
              اكتشف بصمتك التعليمية
            </h3>
            <p className="text-sm text-indigo-700 mb-4">
              سيقوم الذكاء الاصطناعي بتحليل قاعدة معرفتك واستخراج أسلوبك التدريسي الفريد،
              ثم يستخدمه لجعل إجابات المساعد الذكي تبدو مثلك تماماً.
            </p>
            <button
              onClick={handleGenerate}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700"
            >
              ابدأ التحليل
            </button>
          </div>
        )}

        {/* Profile sections */}
        {profile && status === "completed" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Tone */}
            {profile.tone && (
              <Section title="النبرة والأسلوب" icon="🎯">
                <Row label="النبرة الأساسية" value={profile.tone.primary} />
                <Row label="نبرات ثانوية" value={profile.tone.secondary?.join("، ")} />
                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-gray-400">مستوى الثقة</span>
                  <ConfidenceBadge value={profile.tone.confidence} />
                </div>
              </Section>
            )}

            {/* Language */}
            {profile.language_style && (
              <Section title="اللغة والأسلوب" icon="🗣️">
                <Row label="اللهجة" value={profile.language_style.dialect} />
                <Row label="مستوى المفردات" value={profile.language_style.vocabulary_complexity} />
                <Row label="يستخدم تعبيرات عامية" value={profile.language_style.uses_dialect_slang} />
              </Section>
            )}

            {/* Common phrases */}
            {profile.common_phrases && profile.common_phrases.length > 0 && (
              <Section title="العبارات المتكررة" icon="💬">
                <div className="space-y-2">
                  {profile.common_phrases.map((p, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">{p.context}</span>
                      <span className="text-sm font-medium text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                        {p.phrase}
                      </span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Explanation style */}
            {profile.explanation_style && (
              <Section title="أسلوب الشرح" icon="📖">
                <Row label="الأسلوب الأساسي" value={profile.explanation_style.primary_style} />
                {profile.explanation_style.ranked_styles && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-400 mb-1">ترتيب الأساليب المكتشفة:</p>
                    <div className="flex flex-wrap gap-1">
                      {profile.explanation_style.ranked_styles.slice(0, 5).map((s, i) => (
                        <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                          i === 0 ? "bg-indigo-100 text-indigo-700 font-medium" : "bg-gray-100 text-gray-600"
                        }`}>{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-gray-400">مستوى الثقة</span>
                  <ConfidenceBadge value={profile.explanation_style.confidence} />
                </div>
              </Section>
            )}

            {/* Teaching methodology */}
            {profile.teaching_methodology && (
              <Section title="منهجية التدريس" icon="🏫">
                <Row label="يبدأ بـ" value={profile.teaching_methodology.typically_starts_with} />
                <Row label="تدفق الدرس" value={profile.teaching_methodology.lesson_flow} />
                {profile.teaching_methodology.detected_patterns && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {profile.teaching_methodology.detected_patterns.map((p, i) => (
                      <span key={i} className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">{p}</span>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-gray-400">مستوى الثقة</span>
                  <ConfidenceBadge value={profile.teaching_methodology.confidence} />
                </div>
              </Section>
            )}

            {/* Difficulty handling */}
            {profile.difficulty_handling && (
              <Section title="التعامل مع الصعوبات" icon="📈">
                <Row label="الأسلوب" value={profile.difficulty_handling.approach} />
                <Row label="يستخدم المتطلبات المسبقة" value={profile.difficulty_handling.uses_prerequisites} />
                <Row label="يكرر المفاهيم" value={profile.difficulty_handling.repeats_concepts} />
                <Row label="يقدم أمثلة متعددة" value={profile.difficulty_handling.provides_multiple_examples} />
              </Section>
            )}

            {/* Student interaction */}
            {profile.student_interaction && (
              <Section title="التفاعل مع الطلاب" icon="👥">
                <Row label="الأسلوب الأساسي" value={profile.student_interaction.primary_style} />
                {profile.student_interaction.detected_behaviors && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {profile.student_interaction.detected_behaviors.map((b, i) => (
                      <span key={i} className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">{b}</span>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-gray-400">مستوى الثقة</span>
                  <ConfidenceBadge value={profile.student_interaction.confidence} />
                </div>
              </Section>
            )}

            {/* Exam orientation */}
            {profile.exam_orientation && (
              <Section title="التوجه الامتحاني" icon="📝">
                <Row label="مُركّز على الامتحانات" value={profile.exam_orientation.is_exam_focused} />
                {profile.exam_orientation.ranked_focus_areas && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-400 mb-1">مجالات التركيز:</p>
                    <div className="flex flex-wrap gap-1">
                      {profile.exam_orientation.ranked_focus_areas.map((f, i) => (
                        <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                          i === 0 ? "bg-orange-100 text-orange-700 font-medium" : "bg-gray-100 text-gray-600"
                        }`}>{f}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-gray-400">مستوى الثقة</span>
                  <ConfidenceBadge value={profile.exam_orientation.confidence} />
                </div>
              </Section>
            )}

            {/* Teaching habits */}
            {profile.teaching_habits && (
              <Section title="العادات التدريسية" icon="🧠">
                <Row label="مستوى التفصيل" value={profile.teaching_habits.preferred_detail_level} />
                <Row label="يكرر النقاط المهمة" value={profile.teaching_habits.uses_repetition} />
                <Row label="يتوقع أخطاء الطلاب" value={profile.teaching_habits.anticipates_student_mistakes} />
                <Row label="التركيز على" value={profile.teaching_habits.emphasis} />
                <Row label="يشجع التفكير النقدي" value={profile.teaching_habits.encourages_critical_thinking} />
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-gray-400">مستوى الثقة</span>
                  <ConfidenceBadge value={profile.teaching_habits.confidence} />
                </div>
              </Section>
            )}

            {/* Metadata */}
            {profile.metadata && (
              <Section title="بيانات التحليل" icon="📊">
                <Row label="قطع محللة" value={String(profile.metadata.chunks_analyzed)} />
                {profile.metadata.source_type_distribution && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(profile.metadata.source_type_distribution).map(([type, count]) => (
                      <div key={type} className="flex items-center justify-between">
                        <span className="text-xs text-gray-500">
                          {({
                            youtube: "يوتيوب",
                            video: "فيديو",
                            audio: "صوت",
                            pdf: "ملف PDF",
                            docx: "ملف Word",
                            pptx: "عرض تقديمي",
                            text: "نص",
                            manual: "يدوي",
                            unknown: "غير معروف",
                          } as Record<string, string>)[type] ?? type}
                        </span>
                        <span className="text-xs font-medium text-gray-700">{count} مصدر</span>
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            )}

          </div>
        )}
      </div>
    </div>
  );
}
