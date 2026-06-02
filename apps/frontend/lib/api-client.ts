const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://naqla-api-dev-uagnx6q44q-ew.a.run.app";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export interface SourceRecord {
  id: string;
  title: string;
  source_type: string;
  status: string;
  extra_meta: string | null;
  original_url: string | null;
  file_path: string | null;
  error_message: string | null;
  is_resumable?: boolean;
  created_at: string;
}

export interface JobRecord {
  id: string;
  source_id: string;
  status: string;
  chunks_created: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export const api = {
  google: {
    getAuthUrl: (token: string) =>
      request<{ auth_url: string }>("/auth/google", {}, token),
    getStatus: (token: string) =>
      request<{ connected: boolean }>("/auth/google/status", {}, token),
    disconnect: (token: string) =>
      request<{ disconnected: boolean }>("/auth/google", { method: "DELETE" }, token),
  },
  auth: {
    register: (data: {
      email: string;
      password: string;
      full_name: string;
      tenant_name: string;
    }) =>
      request<{ access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    login: (data: { email: string; password: string }) =>
      request<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    me: (token: string) =>
      request<{
        id: string;
        email: string;
        full_name: string;
        role: string;
        tenant_id: string;
      }>("/auth/me", {}, token),
  },
  ingestion: {
    createSource: (
      data: {
        title: string;
        source_type: string;
        original_url?: string;
        raw_text?: string;
      },
      token: string
    ) =>
      request<{ source_id: string; upload_url: string; file_path: string }>(
        "/ingestion/sources",
        { method: "POST", body: JSON.stringify(data) },
        token
      ),
    confirmUpload: (sourceId: string, token: string) =>
      request<{ source_id: string; status: string }>(
        `/ingestion/sources/${sourceId}/confirm-upload`,
        { method: "POST", body: JSON.stringify({}) },
        token
      ),
    listSources: (token: string) =>
      request<SourceRecord[]>("/ingestion/sources", {}, token),
    processSource: (sourceId: string, token: string) =>
      request<JobRecord>(
        `/ingestion/sources/${sourceId}/process`,
        { method: "POST" },
        token
      ),
    getLatestJob: (sourceId: string, token: string) =>
      request<JobRecord>(`/ingestion/sources/${sourceId}/job`, {}, token),
    getJob: (jobId: string, token: string) =>
      request<JobRecord>(`/ingestion/jobs/${jobId}`, {}, token),
    deleteSource: (sourceId: string, token: string) =>
      request<{ message: string }>(`/ingestion/sources/${sourceId}`, { method: "DELETE" }, token),
    updateSource: (sourceId: string, title: string, token: string) =>
      request<SourceRecord>(`/ingestion/sources/${sourceId}?title=${encodeURIComponent(title)}`, { method: "PATCH" }, token),
  },
  copilot: {
    chat: (
      data: {
        messages: Array<{ role: string; content: string }>;
        scope: string;
        task_type?: string;
      },
      token: string
    ) =>
      request<{
        text: string;
        tokens_used: number;
        model: string;
        provider: string;
        source_scope: string;
        context_chunks_used: number;
        insufficient_context: boolean;
        is_profile_complete: boolean;
        missing_profile_fields: string[];
        sources_used: { source_id: string; source_title: string; source_type: string; chunk_count: number }[];
      }>("/copilot/chat", { method: "POST", body: JSON.stringify(data) }, token),
  },
};


// Individual exports for direct import
export const createSource = api.ingestion.createSource;
export const confirmUpload = api.ingestion.confirmUpload;
export const processSource = api.ingestion.processSource;
export const listSources = api.ingestion.listSources;
export const getLatestJob = api.ingestion.getLatestJob;
export const getJob = api.ingestion.getJob;
export const deleteSource = api.ingestion.deleteSource;
export const updateSource = api.ingestion.updateSource;

export async function getSettings(token: string) {
  return request<{ youtube_channel_url: string | null; youtube_channel_id: string | null }>(
    "/settings",
    {},
    token
  );
}

export async function updateSettings(
  token: string,
  payload: Record<string, string | null>
) {
  return request<Record<string, string | null>>(
    "/settings",
    { method: "PUT", body: JSON.stringify(payload) },
    token
  );
}

export async function checkCopilotReady(token: string) {
  return request<{ ready: boolean; missing_fields: string[] }>(
    "/settings/copilot-ready",
    {},
    token
  );
}

export async function getChannelVideos(
  token: string,
  page_token?: string,
  per_page = 10
) {
  const params = new URLSearchParams({ per_page: String(per_page) });
  if (page_token) params.set("page_token", page_token);
  return request<{
    videos: {
      video_id: string;
      url: string;
      title: string;
      description: string;
      thumbnail: string | null;
      published_at: string;
      status: string | null;
    }[];
    next_page_token: string | null;
    prev_page_token: string | null;
    total_results: number;
  }>(`/ingestion/channel/videos?${params}`, {}, token);
}

export async function importChannelVideos(
  token: string,
  video_ids: string[],
  titles: Record<string, string> = {}
) {
  return request<{ imported: number; results: any[] }>(
    "/ingestion/channel/import",
    { method: "POST", body: JSON.stringify({ video_ids, titles }) },
    token
  );
}
