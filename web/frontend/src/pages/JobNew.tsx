import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchJson } from "../api/client";
import { createJob } from "../api/jobs";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { Button } from "../components/ui/Button";
import styles from "./pages.module.css";

const JOB_TYPES = [
  { value: "run", label: "Run", desc: "下载并可选转录、摘要" },
  { value: "download-subs", label: "Download subs", desc: "仅下载字幕与元数据" },
  { value: "download", label: "Download", desc: "下载媒体文件" },
  { value: "transcribe", label: "Transcribe", desc: "转录本地媒体" },
  { value: "summarize", label: "Summarize", desc: "从已有 transcript 生成摘要" },
] as const;

function isYouTubeUrl(value: string): boolean {
  return /youtube\.com|youtu\.be/i.test(value);
}

export function JobNew() {
  const navigate = useNavigate();
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [jobType, setJobType] = useState<string>("run");
  const [url, setUrl] = useState("");
  const [inputPath, setInputPath] = useState("");
  const [cookiesBrowser, setCookiesBrowser] = useState("");
  const [doTranscribe, setDoTranscribe] = useState(true);
  const [doSummary, setDoSummary] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const needsUrl = jobType !== "transcribe" && jobType !== "summarize";
  const needsPath = jobType === "transcribe" || jobType === "summarize";
  const needsDownload =
    jobType === "run" || jobType === "download" || jobType === "download-subs";

  useEffect(() => {
    void fetchJson<{ effective: { download?: { cookies_from_browser?: string | null } } }>(
      "/api/config/effective",
    )
      .then((payload) => {
        const browser = payload.effective?.download?.cookies_from_browser;
        if (typeof browser === "string" && browser) {
          setCookiesBrowser(browser);
        }
      })
      .catch(() => undefined);
  }, []);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const options: Record<string, unknown> = {};
      if (jobType === "run") {
        options.do_transcribe = doTranscribe;
        options.do_summary = doSummary;
      }
      if (cookiesBrowser) {
        options.cookies_from_browser = cookiesBrowser;
      }

      const response = await createJob({
        type: jobType,
        url: needsUrl ? url : undefined,
        input_path: needsPath ? inputPath : undefined,
        options,
      });
      setMessage(response.message);
      navigate(`/jobs/${response.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section>
      <p className={styles.hint}>选项与 `vlp` CLI 对齐。</p>

      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
      >
        <div className={styles.field}>
          <label>任务类型</label>
          {isDesktop ? (
            <div className={styles.filters}>
              {JOB_TYPES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={`${styles.filterChip} ${jobType === item.value ? styles.active : ""}`}
                  onClick={() => setJobType(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : (
            <div className={styles.jobList}>
              {JOB_TYPES.map((item) => (
                <label
                  key={item.value}
                  className={styles.settingCard}
                  style={{ display: "flex", gap: 12, alignItems: "flex-start", cursor: "pointer" }}
                >
                  <input
                    type="radio"
                    name="jobType"
                    value={item.value}
                    checked={jobType === item.value}
                    onChange={() => setJobType(item.value)}
                    style={{ marginTop: 4 }}
                  />
                  <span>
                    <div className={styles.settingTitle}>{item.label}</div>
                    <div className={styles.settingDetail}>{item.desc}</div>
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        {needsUrl && (
          <div className={styles.field}>
            <label htmlFor="url">视频链接</label>
            <input
              id="url"
              type="url"
              placeholder="https://www.bilibili.com/video/BV..."
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              required
            />
          </div>
        )}

        {needsPath && (
          <div className={styles.field}>
            <label htmlFor="inputPath">本地路径</label>
            <input
              id="inputPath"
              type="text"
              placeholder="output/demo-job/transcript.txt"
              value={inputPath}
              onChange={(event) => setInputPath(event.target.value)}
              required
            />
          </div>
        )}

        {jobType === "run" && (
          <>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={doTranscribe}
                onChange={(event) => setDoTranscribe(event.target.checked)}
              />
              转录（--do-transcribe）
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={doSummary}
                onChange={(event) => setDoSummary(event.target.checked)}
              />
              摘要（--do-summary）
            </label>
          </>
        )}

        {needsDownload && (
          <div className={styles.field}>
            <label htmlFor="cookies">Cookies 浏览器</label>
            <select
              id="cookies"
              value={cookiesBrowser}
              onChange={(event) => setCookiesBrowser(event.target.value)}
            >
              <option value="">不指定</option>
              <option value="chrome">Chrome</option>
              <option value="edge">Edge</option>
              <option value="firefox">Firefox</option>
            </select>
            {!cookiesBrowser && isYouTubeUrl(url) && (
              <p className={styles.hint} style={{ marginTop: 8 }}>
                YouTube 通常需要浏览器 cookies，请选择已登录 YouTube 的浏览器。
              </p>
            )}
          </div>
        )}

        {needsDownload && cookiesBrowser && (
          <div className={styles.callout}>
            提交前请完全关闭 {cookiesBrowser === "firefox" ? "Firefox" : "Chrome / Edge / Firefox"}。
          </div>
        )}

        {message && <div className={styles.callout}>{message}</div>}
        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.stickySubmit}>
          <Button type="submit" fullWidth disabled={submitting}>
            {submitting ? "提交中…" : "开始任务"}
          </Button>
          <Button type="button" variant="ghost" fullWidth onClick={() => navigate("/")}>
            返回看板
          </Button>
        </div>
      </form>
    </section>
  );
}
