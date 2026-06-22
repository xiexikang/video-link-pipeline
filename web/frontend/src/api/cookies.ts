import { fetchJson } from "./client";

export interface CookieLoginStartResponse {
  session_id: string;
  cookie_file: string;
  message: string;
}

export interface CookieLoginExportResponse {
  cookie_file: string;
  message: string;
}

export function startCookieLogin(payload: {
  url: string;
  cookie_file?: string;
}): Promise<CookieLoginStartResponse> {
  return fetchJson<CookieLoginStartResponse>("/api/cookies/login/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function exportCookieLogin(sessionId: string): Promise<CookieLoginExportResponse> {
  return fetchJson<CookieLoginExportResponse>(`/api/cookies/login/${sessionId}/export`, {
    method: "POST",
  });
}

export async function cancelCookieLogin(sessionId: string): Promise<void> {
  await fetch(`/api/cookies/login/${sessionId}`, { method: "DELETE" });
}
