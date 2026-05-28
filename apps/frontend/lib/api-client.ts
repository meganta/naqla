const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://naqla-api-dev-uagnx6q44q-ew.a.run.app";

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

export const api = {
  auth: {
    register: (data: { email: string; password: string; full_name: string; tenant_name: string }) =>
      request<{ access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    login: (data: { email: string; password: string }) =>
      request<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    me: (token: string) => request<{ id: string; email: string; full_name: string; role: string; tenant_id: string }>("/auth/me", {}, token),
  },
  ingestion: {
    createSource: (data: { title: string; source_type: string }, token: string) =>
      request<{ source_id: string; upload_url: string; file_path: string }>("/ingestion/sources", {
        method: "POST",
        body: JSON.stringify(data),
      }, token),
    listSources: (token: string) =>
      request<Array<{ id: string; title: string; source_type: string; status: string; created_at: string }>>("/ingestion/sources", {}, token),
    processSource: (sourceId: string, token: string) =>
      request<{ id: string; status: string }>(`/ingestion/sources/${sourceId}/process`, { method: "POST" }, token),
  },
  copilot: {
    chat: (data: { messages: Array<{ role: string; content: string }>; scope: string }, token: string) =>
      request<{ text: string; tokens_used: number; model: string; provider: string; source_scope: string; context_chunks_used: number }>("/copilot/chat", {
        method: "POST",
        body: JSON.stringify(data),
      }, token),
  },
};
