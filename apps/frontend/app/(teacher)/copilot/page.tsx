"use client";
import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const SCOPES = [
  { value: "teacher_kb", label: "قاعدة معرفتي فقط" },
  { value: "official_curriculum", label: "المنهج الرسمي فقط" },
  { value: "teacher_and_curriculum", label: "معرفتي + المنهج" },
  { value: "all", label: "جميع المصادر" },
];

export default function CopilotPage() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [scope, setScope] = useState("teacher_kb");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !token) return;
    const userMsg: Message = { role: "user", content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput(""); setLoading(true);
    try {
      const res = await api.copilot.chat({
        messages: [...messages, userMsg].map(m => ({ role: m.role, content: m.content })),
        scope,
      }, token);
      setMessages(prev => [...prev, { role: "assistant", content: res.text }]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "حدث خطأ. يرجى المحاولة مرة أخرى." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-800">المساعد الذكي</h2>
        <select
          value={scope} onChange={e => setScope(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          {SCOPES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>
      <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-400">
            <div className="text-center">
              <div className="text-5xl mb-4">🤖</div>
              <p>ابدأ محادثة مع المساعد الذكي</p>
              <p className="text-sm mt-1">اسأل عن أي موضوع في اللغة العربية</p>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-start" : "justify-end"}`}>
            <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
              msg.role === "user"
                ? "bg-indigo-600 text-white rounded-br-sm"
                : "bg-gray-100 text-gray-800 rounded-bl-sm"
            }`}>
              {msg.content}
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
      <form onSubmit={handleSend} className="mt-4 flex gap-3">
        <input
          value={input} onChange={e => setInput(e.target.value)}
          placeholder="اكتب سؤالك هنا..."
          className="flex-1 border border-gray-300 rounded-xl px-4 py-3 text-right focus:outline-none focus:ring-2 focus:ring-indigo-400"
          disabled={loading}
        />
        <button
          type="submit" disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl transition disabled:opacity-50"
        >
          إرسال
        </button>
      </form>
    </div>
  );
}
