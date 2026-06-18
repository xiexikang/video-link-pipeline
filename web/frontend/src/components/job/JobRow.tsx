import { Link } from "react-router-dom";
import type { JobListItem } from "../../types/jobs";
import { formatRelativeTime, sourceLabel } from "../../utils/format";
import { Badge } from "../ui/Badge";
import { StageChip } from "./StageChip";
import styles from "./JobRow.module.css";

const STAGES = ["download", "transcribe", "summarize"] as const;

interface JobRowProps {
  job: JobListItem;
  refreshing?: boolean;
}

function StatusBar({ status }: { status: string }) {
  const barClass = [styles.bar, styles[status as keyof typeof styles] ?? styles.idle].join(" ");
  return <div className={barClass} aria-hidden />;
}

function cardBorderClass(status: string): string {
  const map: Record<string, string> = {
    queued: styles.cardQueued,
    running: styles.cardRunning,
    succeeded: styles.cardSucceeded,
    failed: styles.cardFailed,
    idle: styles.cardIdle,
  };
  return map[status] ?? styles.cardIdle;
}

function JobContent({ job }: { job: JobListItem }) {
  return (
    <>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>{job.title}</div>
          <div className={`${styles.meta} mono`}>{sourceLabel(job)}</div>
        </div>
        <Badge status={job.runtime_status} />
      </div>
      <div className={styles.chips}>
        {STAGES.map((key) => (
          <StageChip key={key} stageKey={key} status={job.stages[key]?.status ?? "idle"} />
        ))}
      </div>
      <div className={styles.meta}>{formatRelativeTime(job.updated_at)}</div>
    </>
  );
}

export function JobRow({ job, refreshing = false }: JobRowProps) {
  const stateClass = refreshing ? styles.refreshing : "";

  return (
    <>
      <Link to={`/jobs/${job.id}`} className={`${styles.row} ${stateClass}`}>
        <StatusBar status={job.runtime_status} />
        <div>
          <div className={styles.title}>{job.title}</div>
          <div className={`${styles.meta} mono`}>{sourceLabel(job)}</div>
          <div className={styles.chips}>
            {STAGES.map((key) => (
              <StageChip key={key} stageKey={key} status={job.stages[key]?.status ?? "idle"} />
            ))}
          </div>
        </div>
        <div className={styles.desktopMeta}>
          <Badge status={job.runtime_status} />
          <div>{formatRelativeTime(job.updated_at)}</div>
        </div>
      </Link>

      <Link
        to={`/jobs/${job.id}`}
        className={`${styles.card} ${cardBorderClass(job.runtime_status)} ${stateClass}`}
      >
        <JobContent job={job} />
      </Link>
    </>
  );
}
