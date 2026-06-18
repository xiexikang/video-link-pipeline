import type { RuntimeStatus } from "../../types/jobs";
import { runtimeLabel } from "../../utils/format";
import styles from "./Badge.module.css";

interface BadgeProps {
  status: RuntimeStatus | string;
}

export function Badge({ status }: BadgeProps) {
  const className = [styles.badge, styles[status as keyof typeof styles] ?? styles.idle].join(" ");
  return (
    <span className={className}>
      {status === "running" && <span className={styles.pulse} aria-hidden />}
      {runtimeLabel(status)}
    </span>
  );
}
