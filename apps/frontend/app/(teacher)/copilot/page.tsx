"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/lib/auth";
import { api, checkCopilotReady } from "@/lib/api-client";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: { source_title: string; source_type: string; chunk_count: number; page_numbers?: number[] }[];
  insufficient_context?: boolean;
}

const SCOPES = [
  { value: "teacher_kb", label: "قاعدة معرفتي فقط" },
  { value: "official_curriculum", label: "المنهج الرسمي فقط" },
  { value: "teacher_and_curriculum", label: "معرفتي + المنهج" },
  { value: "all", label: "جميع المصادر" },
];

const TASK_TYPES = [
  { value: "answer_question", label: "إجابة سؤال" },
  { value: "explain_concept", label: "شرح مفهوم" },
  { value: "generate_examples", label: "أمثلة تطبيقية" },
  { value: "generate_exam_questions", label: "أسئلة امتحانية" },
  { value: "summarize_source", label: "تلخيص مصدر" },
  { value: "create_revision_notes", label: "ملاحظات مراجعة" },
  { value: "rewrite_explanation", label: "إعادة صياغة" },
  { value: "improve_teacher_content", label: "تحسين محتوى" },
];

export default function CopilotPage() {
  const { token } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [scope, setScope] = useState("teacher_kb");
  const [taskType, setTaskType] = useState("answer_question");
  const [loading, setLoading] = useState(false);
  const [profileReady, setProfileReady] = useState<boolean | null>(null);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!token) return;
    checkCopilotReady(token)
      .then((r) => {
        setProfileReady(r.ready);
        setMissingFields(r.missing_fields);
      })
      .catch(() => setProfileReady(true));
  }, [token]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !token) return;
    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.copilot.chat(
        {
          messages: [...messages, userMsg].map((m) => ({ role: m.role, content: m.content })),
          scope,
          task_type: taskType,
        },
        token
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.text,
          sources: res.sources_used,
          insufficient_context: res.insufficient_context,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "حدث خطأ. يرجى المحاولة مرة أخرى." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div dir="rtl" className="flex flex-col h-[calc(100vh-8rem)]">

      {/* Profile incomplete warning */}
      {profileReady === false && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-4
          flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-yellow-800">
              ⚠️ ملفك الشخصي غير مكتمل — المساعد يعمل بإعدادات افتراضية
            </p>
            <p className="text-xs text-yellow-600 mt-0.5">
              أكمل إعداد: {missingFields.join("، ")} للحصول على إجابات أدق
            </p>
          </div>
          <button
            onClick={() => router.push("/settings")}
            className="text-xs bg-yellow-600 text-white px-3 py-1.5 rounded-lg hover:bg-yellow-700"
          >
            إكمال الإعداد
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between mb-4 gap-3">
        <h2 className="text-2xl font-bold text-gray-800 shrink-0">المساعد الذكي</h2>
        <div className="flex gap-2">
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm
              focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {TASK_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm
              focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {SCOPES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-400">
            <div className="text-center">
              <div className="text-5xl mb-4">🤖</div>
              <p>ابدأ محادثة مع المساعد الذكي</p>
              <p className="text-sm mt-1">اختر نوع المهمة والمصدر ثم اكتب سؤالك</p>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-start" : "justify-end"}`}>
            <div className="max-w-[80%]">
              <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-br-sm"
                  : "bg-gray-100 text-gray-800 rounded-bl-sm"
              }`}>
                {msg.role === "user" ? (
                msg.content
              ) : (
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 underline hover:text-indigo-800"
                      >
                        {children}
                      </a>
                    ),
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-semibold">{children}</strong>
                    ),
                    h1: ({ children }) => (
                      <h1 className="text-base font-bold mb-2">{children}</h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-sm font-bold mb-1">{children}</h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="text-sm font-semibold mb-1">{children}</h3>
                    ),
                    code: ({ children }) => (
                      <code className="bg-gray-200 px-1 rounded text-xs">{children}</code>
                    ),
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              )}
              </div>
              {/* Sources used — only show sources cited in the answer */}
              {msg.sources && msg.sources.filter(
                s => msg.content.includes(s.source_title)
              ).length > 0 && (
                <div className="mt-2 border-t border-indigo-100 pt-2">
                  <p className="text-xs text-gray-400 mb-1 text-right">📖 المصادر المستخدمة:</p>
                  <div className="flex flex-wrap gap-1 justify-end">
                    {msg.sources.filter(
                      s => msg.content.includes(s.source_title)
                    ).map((s, j) => (
                      <span key={j}
                        className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200
                          px-2 py-0.5 rounded-full font-medium">
                        📚 {s.source_title}
                        {s.page_numbers && s.page_numbers.length > 0 && (
                          <span className="text-indigo-400 mr-1">
                            {" "}— ص {s.page_numbers.join("، ")}
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {/* Insufficient context */}
              {msg.insufficient_context && (
                <p className="text-xs text-orange-500 mt-1 text-left">
                  ⚠️ لم يُعثر على محتوى كافٍ في قاعدة المعرفة
                </p>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-end">
            <div className="bg-gray-100 rounded-2xl px-4 py-3 text-sm text-gray-500 rounded-bl-sm">
              جارٍ الكتابة...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="mt-4 flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="اكتب سؤالك هنا..."
          className="flex-1 border border-gray-300 rounded-xl px-4 py-3 text-right
            focus:outline-none focus:ring-2 focus:ring-indigo-400"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl
            transition disabled:opacity-50"
        >
          إرسال
        </button>
      </form>
    </div>
  );
}
