import type { StageSummary } from "../../types/jobs";
import { stageLabel } from "../../utils/format";
import styles from "./SignalFlowBar.module.css";

const STAGES = ["download", "transcribe", "summarize"] as const;

interface SignalFlowBarProps {
  stages: Record<string, StageSummary>;
  orientation?: "horizontal" | "vertical";
  runningStage?: string | null;
}

function statusText(stage: StageSummary): string {
  if (stage.reused_existing) return "复用已有";
  switch (stage.status) {
    case "done":
      return "完成";
    case "failed":
      return stage.error_code ?? "失败";
    case "running":
      return "运行中";
    case "skipped":
      return "跳过";
    default:
      return "未开始";
  }
}

export function SignalFlowBar({
  stages,
  orientation = "horizontal",
  runningStage = null,
}: SignalFlowBarProps) {
  const flowClass = [styles.flow, orientation === "vertical" ? styles.vertical : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={flowClass} role="list" aria-label="Pipeline 阶段">
      {STAGES.map((key, index) => {
        const stage = stages[key] ?? { status: "idle", success: null };
        const effectiveStatus =
          runningStage === key && stage.status !== "done" && stage.status !== "failed"
            ? "running"
            : stage.status;
        const nodeClass = [styles.node, styles[effectiveStatus]].join(" ");

        return (
          <div key={key} role="listitem" style={{ display: "contents" }}>
            {index > 0 && <div className={styles.connector} aria-hidden />}
            <div className={nodeClass}>
              <div className={styles.nodeHeader}>
                <span className={styles.nodeTitle}>{stageLabel(key)}</span>
                <span className={styles.nodeStatus}>{statusText(stage)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
