import { fetchJson } from "./client";
import type { CreateJobResponse } from "../types/jobs";

export interface CreateJobPayload {
  type: string;
  url?: string;
  input_path?: string;
  options?: Record<string, unknown>;
}

export function createJob(payload: CreateJobPayload): Promise<CreateJobResponse> {
  return fetchJson<CreateJobResponse>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
