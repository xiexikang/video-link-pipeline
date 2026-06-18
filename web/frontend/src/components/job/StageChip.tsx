import type { StageStatus } from "../../types/jobs";
import { stageLabel } from "../../utils/format";
import styles from "./StageChip.module.css";

interface StageChipProps {
  stageKey: string;
  status: StageStatus;
}

function statusIcon(status: StageStatus): string {
  switch (status) {
    case "done":
      return "✓";
    case "failed":
      return "×";
    case "running":
      return "●";
    case "skipped":
      return "—";
    default:
      return "—";
  }
}

export function StageChip({ stageKey, status }: StageChipProps) {
  return (
    <span className={`${styles.chip} ${styles[status]}`}>
      <span>{stageLabel(stageKey)}</span>
      <span className={styles.icon} aria-hidden>
        {statusIcon(status)}
      </span>
    </span>
  );
}
