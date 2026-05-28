"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import {
  createSource,
  confirmUpload,
  processSource,
  listSources,
  getLatestJob,
  deleteSource,
  updateSource,
  SourceRecord,
} from "@/lib/api-client";

const SOURCE_TYPES = [
  { value: "text", label: "نص يدوي", icon: "📝" },
  { value: "manual", label: "محتوى مخصص", icon: "✏️" },
  { value: "pdf", label: "ملف PDF", icon: "📄" },
  { value: "docx", label: "ملف Word", icon: "📘" },
  { value: "pptx", label: "ملف PowerPoint", icon: "📊" },
  { value: "youtube", label: "فيديو يوتيوب", icon: "🎬" },
  { value: "youtube_channel", label: "قناة يوتيوب", icon: "📺" },
  { value: "audio", label: "ملف صوتي", icon: "🎵" },
  { value: "video", label: "ملف فيديو", icon: "🎥" },
];

const UNSUPPORTED_TYPES = ["facebook", "instagram", "tiktok", "generic_url"];

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  upload_pending: "بانتظار الرفع",
  uploaded: "تم الرفع",
  processing: "جاري المعالجة",
  processed: "تمت المعالجة",
  failed: "فشل",
  unsupported: "غير مدعوم",
};

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: "بانتظار التنفيذ",
  processing: "جاري المعالجة",
  completed: "تمت بنجاح",
  failed: "فشل",
};

