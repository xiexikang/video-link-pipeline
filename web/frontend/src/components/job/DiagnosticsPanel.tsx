import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./DiagnosticsPanel.module.css";

interface DiagnosticItem {
  code: string;
  hint?: string | null;
  message?: string | null;
  kind?: "error" | "warning";
}

interface DiagnosticsPanelProps {
  items: DiagnosticItem[];
}

export function DiagnosticsPanel({ items }: DiagnosticsPanelProps) {
  const hasAutoExpand = items.some((item) => item.kind === "error" || item.code);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (hasAutoExpand) {
      setOpen(true);
    }
  }, [hasAutoExpand]);

  if (items.length === 0) return null;

  return (
    <section className={styles.panel}>
      <button type="button" className={styles.toggle} onClick={() => setOpen((value) => !value)}>
        <span>诊断</span>
        <ChevronDown size={16} style={{ transform: open ? "rotate(180deg)" : undefined }} />
      </button>
      {open && (
        <div className={styles.body}>
          {items.map((item) => (
            <div
              key={`${item.code}-${item.message ?? ""}`}
              className={`${styles.item} ${item.kind === "warning" ? styles.warning : ""}`}
            >
              <div className={styles.code}>{item.code}</div>
              {(item.hint || item.message) && (
                <div className={styles.hint}>{item.hint ?? item.message}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
