import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { fetchJson } from "../../api/client";
import type { ArtifactPreview as ArtifactPreviewData, PreviewTabId } from "../../types/jobs";
import { PREVIEW_TABS } from "../../types/jobs";
import styles from "./ArtifactPreview.module.css";

interface ArtifactPreviewProps {
  jobId: string;
  artifacts: Record<string, string>;
}

function resolveTabKey(tabId: PreviewTabId, artifacts: Record<string, string>): string | null {
  const tab = PREVIEW_TABS.find((item) => item.id === tabId);
  if (!tab) return null;
  return tab.keys.find((key) => artifacts[key]) ?? null;
}

function emptyMessage(tabId: PreviewTabId): string {
  const messages: Record<PreviewTabId, string> = {
    transcript: "还没有 transcript。转录完成后会出现在这里。",
    summary: "还没有 summary。摘要完成后会出现在这里。",
    subtitle: "还没有字幕文件。",
    media: "还没有可播放的媒体文件。",
    keywords: "还没有 keywords.json。",
  };
  return messages[tabId];
}

export function ArtifactPreview({ jobId, artifacts }: ArtifactPreviewProps) {
  const availableTabs = useMemo(
    () =>
      PREVIEW_TABS.filter((tab) => tab.keys.some((key) => Boolean(artifacts[key]))),
    [artifacts],
  );

  const [activeTab, setActiveTab] = useState<PreviewTabId>("transcript");
  const [preview, setPreview] = useState<ArtifactPreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (availableTabs.length === 0) return;
    if (!availableTabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(availableTabs[0].id);
    }
  }, [availableTabs, activeTab]);

  const activeKey = resolveTabKey(activeTab, artifacts);

  useEffect(() => {
    if (!activeKey) {
      setPreview(null);
      setError(null);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    void fetchJson<ArtifactPreviewData>(`/api/jobs/${jobId}/artifacts/${activeKey}`)
      .then((data) => {
        if (!active) return;
        setPreview(data);
      })
      .catch((err: Error) => {
        if (!active) return;
        setPreview(null);
        setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [jobId, activeKey]);

  if (availableTabs.length === 0) {
    return <div className={styles.empty}>还没有可用产物。</div>;
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.tabs} role="tablist" aria-label="产物预览">
        {PREVIEW_TABS.map((tab) => {
          const hasArtifact = tab.keys.some((key) => artifacts[key]);
          if (!hasArtifact) return null;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className={`${styles.tab} ${activeTab === tab.id ? styles.active : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className={styles.content}>
        {loading && <div className={styles.empty}>加载预览…</div>}
        {error && <div className={styles.error}>预览失败：{error}</div>}
        {!loading && !error && !activeKey && (
          <div className={styles.empty}>{emptyMessage(activeTab)}</div>
        )}
        {!loading && !error && preview?.kind === "media" && preview.media_url && (
          preview.artifact_key === "audio" ? (
            <audio className={styles.audio} controls src={preview.media_url}>
              <track kind="captions" />
            </audio>
          ) : (
            <video className={styles.media} controls src={preview.media_url}>
              <track kind="captions" />
            </video>
          )
        )}
        {!loading && !error && preview?.content && preview.kind === "markdown" && (
          <div className={styles.prose}>
            <ReactMarkdown>{preview.content}</ReactMarkdown>
          </div>
        )}
        {!loading && !error && preview?.content && preview.kind === "json" && (
          <pre className={styles.jsonBlock}>
            {(() => {
              try {
                return JSON.stringify(JSON.parse(preview.content), null, 2);
              } catch {
                return preview.content;
              }
            })()}
          </pre>
        )}
        {!loading &&
          !error &&
          preview?.content &&
          (preview.kind === "text" || preview.kind === "subtitle") && (
            <pre className={styles.textBody}>{preview.content}</pre>
          )}
      </div>
    </div>
  );
}
