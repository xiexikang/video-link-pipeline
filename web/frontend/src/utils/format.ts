const STAGE_LABELS: Record<string, string> = {
  download: "下载",
  transcribe: "转录",
  summarize: "摘要",
};

export function stageLabel(key: string): string {
  return STAGE_LABELS[key] ?? key;
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "时间未知";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;

  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  return `${days} 天前`;
}

export function runtimeLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    idle: "空闲",
  };
  return labels[status] ?? status;
}

export function sourceLabel(job: { source_url: string | null; source_path: string | null }): string {
  return job.source_url ?? job.source_path ?? "来源未知";
}
