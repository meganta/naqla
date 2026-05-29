"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { getSettings, updateSettings } from "@/lib/api-client";

const SUBJECTS = [
  "اللغة العربية", "الرياضيات", "العلوم", "الفيزياء", "الكيمياء", "الأحياء",
  "التاريخ", "الجغرافيا", "التربية الدينية", "اللغة الإنجليزية", "الحاسب الآلي", "أخرى",
];

const GRADE_LEVELS = [
  "المرحلة الابتدائية", "المرحلة الإعدادية", "المرحلة الثانوية",
  "الصف الأول الثانوي", "الصف الثاني الثانوي", "الصف الثالث الثانوي",
];

const COUNTRIES = [
  "مصر", "المملكة العربية السعودية", "الإمارات العربية المتحدة",
  "الكويت", "قطر", "البحرين", "الأردن", "المغرب", "تونس", "أخرى",
];

const STUDENT_LEVELS = ["متقدم", "متوسط", "مبتدئ", "مختلط"];

const TONES = ["ودي وأكاديمي", "رسمي", "تشجيعي", "موجز ومباشر"];

const METHODOLOGY_TEMPLATES = [
  { value: "step-by-step", label: "خطوة بخطوة" },
  { value: "exam-focused", label: "تركيز امتحاني" },
  { value: "weak-student-support", label: "دعم الطلاب الضعاف" },
  { value: "fast-revision", label: "مراجعة سريعة" },
  { value: "skill-mastery", label: "إتقان المهارة" },
  { value: "memorization", label: "حفظ وتكرار" },
];

const EXPLANATION_DEPTHS = ["سطحي", "متوسط", "تفصيلي", "تطبيقي"];

interface SettingsData {
  youtube_channel_url: string | null;
  subject: string | null;
  grade_level: string | null;
  curriculum_country: string | null;
  curriculum_name: string | null;
  school_name: string | null;
  academic_year: string | null;
  teaching_language: string | null;
  student_level: string | null;
  copilot_tone: string | null;
  copilot_response_language: string | null;
  methodology_template: string | null;
  teaching_style: string | null;
  explanation_depth: string | null;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
      <h2 className="text-base font-semibold text-gray-800 mb-4">{title}</h2>
      {children}
    </div>
  );
}

function Field({
  label, required, children,
}: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">
        {label}{required && <span className="text-red-500 mr-1">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-400 focus:border-transparent";

function Select({
  value, onChange, options, placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[] | { value: string; label: string }[];
  placeholder?: string;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) =>
        typeof o === "string"
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>
      )}
    </select>
  );
}

