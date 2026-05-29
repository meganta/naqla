"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { getChannelVideos, importChannelVideos } from "@/lib/api-client";

interface Video {
  video_id: string;
  url: string;
  title: string;
  description: string;
  thumbnail: string | null;
  published_at: string;
  status: string | null;
}

interface Props {
  token: string;
  onClose: () => void;
  onImported: () => void;
}

const VIDEO_STATUS_LABELS: Record<string, string> = {
  processed: "في قاعدة المعرفة ✓",
  processing: "جاري المعالجة",
  failed: "فشل",
  uploaded: "تم الرفع",
  draft: "مسودة",
};

const VIDEO_STATUS_COLORS: Record<string, string> = {
  processed: "bg-green-100 text-green-700",
  processing: "bg-yellow-100 text-yellow-700",
  failed: "bg-red-100 text-red-700",
};

export function ChannelImportModal({ token, onClose, onImported }: Props) {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [prevPageToken, setPrevPageToken] = useState<string | null>(null);
  const [currentPageToken, setCurrentPageToken] = useState<string | undefined>(undefined);
  const [totalResults, setTotalResults] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);

  const fetchVideos = useCallback(async (pageToken?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getChannelVideos(token, pageToken, 10);
      setVideos(data.videos);
      setNextPageToken(data.next_page_token);
      setPrevPageToken(data.prev_page_token);
      setTotalResults(data.total_results);
      // Select all non-processed videos by default
      const newSelected = new Set(
        data.videos
          .filter((v) => v.status !== "processed")
          .map((v) => v.video_id)
      );
      setSelected(newSelected);
    } catch (e: any) {
      setError(e.message || "حدث خطأ أثناء جلب الفيديوهات");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  const toggleVideo = (videoId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(videoId)) next.delete(videoId);
      else next.add(videoId);
      return next;
    });
  };

  const toggleAll = () => {
    const nonProcessed = videos.filter((v) => v.status !== "processed").map((v) => v.video_id);
    if (nonProcessed.every((id) => selected.has(id))) {
      setSelected(new Set());
    } else {
      setSelected(new Set(nonProcessed));
    }
  };

  const handleImport = async () => {
    if (selected.size === 0) return;
    setImporting(true);
    setImportResult(null);
    try {
      const titlesMap: Record<string, string> = {};
    videos.forEach((v) => { if (selected.has(v.video_id)) titlesMap[v.video_id] = v.title; });
    const result = await importChannelVideos(token, Array.from(selected), titlesMap);
      setImportResult(`تم استيراد ${result.imported} فيديو بنجاح`);
      onImported();
      setTimeout(onClose, 2000);
    } catch (e: any) {
      setError(e.message || "حدث خطأ أثناء الاستيراد");
    } finally {
      setImporting(false);
    }
  };

  const handleNextPage = () => {
    if (nextPageToken) {
      setCurrentPageToken(nextPageToken);
      fetchVideos(nextPageToken);
    }
  };

  const handlePrevPage = () => {
    if (prevPageToken) {
      setCurrentPageToken(prevPageToken);
      fetchVideos(prevPageToken);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div dir="rtl" className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4
        max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-bold text-gray-900">استيراد من قناة يوتيوب</h2>
            {totalResults > 0 && (
              <p className="text-xs text-gray-400 mt-0.5">
                {totalResults} فيديو في القناة
              </p>
            )}
          </div>
          <button onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl font-light">✕</button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center justify-center py-16">
              <svg className="w-6 h-6 animate-spin text-indigo-600" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10"
                  stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor"
                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
            </div>
          )}

          {importResult && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4
              text-sm text-green-700 mb-4">
              {importResult}
            </div>
          )}

          {!loading && !error && videos.length > 0 && (
            <>
              {/* Select all */}
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100">
                <input
                  type="checkbox"
                  id="select-all"
                  checked={videos
                    .filter((v) => v.status !== "processed")
                    .every((v) => selected.has(v.video_id))}
                  onChange={toggleAll}
                  className="w-4 h-4 accent-indigo-600"
                />
                <label htmlFor="select-all" className="text-sm text-gray-600 cursor-pointer">
                  تحديد الكل ({selected.size} محدد)
                </label>
              </div>

              {/* Video list */}
              <div className="space-y-2">
                {videos.map((video) => {
                  const isProcessed = video.status === "processed";
                  const isSelected = selected.has(video.video_id);
                  return (
                    <div
                      key={video.video_id}
                      onClick={() => !isProcessed && toggleVideo(video.video_id)}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-colors
                        cursor-pointer ${
                          isProcessed
                            ? "border-gray-100 bg-gray-50 opacity-60 cursor-default"
                            : isSelected
                            ? "border-indigo-300 bg-indigo-50"
                            : "border-gray-200 hover:border-gray-300"
                        }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={isProcessed}
                        onChange={() => toggleVideo(video.video_id)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 accent-indigo-600 shrink-0"
                      />
                      {video.thumbnail && (
                        <Image
                          src={video.thumbnail}
                          alt={video.title}
                          width={80}
                          height={48}
                          className="object-cover rounded-lg shrink-0"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {video.title}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {new Date(video.published_at).toLocaleDateString("ar-SA")}
                        </p>
                      </div>
                      {video.status && (
                        <span className={`text-xs px-2 py-1 rounded-full shrink-0 ${
                          VIDEO_STATUS_COLORS[video.status] || "bg-gray-100 text-gray-600"
                        }`}>
                          {VIDEO_STATUS_LABELS[video.status] || video.status}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Pagination + Footer */}
        <div className="p-5 border-t border-gray-100 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevPage}
              disabled={!prevPageToken || loading}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg
                disabled:opacity-40 hover:bg-gray-50"
            >
              ← السابق
            </button>
            <button
              onClick={handleNextPage}
              disabled={!nextPageToken || loading}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg
                disabled:opacity-40 hover:bg-gray-50"
            >
              التالي →
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg">
              إلغاء
            </button>
            <button
              onClick={handleImport}
              disabled={importing || selected.size === 0}
              className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium
                hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {importing
                ? "جاري الاستيراد..."
                : `استيراد ${selected.size} فيديو`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
