"use client";
import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api-client";

interface Source {
  id: string;
  title: string;
  source_type: string;
  status: string;
  created_at: string;
}

const SOURCE_TYPES = [
  { value: "pdf", label: "ملف PDF" },
  { value: "docx", label: "ملف Word" },
  { value: "text", label: "نص مكتوب" },
  { value: "manual", label: "إدخال يدوي" },
];

const STATUS_LABELS: Record<string, string> = {
  pending: "في الانتظار",
  queued: "في الطابور",
  processing: "جارٍ المعالجة",
  processed: "تمت المعالجة",
  failed: "فشل",
};

export default function KnowledgePage() {
  const { token } = useAuth();
  const [sources, setSources] = useState<Source[]>([]);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("pdf");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (token) api.ingestion.listSources(token).then(setSources);
  }, [token]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setLoading(true); setMessage("");
    try {
      const res = await api.ingestion.createSource({ title, source_type: sourceType }, token);
      setMessage(`تم إنشاء المصدر. رابط الرفع جاهز للاستخدام.`);
      setTitle("");
      const updated = await api.ingestion.listSources(token);
      setSources(updated);
      if (res.source_id && sourceType !== "manual") {
        await api.ingestion.processSource(res.source_id, token);
      }
    } catch {
      setMessage("حدث خطأ أثناء إنشاء المصدر.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">مصادر المعرفة</h2>
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h3 className="text-lg font-medium text-gray-700 mb-4">إضافة مصدر جديد</h3>
        <form onSubmit={handleCreate} className="flex gap-4 flex-wrap">
          <input
            value={title} onChange={e => setTitle(e.target.value)}
            placeholder="عنوان المصدر" required
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-right focus:outline-none focus:ring-2 focus:ring-indigo-400 min-w-48"
          />
          <select
            value={sourceType} onChange={e => setSourceType(e.target.value)}
            className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {SOURCE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <button
            type="submit" disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg transition disabled:opacity-50"
          >
            {loading ? "جارٍ الإضافة..." : "إضافة"}
          </button>
        </form>
        {message && <p className="mt-3 text-sm text-green-600">{message}</p>}
      </div>
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-6 border-b border-gray-100">
          <h3 className="text-lg font-medium text-gray-700">المصادر المضافة</h3>
        </div>
        {sources.length === 0 ? (
          <div className="p-12 text-center text-gray-400">لا توجد مصادر بعد</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-right px-6 py-3 text-gray-500 font-medium">العنوان</th>
                <th className="text-right px-6 py-3 text-gray-500 font-medium">النوع</th>
                <th className="text-right px-6 py-3 text-gray-500 font-medium">الحالة</th>
                <th className="text-right px-6 py-3 text-gray-500 font-medium">التاريخ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sources.map(s => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-800">{s.title}</td>
                  <td className="px-6 py-4 text-gray-500">{s.source_type}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      s.status === "processed" ? "bg-green-100 text-green-700" :
                      s.status === "failed" ? "bg-red-100 text-red-700" :
                      "bg-yellow-100 text-yellow-700"
                    }`}>
                      {STATUS_LABELS[s.status] || s.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-400">{new Date(s.created_at).toLocaleDateString("ar-EG")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