export default function SettingsPage() {
  const { token, user } = useAuth();
  const [data, setData] = useState<SettingsData>({
    youtube_channel_url: "",
    subject: "",
    grade_level: "",
    curriculum_country: "",
    curriculum_name: "",
    school_name: "",
    academic_year: "",
    teaching_language: "العربية",
    student_level: "",
    copilot_tone: "",
    copilot_response_language: "العربية",
    methodology_template: "",
    teaching_style: "",
    explanation_depth: "",
  });
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  useEffect(() => {
    if (!token) return;
    getSettings(token)
      .then((s: any) => {
        setData({
          youtube_channel_url: s.youtube_channel_url || "",
          subject: s.subject || "",
          grade_level: s.grade_level || "",
          curriculum_country: s.curriculum_country || "",
          curriculum_name: s.curriculum_name || "",
          school_name: s.school_name || "",
          academic_year: s.academic_year || "",
          teaching_language: s.teaching_language || "العربية",
          student_level: s.student_level || "",
          copilot_tone: s.copilot_tone || "",
          copilot_response_language: s.copilot_response_language || "العربية",
          methodology_template: s.methodology_template || "",
          teaching_style: s.teaching_style || "",
          explanation_depth: s.explanation_depth || "",
        });
      })
      .catch(console.error)
      .finally(() => setFetching(false));
  }, [token]);

  const set = (key: keyof SettingsData) => (value: string) =>
    setData((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    if (!token) return;
    setLoading(true);
    setMessage(null);
    try {
      await updateSettings(token, {
        ...data,
        youtube_channel_url: data.youtube_channel_url || null,
      });
      setMessage({ text: "تم الحفظ بنجاح ✓", error: false });
    } catch (e: any) {
      setMessage({ text: e.message || "حدث خطأ", error: true });
    } finally {
      setLoading(false);
    }
  };

  const isProfileComplete = !!(data.subject && data.grade_level && data.curriculum_country);

  if (fetching) return (
    <div dir="rtl" className="flex items-center justify-center min-h-[200px]">
      <p className="text-gray-400 text-sm">جاري التحميل...</p>
    </div>
  );

  return (
    <div dir="rtl" className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">الإعدادات</h1>
        {!isProfileComplete && (
          <span className="text-xs bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full">
            ⚠️ أكمل ملفك لتفعيل المساعد الذكي
          </span>
        )}
      </div>

      {/* Profile */}
      <Section title="الملف الشخصي">
        <div className="space-y-1">
          <p className="text-sm text-gray-700">{user?.full_name}</p>
          <p className="text-xs text-gray-400">{user?.email}</p>
        </div>
      </Section>

      {/* Academic profile */}
      <Section title="التخصص الأكاديمي">
        <p className="text-xs text-gray-400 mb-4">
          هذه المعلومات تُشكّل هوية المساعد الذكي وتجعل إجاباته أدق وأكثر تخصصاً
        </p>
        <div className="grid grid-cols-2 gap-4">
          <Field label="المادة الدراسية" required>
            <Select value={data.subject || ""} onChange={set("subject")}
              options={SUBJECTS} placeholder="اختر المادة" />
          </Field>
          <Field label="المرحلة الدراسية" required>
            <Select value={data.grade_level || ""} onChange={set("grade_level")}
              options={GRADE_LEVELS} placeholder="اختر المرحلة" />
          </Field>
          <Field label="الدولة والمنهج" required>
            <Select value={data.curriculum_country || ""} onChange={set("curriculum_country")}
              options={COUNTRIES} placeholder="اختر الدولة" />
          </Field>
          <Field label="اسم المنهج">
            <input type="text" value={data.curriculum_name || ""} onChange={(e) => set("curriculum_name")(e.target.value)}
              className={inputCls} placeholder="مثال: المنهج المصري الرسمي" />
          </Field>
          <Field label="اسم المدرسة">
            <input type="text" value={data.school_name || ""} onChange={(e) => set("school_name")(e.target.value)}
              className={inputCls} placeholder="اسم المدرسة" />
          </Field>
          <Field label="العام الدراسي">
            <input type="text" value={data.academic_year || ""} onChange={(e) => set("academic_year")(e.target.value)}
              className={inputCls} placeholder="2025-2026" />
          </Field>
          <Field label="مستوى الطلاب">
            <Select value={data.student_level || ""} onChange={set("student_level")}
              options={STUDENT_LEVELS} placeholder="اختر المستوى" />
          </Field>
          <Field label="لغة التدريس">
            <Select value={data.teaching_language || ""} onChange={set("teaching_language")}
              options={["العربية", "الإنجليزية", "ثنائي"]} />
          </Field>
        </div>
      </Section>

      {/* Methodology */}
      <Section title="منهجية التدريس">
        <p className="text-xs text-gray-400 mb-4">
          تحدد كيف يشرح المساعد الذكي ويبني المحتوى التعليمي
        </p>
        <div className="grid grid-cols-2 gap-4">
          <Field label="قالب المنهجية">
            <Select value={data.methodology_template || ""} onChange={set("methodology_template")}
              options={METHODOLOGY_TEMPLATES} placeholder="اختر القالب" />
          </Field>
          <Field label="عمق الشرح">
            <Select value={data.explanation_depth || ""} onChange={set("explanation_depth")}
              options={EXPLANATION_DEPTHS} placeholder="اختر العمق" />
          </Field>
          <Field label="أسلوب التدريس" >
            <input type="text" value={data.teaching_style || ""} onChange={(e) => set("teaching_style")(e.target.value)}
              className={inputCls} placeholder="مثال: شرح بأمثلة تطبيقية" />
          </Field>
        </div>
      </Section>

      {/* Copilot behavior */}
      <Section title="إعدادات المساعد الذكي">
        <div className="grid grid-cols-2 gap-4">
          <Field label="نبرة المساعد">
            <Select value={data.copilot_tone || ""} onChange={set("copilot_tone")}
              options={TONES} placeholder="اختر النبرة" />
          </Field>
          <Field label="لغة الإجابة">
            <Select value={data.copilot_response_language || ""} onChange={set("copilot_response_language")}
              options={["العربية", "الإنجليزية", "حسب السؤال"]} />
          </Field>
        </div>
      </Section>

      {/* YouTube */}
      <Section title="قناة يوتيوب">
        <p className="text-xs text-gray-400 mb-3">
          أضف رابط قناتك لاستيراد الفيديوهات إلى قاعدة المعرفة
        </p>
        <Field label="رابط القناة">
          <input type="url" value={data.youtube_channel_url || ""} onChange={(e) => set("youtube_channel_url")(e.target.value)}
            className={inputCls} placeholder="https://www.youtube.com/@channelname" />
        </Field>
      </Section>

      {/* Save */}
      <div className="flex items-center gap-3 pb-8">
        <button onClick={handleSave} disabled={loading}
          className="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          {loading ? "جاري الحفظ..." : "حفظ الإعدادات"}
        </button>
        {message && (
          <p className={`text-sm ${message.error ? "text-red-600" : "text-green-600"}`}>
            {message.text}
          </p>
        )}
      </div>
    </div>
  );
}
