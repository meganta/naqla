"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import {
  createSource,
  confirmUpload,
  processSource,
  listSources,
  deleteSource,
  updateSource,
  SourceRecord,
} from "@/lib/api-client";

const SOURCE_TYPES = [
  { value: "pdf", label: "ملف PDF", icon: "📄" },
  { value: "docx", label: "ملف Word", icon: "📘" },
  { value: "pptx", label: "ملف PowerPoint", icon: "📊" },
  { value: "youtube", label: "فيديو يوتيوب", icon: "🎬" },
  { value: "youtube_channel", label: "قناة يوتيوب", icon: "📺" },
  { value: "audio", label: "ملف صوتي", icon: "🎵" },
  { value: "video", label: "ملف فيديو", icon: "🎥" },
];

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  upload_pending: "بانتظار الرفع",
  uploaded: "تم الرفع",
  processing: "جاري المعالجة",
  processed: "تمت المعالجة",
  failed: "فشل",
  unsupported: "غير مدعوم",
};

const STATUS_COLORS: Record<string, string> = {
  processed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  processing: "bg-yellow-100 text-yellow-800",
  upload_pending: "bg-blue-100 text-blue-800",
  uploaded: "bg-blue-100 text-blue-800",
};

export default function KnowledgePage() {
  const { token } = useAuth();
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    source_type: "pdf",
    original_url: "",
    raw_text: "",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string>("");

  const handleDelete = async (sourceId: string) => {
    if (!window.confirm("هل تريد حذف هذا المصدر؟ لا يمكن التراجع عن هذا الإجراء.")) return;
    if (!token) return;
    try {
      await deleteSource(sourceId, token);
      await fetchSources();
    } catch (e: any) {
      alert("فشل الحذف: " + (e.message || "خطأ غير معروف"));
    }
  };

  const fetchSources = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listSources(token);
      setSources(data);
    } catch (e) {
      console.error("Failed to fetch sources:", e);
    }
  }, []);

  useEffect(() => {
    fetchSources();
    const interval = setInterval(fetchSources, 5000);
    return () => clearInterval(interval);
  }, [fetchSources]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) { setUploadProgress("يجب تسجيل الدخول أولاً"); return; }
    setLoading(true);
    setUploadProgress("");
    try {
      const isFileType = ["pdf", "docx", "pptx", "audio", "video"].includes(formData.source_type);
      const isUrlType = ["youtube", "youtube_channel"].includes(formData.source_type);
      const createPayload: any = { title: formData.title, source_type: formData.source_type };
      if (isUrlType) createPayload.original_url = formData.original_url;

      const source = await createSource(createPayload, token);

      if (isFileType && source.upload_url && selectedFile) {
        setUploadProgress("جاري رفع الملف...");
        const uploadRes = await fetch(source.upload_url, {
          method: "PUT",
          headers: { "Content-Type": "application/octet-stream" },
          body: selectedFile,
        });
        if (!uploadRes.ok) throw new Error("فشل رفع الملف إلى التخزين السحابي");
        setUploadProgress("تم الرفع، جاري التأكيد...");
        await confirmUpload(source.source_id, token);
      }

      await processSource(source.source_id, token);
      setUploadProgress("تم إرسال المهمة بنجاح!");
      setFormData({ title: "", source_type: "pdf", original_url: "", raw_text: "" });
      setSelectedFile(null);
      setShowForm(false);
      await fetchSources();
    } catch (error: any) {
      setUploadProgress(`خطأ: ${error.message || "حدث خطأ غير متوقع"}`);
    } finally {
      setLoading(false);
    }
  };

  const isFileType = ["pdf", "docx", "pptx", "audio", "video"].includes(formData.source_type);
  const isUrlType = ["youtube", "youtube_channel"].includes(formData.source_type);

  return (
    <div dir="rtl" className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">مصادر المعرفة</h1>
          <button
            onClick={() => { setShowForm(!showForm); setUploadProgress(""); }}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg
              hover:bg-indigo-700 text-sm font-medium"
          >
            <span>{showForm ? "✕" : "+"}</span>
            <span>{showForm ? "إلغاء" : "إضافة مصدر"}</span>
          </button>
        </div>

        {/* Collapsible Form */}
        {showForm && (
          <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
            <form onSubmit={handleSubmit} className="space-y-3">
              {/* Title + Type in one row */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 mb-1">العنوان</label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg
                      focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                    placeholder="عنوان المصدر"
                    required
                  />
                </div>
                <div className="w-48">
                  <label className="block text-xs font-medium text-gray-600 mb-1">النوع</label>
                  <select
                    value={formData.source_type}
                    onChange={(e) => setFormData({
                      ...formData, source_type: e.target.value, original_url: "", raw_text: "",
                    })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg
                      focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                  >
                    {SOURCE_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.icon} {type.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* File upload */}
              {isFileType && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">الملف</label>
                  <input
                    type="file"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                    accept={
                      formData.source_type === "pdf" ? ".pdf" :
                      formData.source_type === "docx" ? ".docx" :
                      formData.source_type === "pptx" ? ".pptx" :
                      formData.source_type === "audio" ? "audio/*" : "video/*"
                    }
                    required
                  />
                  {selectedFile && (
                    <p className="text-xs text-gray-400 mt-1">
                      {selectedFile.name} — {(selectedFile.size / 1024 / 1024).toFixed(2)} ميجابايت
                    </p>
                  )}
                </div>
              )}

              {/* URL input */}
              {isUrlType && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">رابط يوتيوب</label>
                  <input
                    type="url"
                    value={formData.original_url}
                    onChange={(e) => setFormData({ ...formData, original_url: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg
                      focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                    placeholder="https://www.youtube.com/watch?v=..."
                    required
                  />
                </div>
              )}

              {/* Submit row */}
              <div className="flex items-center gap-3 pt-1">
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                    hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "جاري المعالجة..." : "إضافة"}
                </button>
                {uploadProgress && (
                  <p className={`text-sm ${
                    uploadProgress.startsWith("خطأ") ? "text-red-600" : "text-indigo-600"
                  }`}>
                    {uploadProgress}
                  </p>
                )}
              </div>
            </form>
          </div>
        )}

        {/* Sources List */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-gray-800 mb-4">
            المصادر المضافة
            {sources.length > 0 && (
              <span className="mr-2 text-xs font-normal text-gray-400">({sources.length})</span>
            )}
          </h2>

          {sources.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">لا توجد مصادر مضافة بعد</p>
          ) : (
            <div className="space-y-2">
              {sources.map((source) => (
                <div
                  key={source.id}
                  className="flex items-center justify-between border border-gray-100
                    rounded-lg px-4 py-3 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-lg">
                      {SOURCE_TYPES.find((t) => t.value === source.source_type)?.icon || "📁"}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{source.title}</p>
                      {source.original_url && (
                        <p className="text-xs text-gray-400 truncate max-w-xs">{source.original_url}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                      STATUS_COLORS[source.status] || "bg-gray-100 text-gray-600"
                    }`}>
                      {STATUS_LABELS[source.status] || source.status}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(source.created_at).toLocaleDateString("ar-SA")}
                    </span>
                    <button
                      onClick={() => handleDelete(source.id)}
                      className="text-xs text-red-500 hover:text-red-700 px-2 py-1
                        rounded hover:bg-red-50 transition-colors"
                    >
                      حذف
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
