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
  },
  copilot: {
    chat: (
      data: {
        messages: Array<{ role: string; content: string }>;
        scope: string;
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
      }>("/copilot/chat", { method: "POST", body: JSON.stringify(data) }, token),
  },
};
