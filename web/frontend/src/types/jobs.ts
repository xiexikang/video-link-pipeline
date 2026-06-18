export type StageStatus = "idle" | "running" | "done" | "failed" | "skipped";
export type RuntimeStatus = "queued" | "running" | "succeeded" | "failed" | "idle";

export interface StageSummary {
  status: StageStatus;
  success: boolean | null;
  reused_existing?: boolean | null;
  error_code?: string | null;
  hint?: string | null;
}

export interface JobListItem {
  id: string;
  job_dir: string;
  title: string;
  source_url: string | null;
  source_path: string | null;
  command: string | null;
  updated_at: string | null;
  stages: Record<string, StageSummary>;
  runtime_status: RuntimeStatus;
}

export interface JobListResponse {
  jobs: JobListItem[];
  total: number;
}

export interface JobDetailResponse {
  id: string;
  job_dir: string;
  manifest: Record<string, unknown>;
  stages: Record<string, StageSummary>;
  runtime_status: RuntimeStatus;
  log?: string | null;
}

export interface DoctorCheck {
  name: string;
  ok: boolean;
  detail: string;
  section: string;
  code: string | null;
  hint: string | null;
}

export interface DoctorResponse {
  checks: DoctorCheck[];
  output_dir: string;
  config_source: string | null;
}

export interface CreateJobResponse {
  id: string;
  job_dir: string | null;
  runtime_status: RuntimeStatus;
  message: string;
}

export interface ArtifactPreview {
  artifact_key: string;
  kind: "text" | "markdown" | "json" | "subtitle" | "media";
  content: string | null;
  filename: string | null;
  media_url: string | null;
}

export type PreviewTabId = "transcript" | "summary" | "subtitle" | "media" | "keywords";

export const PREVIEW_TABS: { id: PreviewTabId; label: string; keys: string[] }[] = [
  { id: "transcript", label: "transcript", keys: ["transcript_txt"] },
  { id: "summary", label: "summary", keys: ["summary_md"] },
  { id: "subtitle", label: "subtitle", keys: ["subtitle_srt", "subtitle_vtt"] },
  { id: "media", label: "media", keys: ["video", "audio"] },
  { id: "keywords", label: "keywords", keys: ["keywords_json"] },
];