export default function KnowledgePage() {
  const { token } = useAuth();
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    source_type: "text",
    original_url: "",
    raw_text: "",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const [pollingJobs, setPollingJobs] = useState<Set<string>>(new Set());
  const [editingSource, setEditingSource] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const handleDelete = async (sourceId: string) => {
    if (!window.confirm("Delete this source? This cannot be undone.")) {
      return;
    }
    if (!token) return;
    try {
      await deleteSource(sourceId, token);
      await fetchSources();
    } catch (e: any) {
      alert("Delete failed: " + (e.message || "Unknown error"));
    }
  };

  const handleEdit = (sourceId: string, currentTitle: string) => {
    setEditingSource(sourceId);
    setEditTitle(currentTitle);
  };

  const handleSaveEdit = async (sourceId: string) => {
    if (!token) return;
    try {
      await updateSource(sourceId, editTitle, token);
      setEditingSource(null);
      setEditTitle("");
      await fetchSources();
    } catch (e: any) {
      alert("Update failed: " + (e.message || "Unknown error"));
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
    if (!token) {
      setUploadProgress("يجب تسجيل الدخول أولاً");
      return;
    }
    setLoading(true);
    setUploadProgress("");

    try {
      const isFileType = ["pdf", "docx", "pptx", "audio", "video"].includes(
        formData.source_type
      );
      const isTextType = ["text", "manual"].includes(formData.source_type);
      const isUrlType = ["youtube", "youtube_channel"].includes(
        formData.source_type
      );

      // Step 1: Create source
      const createPayload: any = {
        title: formData.title,
        source_type: formData.source_type,
      };

      if (isTextType) {
        createPayload.raw_text = formData.raw_text;
      } else if (isUrlType) {
        createPayload.original_url = formData.original_url;
      }

      const source = await createSource(createPayload, token);

      // Step 2: Upload file if needed
      if (isFileType && source.upload_url && selectedFile) {
        setUploadProgress("جاري رفع الملف...");
        const uploadRes = await fetch(source.upload_url, {
          method: "PUT",
          headers: {
            "Content-Type": "application/octet-stream",
          },
          body: selectedFile,
        });

        if (!uploadRes.ok) {
          throw new Error("فشل رفع الملف إلى التخزين السحابي");
        }

        setUploadProgress("تم الرفع، جاري التأكيد...");
        await confirmUpload(source.source_id, token);
        setUploadProgress("تم التأكيد، جاري المعالجة...");
      } else if (isTextType) {
        setUploadProgress("جاري معالجة النص...");
      } else if (isUrlType) {
        setUploadProgress("جاري معالجة الرابط...");
      }

      // Step 3: Process source
      await processSource(source.source_id, token);
      setUploadProgress("تم إرسال المهمة بنجاح!");

      // Start polling
      setPollingJobs((prev) => new Set(prev).add(source.source_id));

      // Reset form
      setFormData({ title: "", source_type: "text", original_url: "", raw_text: "" });
      setSelectedFile(null);

      // Refresh list
      await fetchSources();
    } catch (error: any) {
      setUploadProgress(`خطأ: ${error.message || "حدث خطأ غير متوقع"}`);
    } finally {
      setLoading(false);
    }
  };

  const getJobForSource = (sourceId: string) => {
    // Jobs are fetched with sources via polling
    return null;
  };

  return (
    <div dir="rtl" className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8 text-center">
          مصادر المعرفة
        </h1>

        {/* Create Source Form */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            إضافة مصدر جديد
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                العنوان
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) =>
                  setFormData({ ...formData, title: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="أدخل عنوان المصدر"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                نوع المصدر
              </label>
              <select
                value={formData.source_type}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    source_type: e.target.value,
                    original_url: "",
                    raw_text: "",
                  })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {SOURCE_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.icon} {type.label}
                  </option>
                ))}
              </select>
            </div>

            {/* File upload for file types */}
            {["pdf", "docx", "pptx", "audio", "video"].includes(
              formData.source_type
            ) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  اختيار الملف
                </label>
                <input
                  type="file"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  accept={
                    formData.source_type === "pdf"
                      ? ".pdf"
                      : formData.source_type === "docx"
                      ? ".docx"
                      : formData.source_type === "pptx"
                      ? ".pptx"
                      : formData.source_type === "audio"
                      ? "audio/*"
                      : "video/*"
                  }
                  required
                />
                {selectedFile && (
                  <p className="text-sm text-gray-500 mt-1">
                    الملف المختار: {selectedFile.name} (
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} ميجابايت)
                  </p>
                )}
              </div>
            )}

            {/* Text area for text/manual */}
            {["text", "manual"].includes(formData.source_type) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  المحتوى النصي
                </label>
                <textarea
                  value={formData.raw_text}
                  onChange={(e) =>
                    setFormData({ ...formData, raw_text: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent h-32"
                  placeholder="أدخل النص العربي هنا..."
                  required
                />
              </div>
            )}

            {/* URL input for YouTube */}
            {["youtube", "youtube_channel"].includes(formData.source_type) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  رابط يوتيوب
                </label>
                <input
                  type="url"
                  value={formData.original_url}
                  onChange={(e) =>
                    setFormData({ ...formData, original_url: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="https://www.youtube.com/watch?v=..."
                  required
                />
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "جاري المعالجة..." : "إضافة المصدر"}
            </button>

            {uploadProgress && (
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm text-blue-800">{uploadProgress}</p>
              </div>
            )}
          </form>
        </div>

        {/* Sources List */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            المصادر المضافة
          </h2>

          {sources.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              لا توجد مصادر مضافة بعد
            </p>
          ) : (
            <div className="space-y-4">
              {sources.map((source) => (
                <div
                  key={source.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {source.title}
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        النوع: {SOURCE_TYPES.find((t) => t.value === source.source_type)?.label || source.source_type}
                      </p>
                      <p className="text-sm text-gray-500">
                        الحالة:{" "}
                        <span
                          className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                            source.status === "processed"
                              ? "bg-green-100 text-green-800"
                              : source.status === "failed"
                              ? "bg-red-100 text-red-800"
                              : source.status === "processing"
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {STATUS_LABELS[source.status] || source.status}
                        </span>
                      </p>
                      {source.original_url && (
                        <p className="text-sm text-gray-500 truncate max-w-md">
                          الرابط: {source.original_url}
                        </p>
                      )}
                      {source.file_path && (
                        <p className="text-sm text-gray-500 truncate max-w-md">
                          الملف: {source.file_path}
                        </p>
                      )}
                    </div>
                    <div className="text-left">
                      <p className="text-xs text-gray-400">
                        {new Date(source.created_at).toLocaleDateString("ar-SA")}
                      </p>
                      <div className="mt-2 flex gap-2">
                        {editingSource === source.id ? (
                          <>
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              className="px-2 py-1 text-sm border border-gray-300 rounded"
                            />
                            <button
                              onClick={() => handleSaveEdit(source.id)}
                              className="px-2 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                            >
                              حفظ
                            </button>
                            <button
                              onClick={() => { setEditingSource(null); setEditTitle(""); }}
                              className="px-2 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600"
                            >
                              إلغاء
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => handleEdit(source.id, source.title)}
                              className="px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                            >
                              تعديل
                            </button>
                            <button
                              onClick={() => handleDelete(source.id)}
                              className="px-2 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                            >
                              حذف
                            </button>
                          </>
                        )}
                      </div>
                    </div>
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
