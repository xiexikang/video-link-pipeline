import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchJson } from "../api/client";
import { ArtifactPreview } from "../components/job/ArtifactPreview";
import { DiagnosticsPanel } from "../components/job/DiagnosticsPanel";
import { SignalFlowBar } from "../components/job/SignalFlowBar";
import { Badge } from "../components/ui/Badge";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { JobDetailResponse, StageSummary } from "../types/jobs";
import { sourceLabel } from "../utils/format";
import styles from "./pages.module.css";

function collectDiagnostics(manifest: Record<string, unknown>) {
  const items: { code: string; hint?: string | null; message?: string | null; kind?: "error" | "warning" }[] =
    [];
  const execution = manifest.execution;
  if (!execution || typeof execution !== "object") return items;

  const download = (execution as Record<string, unknown>).download;
  if (download && typeof download === "object") {
    const block = download as Record<string, unknown>;
    if (typeof block.error_code === "string") {
      items.push({
        code: block.error_code,
        hint: typeof block.hint === "string" ? block.hint : null,
        kind: "error",
      });
    }
    const warnings = block.warning_details;
    if (Array.isArray(warnings)) {
      for (const warning of warnings) {
        if (!warning || typeof warning !== "object") continue;
        const record = warning as Record<string, unknown>;
        if (typeof record.code === "string") {
          items.push({
            code: record.code,
            message: typeof record.message === "string" ? record.message : null,
            hint: typeof record.description === "string" ? record.description : null,
            kind: "warning",
          });
        }
      }
    }
  }

  for (const stage of ["transcribe", "summarize"]) {
    const block = (execution as Record<string, unknown>)[stage];
    if (block && typeof block === "object") {
      const record = block as Record<string, unknown>;
      if (typeof record.error_code === "string") {
        items.push({
          code: record.error_code,
          hint: typeof record.hint === "string" ? record.hint : null,
          kind: "error",
        });
      }
    }
  }

  return items;
}

function detectRunningStage(
  runtimeStatus: string,
  stages: Record<string, StageSummary>,
): string | null {
  if (runtimeStatus !== "running" && runtimeStatus !== "queued") return null;
  const order = ["download", "transcribe", "summarize"];
  for (const stage of order) {
    const status = stages[stage]?.status;
    if (status === "idle" || status === "running") return stage;
  }
  return "download";
}

export function JobDetail() {
  const { id } = useParams();
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [detail, setDetail] = useState<JobDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [configOpen, setConfigOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(true);

  useEffect(() => {
    if (!id) return;
    let active = true;

    const load = async () => {
      try {
        const payload = await fetchJson<JobDetailResponse>(`/api/jobs/${id}`);
        if (!active) return;
        setDetail(payload);
        setError(null);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [id]);

  const diagnostics = useMemo(
    () => (detail ? collectDiagnostics(detail.manifest) : []),
    [detail],
  );

  const artifactMap = useMemo(() => {
    const artifacts = detail?.manifest.artifacts;
    if (!artifacts || typeof artifacts !== "object") return {} as Record<string, string>;
    return Object.fromEntries(
      Object.entries(artifacts as Record<string, unknown>).filter(
        ([key, value]) => key !== "folder" && typeof value === "string" && value,
      ),
    ) as Record<string, string>;
  }, [detail]);

  const runningStage = detail
    ? detectRunningStage(detail.runtime_status, detail.stages)
    : null;

  if (loading) return <div className={styles.previewPlaceholder}>加载任务详情…</div>;
  if (error || !detail) return <div className={styles.error}>无法加载任务：{error ?? "未找到"}</div>;

  const input = detail.manifest.input as Record<string, unknown> | undefined;
  const source = sourceLabel({
    source_url: typeof input?.url === "string" ? input.url : null,
    source_path: typeof input?.input_path === "string" ? input.input_path : null,
  });

  const title = detail.job_dir ? detail.job_dir.split("/").pop() : "任务";

  return (
    <section>
      <header className={styles.detailHeader}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h2 className="display-sm" style={{ margin: 0 }}>
            {title}
          </h2>
          <Badge status={detail.runtime_status} />
        </div>
        {typeof input?.url === "string" ? (
          <a className={`${styles.sourceLink} mono`} href={input.url} target="_blank" rel="noreferrer">
            {source}
          </a>
        ) : (
          <div className={`${styles.sourceLink} mono`}>{source}</div>
        )}
        <div className="caption" style={{ marginTop: 8 }}>
          {typeof detail.manifest.command === "string" ? detail.manifest.command : "未知命令"}
          {detail.job_dir ? (
            <>
              {" "}
              · <span className="mono">{detail.job_dir}</span>
            </>
          ) : null}
        </div>
      </header>

      <SignalFlowBar
        stages={detail.stages}
        orientation={isDesktop ? "horizontal" : "vertical"}
        runningStage={runningStage}
      />

      {(detail.runtime_status === "running" || detail.runtime_status === "queued") && (
        <div className={`${styles.pollingNote} caption`}>每 4 秒更新</div>
      )}

      <DiagnosticsPanel items={diagnostics} />

      <section className={styles.configFold}>
        <button type="button" className={styles.configToggle} onClick={() => setLogOpen((v) => !v)}>
          执行日志
          {detail.runtime_status === "running" || detail.runtime_status === "queued" ? "（实时）" : ""}
        </button>
        {logOpen && (
          <div className={styles.configBody}>
            {detail.log ? (
              <pre>{detail.log}</pre>
            ) : (
              <div className={styles.previewPlaceholder}>
                {detail.runtime_status === "running" || detail.runtime_status === "queued"
                  ? "任务运行中，日志即将出现…"
                  : "暂无执行日志。"}
              </div>
            )}
          </div>
        )}
      </section>

      <section className={styles.artifacts}>
        <div className={styles.artifactList}>
          <div className="caption" style={{ marginBottom: 8 }}>
            产物路径
          </div>
          {Object.keys(artifactMap).length === 0 ? (
            <div className={styles.previewPlaceholder}>还没有可用产物。</div>
          ) : (
            Object.entries(artifactMap).map(([key, path]) => (
              <div key={key} className={styles.artifactItem} style={{ cursor: "default" }}>
                <div>{key}</div>
                <div className="mono" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                  {path}
                </div>
              </div>
            ))
          )}
        </div>
        <div className={styles.previewPanel}>
          <div className="caption" style={{ marginBottom: 8 }}>
            预览
          </div>
          {id ? <ArtifactPreview jobId={id} artifacts={artifactMap} /> : null}
        </div>
      </section>

      <section className={styles.configFold}>
        <button type="button" className={styles.configToggle} onClick={() => setConfigOpen((v) => !v)}>
          config_effective
        </button>
        {configOpen && (
          <div className={styles.configBody}>
            <pre>{JSON.stringify(detail.manifest.config_effective ?? {}, null, 2)}</pre>
          </div>
        )}
      </section>

      <p className="caption" style={{ marginTop: 16 }}>
        <Link to="/" style={{ color: "var(--vlp-accent)" }}>
          返回看板
        </Link>
      </p>
    </section>
  );
}
