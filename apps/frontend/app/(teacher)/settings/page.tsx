"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { getSettings, updateSettings } from "@/lib/api-client";

export default function SettingsPage() {
  const { token, user } = useAuth();
  const [channelUrl, setChannelUrl] = useState("");
  const [savedChannelId, setSavedChannelId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  useEffect(() => {
    if (!token) return;
    getSettings(token)
      .then((s) => {
        setChannelUrl(s.youtube_channel_url || "");
        setSavedChannelId(s.youtube_channel_id || null);
      })
      .catch(console.error)
      .finally(() => setFetching(false));
  }, [token]);

  const handleSave = async () => {
    if (!token) return;
    setLoading(true);
    setMessage(null);
    try {
      const s = await updateSettings(token, channelUrl || null);
      setSavedChannelId(s.youtube_channel_id || null);
      setMessage({ text: "تم الحفظ بنجاح", error: false });
    } catch (e: any) {
      setMessage({ text: e.message || "حدث خطأ", error: true });
    } finally {
      setLoading(false);
    }
  };

  if (fetching) return (
    <div dir="rtl" className="flex items-center justify-center min-h-screen">
      <p className="text-gray-400">جاري التحميل...</p>
    </div>
  );

  return (
    <div dir="rtl" className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">الإعدادات</h1>

      {/* Profile */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-800 mb-4">الملف الشخصي</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">الاسم</label>
            <p className="text-sm text-gray-900">{user?.full_name}</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              البريد الإلكتروني
            </label>
            <p className="text-sm text-gray-900">{user?.email}</p>
          </div>
        </div>
      </div>

      {/* YouTube Channel */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-1">قناة يوتيوب</h2>
        <p className="text-xs text-gray-400 mb-4">
          أضف رابط قناتك على يوتيوب لاستيراد الفيديوهات إلى قاعدة المعرفة
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">رابط القناة</label>
            <input
              type="url"
              value={channelUrl}
              onChange={(e) => setChannelUrl(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg
                focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              placeholder="https://www.youtube.com/@channelname"
            />
          </div>
          {savedChannelId && (
            <p className="text-xs text-green-600">
              ✓ القناة المحفوظة: {savedChannelId}
            </p>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={loading}
              className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? "جاري الحفظ..." : "حفظ"}
            </button>
            {message && (
              <p className={`text-sm ${message.error ? "text-red-600" : "text-green-600"}`}>
                {message.text}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
