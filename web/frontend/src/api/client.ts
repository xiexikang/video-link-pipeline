const API_OFFLINE_MESSAGE =
  "无法连接 API 服务，请运行 scripts/dev-web.ps1 启动后端（127.0.0.1:8765）";

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error(API_OFFLINE_MESSAGE);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const payload = await fetchJson<{ status: string }>("/health");
    return payload.status === "ok";
  } catch {
    return false;
  }
}
