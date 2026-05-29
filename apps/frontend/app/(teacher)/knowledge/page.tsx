"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import {
  createSource,
  confirmUpload,
  processSource,
  listSources,
  deleteSource,
  SourceRecord,
} from "@/lib/api-client";

const SOURCE_TYPES = [
  { value: "pdf", label: "PDF", icon: "📄", accept: ".pdf" },
  { value: "docx", label: "Word", icon: "📘", accept: ".docx" },
  { value: "pptx", label: "PowerPoint", icon: "📊", accept: ".pptx" },
  { value: "audio", label: "صوت", icon: "🎵", accept: "audio/*" },
  { value: "video", label: "فيديو", icon: "🎥", accept: "video/*" },
  { value: "youtube", label: "يوتيوب", icon: "🎬", accept: null },
  { value: "youtube_channel", label: "قناة", icon: "📺", accept: null },
];

const FILE_TYPES = ["pdf", "docx", "pptx", "audio", "video"];
const URL_TYPES = ["youtube", "youtube_channel"];

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
  draft: "bg-gray-100 text-gray-600",
};

function titleFromFile(file: File): string {
  return file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
}

function titleFromUrl(url: string): string {
  try {
    const u = new URL(url);
    const v = u.searchParams.get("v");
    if (v) return `يوتيوب: ${v}`;
    const parts = u.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1] || url;
  } catch {
    return url;
  }
}

export default function KnowledgePage() {
  const { token } = useAuth();
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [originalUrl, setOriginalUrl] = useState("");
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

  const hasActiveSources = sources.some((s) =>
    ["draft", "upload_pending", "uploaded", "processing"].includes(s.status)
  );

  useEffect(() => {
    fetchSources();
    const interval = setInterval(fetchSources, hasActiveSources ? 1000 : 5000);
    return () => clearInterval(interval);
  }, [fetchSources, hasActiveSources]);

  const resetForm = () => {
    setSelectedType(null);
    setSelectedFile(null);
    setOriginalUrl("");
    setUploadProgress("");
    setShowForm(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedType) return;
    setLoading(true);
    setUploadProgress("");

    try {
      const isFile = FILE_TYPES.includes(selectedType);
      const isUrl = URL_TYPES.includes(selectedType);

      const title = isFile && selectedFile
        ? titleFromFile(selectedFile)
        : isUrl && originalUrl
        ? titleFromUrl(originalUrl)
        : selectedType;

      const createPayload: any = { title, source_type: selectedType };
      if (isUrl) createPayload.original_url = originalUrl;

      const source = await createSource(createPayload, token);

      if (isFile && source.upload_url && selectedFile) {
        setUploadProgress("جاري رفع الملف...");
        const uploadRes = await fetch(source.upload_url, {
          method: "PUT",
          body: selectedFile,
        });
        if (!uploadRes.ok) throw new Error("فشل رفع الملف إلى التخزين السحابي");
        setUploadProgress("تم الرفع، جاري التأكيد...");
        await confirmUpload(source.source_id, token);
      }

      await processSource(source.source_id, token);
      setUploadProgress("تم إرسال المهمة بنجاح!");
      resetForm();
      await fetchSources();
    } catch (error: any) {
      setUploadProgress(`خطأ: ${error.message || "حدث خطأ غير متوقع"}`);
    } finally {
      setLoading(false);
    }
  };

  const currentType = SOURCE_TYPES.find((t) => t.value === selectedType);
  const isFile = selectedType ? FILE_TYPES.includes(selectedType) : false;
  const isUrl = selectedType ? URL_TYPES.includes(selectedType) : false;
  const canSubmit = selectedType && (
    (isFile && selectedFile) || (isUrl && originalUrl)
  );

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
            <form onSubmit={handleSubmit} className="space-y-4">

              {/* Type selector — icon buttons */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-2">
                  اختر نوع المصدر
                </label>
                <div className="flex flex-wrap gap-2">
                  {SOURCE_TYPES.map((type) => (
                    <button
                      key={type.value}
                      type="button"
                      onClick={() => {
                        setSelectedType(type.value);
                        setSelectedFile(null);
                        setOriginalUrl("");
                      }}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border
                        transition-colors ${
                          selectedType === type.value
                            ? "bg-indigo-600 text-white border-indigo-600"
                            : "bg-white text-gray-700 border-gray-300 hover:border-indigo-400"
                        }`}
                    >
                      <span>{type.icon}</span>
                      <span>{type.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* File picker */}
              {isFile && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">الملف</label>
                  <input
                    type="file"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
                    accept={currentType?.accept || undefined}
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
              {isUrl && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    {selectedType === "youtube_channel" ? "رابط القناة أو المعرّف" : "رابط يوتيوب"}
                  </label>
                  <input
                    type="url"
                    value={originalUrl}
                    onChange={(e) => setOriginalUrl(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg
                      focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                    placeholder={
                      selectedType === "youtube_channel"
                        ? "https://www.youtube.com/@channel"
                        : "https://www.youtube.com/watch?v=..."
                    }
                    required
                  />
                </div>
              )}

              {/* Submit row */}
              {selectedType && (
                <div className="flex items-center gap-3 pt-1">
                  <button
                    type="submit"
                    disabled={loading || !canSubmit}
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
              )}
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
                    <span className={`text-xs px-2 py-1 rounded-full font-medium
                      inline-flex items-center gap-1 ${
                        STATUS_COLORS[source.status] || "bg-gray-100 text-gray-600"
                      }`}>
                      {["draft", "processing", "upload_pending", "uploaded"].includes(
                        source.status
                      ) && (
                        <svg className="inline-block w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10"
                            stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor"
                            d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                        </svg>
                      )}
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
