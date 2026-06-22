import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchJson } from "../api/client";
import { cancelCookieLogin, exportCookieLogin, startCookieLogin } from "../api/cookies";
import { createJob } from "../api/jobs";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { Button } from "../components/ui/Button";
import styles from "./pages.module.css";

const JOB_TYPES = [
  { value: "run", label: "完整流程", desc: "下载内容，并按需继续转录和摘要。" },
  { value: "download-subs", label: "仅抓字幕", desc: "只保留字幕、页面信息和基础元数据。" },
  { value: "download", label: "仅下载媒体", desc: "抓取视频或音频文件，不继续处理。" },
  { value: "transcribe", label: "转录本地媒体", desc: "从已有文件生成 transcript。" },
  { value: "summarize", label: "生成摘要", desc: "从已有 transcript 提炼摘要内容。" },
] as const;

const BROWSER_LABELS: Record<string, string> = {
  chrome: "Chrome",
  edge: "Edge",
  firefox: "Firefox",
};

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
  const [cookiesFile, setCookiesFile] = useState("");
  const [doTranscribe, setDoTranscribe] = useState(true);
  const [doSummary, setDoSummary] = useState(false);
  const [cookieSessionId, setCookieSessionId] = useState<string | null>(null);
  const [cookieLoginBusy, setCookieLoginBusy] = useState(false);
  const [cookieLoginMessage, setCookieLoginMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const needsUrl = jobType !== "transcribe" && jobType !== "summarize";
  const needsPath = jobType === "transcribe" || jobType === "summarize";
  const needsDownload =
    jobType === "run" || jobType === "download" || jobType === "download-subs";

  useEffect(() => {
    void fetchJson<{
      effective: { download?: { cookies_from_browser?: string | null; cookie_file?: string | null } };
    }>("/api/config/effective")
      .then((payload) => {
        const browser = payload.effective?.download?.cookies_from_browser;
        const cookieFile = payload.effective?.download?.cookie_file;
        if (typeof browser === "string" && browser) {
          setCookiesBrowser(browser);
        }
        if (typeof cookieFile === "string" && cookieFile) {
          setCookiesFile(cookieFile);
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
      if (cookiesFile.trim()) {
        options.cookie_file = cookiesFile.trim();
      } else if (cookiesBrowser) {
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

  const handleStartCookieLogin = async () => {
    if (!url.trim()) {
      setError("请先填写视频链接或平台首页 URL");
      return;
    }
    setCookieLoginBusy(true);
    setError(null);
    setCookieLoginMessage(null);
    try {
      const response = await startCookieLogin({
        url: url.trim(),
        cookie_file: cookiesFile.trim() || undefined,
      });
      setCookieSessionId(response.session_id);
      setCookiesFile(response.cookie_file);
      setCookieLoginMessage(response.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "打开登录窗口失败");
    } finally {
      setCookieLoginBusy(false);
    }
  };

  const handleExportCookieLogin = async () => {
    if (!cookieSessionId) return;
    setCookieLoginBusy(true);
    setError(null);
    try {
      const response = await exportCookieLogin(cookieSessionId);
      setCookiesFile(response.cookie_file);
      setCookieSessionId(null);
      setCookieLoginMessage(response.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出 Cookies 失败");
    } finally {
      setCookieLoginBusy(false);
    }
  };

  const handleCancelCookieLogin = async () => {
    if (!cookieSessionId) return;
    setCookieLoginBusy(true);
    try {
      await cancelCookieLogin(cookieSessionId);
      setCookieSessionId(null);
      setCookieLoginMessage("已关闭登录窗口");
    } finally {
      setCookieLoginBusy(false);
    }
  };

  return (
    <section>
      <div className={styles.heroPanel}>
        <div>
          <div className="caption">New job</div>
          <h2 className="display-lg" style={{ margin: "6px 0 0" }}>
            选择来源，发起一次新的处理流程
          </h2>
          <p className={styles.heroLead}>
            Web 端和 `vlp` CLI 使用同一套能力。这里更适合发起任务、补 Cookies 登录，再回到详情页观察阶段进度。
          </p>
        </div>
        <div className={styles.heroMeta}>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{needsDownload ? "下载" : "处理"}</div>
            <div className={styles.statLabel}>当前任务面向</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{jobType === "run" ? "3" : "1"}</div>
            <div className={styles.statLabel}>预计阶段数</div>
          </div>
        </div>
      </div>

      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
      >
        <div className={styles.field}>
          <div className={styles.fieldTitle}>任务类型</div>
          <div className={styles.fieldCopy}>先决定这次只下载，还是要继续转录与摘要。</div>
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
            <div className={styles.fieldTitle}>来源链接</div>
            <div className={styles.fieldCopy}>填写视频页或可直接解析的内容链接。</div>
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
            <div className={styles.fieldTitle}>本地输入</div>
            <div className={styles.fieldCopy}>输入本地媒体或 transcript 路径，直接进入对应阶段。</div>
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
          <div className={styles.field}>
            <div className={styles.fieldTitle}>后续阶段</div>
            <div className={styles.fieldCopy}>完整流程里可以决定下载完成后是否继续处理。</div>
            <div className={styles.optionList}>
              <label className={styles.optionRow}>
                <input
                  type="checkbox"
                  checked={doTranscribe}
                  onChange={(event) => setDoTranscribe(event.target.checked)}
                />
                <span className={styles.optionBody}>
                  <span className={styles.optionTitle}>继续转录</span>
                  <span className={styles.optionCopy}>生成 transcript，便于搜索、校对和后续摘要。</span>
                </span>
              </label>
              <label className={styles.optionRow}>
                <input
                  type="checkbox"
                  checked={doSummary}
                  onChange={(event) => setDoSummary(event.target.checked)}
                />
                <span className={styles.optionBody}>
                  <span className={styles.optionTitle}>继续摘要</span>
                  <span className={styles.optionCopy}>基于 transcript 提炼重点，便于复用成内容素材。</span>
                </span>
              </label>
            </div>
          </div>
        )}

        {needsDownload && (
          <div className={styles.field}>
            <div className={styles.fieldTitle}>浏览器 Cookies</div>
            <div className={styles.fieldCopy}>需要登录态的平台，优先准备 Cookies，再发起下载。</div>
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
                YouTube 如需登录态，推荐先用 CLI 导出 cookies.txt，再在下方填写文件路径。
              </p>
            )}
          </div>
        )}

        {needsDownload && (
          <div className={styles.field}>
            <div className={styles.fieldTitle}>Cookies 文件</div>
            <div className={styles.fieldCopy}>推荐使用导出的 cookies.txt，避免直接读取浏览器数据库。</div>
            <label htmlFor="cookieFile">Cookies 文件路径</label>
            <input
              id="cookieFile"
              type="text"
              placeholder="temp\web-cookies\bilibili.com.txt"
              value={cookiesFile}
              onChange={(event) => setCookiesFile(event.target.value)}
            />
            <p className={styles.hint} style={{ marginTop: 8 }}>
              优先使用 `vlp cookies-login` 导出的 Netscape cookies.txt。填写后 Web 下载不会读取浏览器数据库，也不用关闭浏览器。
            </p>
            <div className={styles.callout}>
              <strong>使用方式</strong>
              <div className={styles.calloutSteps}>
                <div className={styles.calloutStep}>
                  <span className={styles.calloutStepIndex}>1</span>
                  <span>点击“打开登录窗口”。</span>
                </div>
                <div className={styles.calloutStep}>
                  <span className={styles.calloutStepIndex}>2</span>
                  <span>在弹出的浏览器里完成登录，并保持该页面打开。</span>
                </div>
                <div className={styles.calloutStep}>
                  <span className={styles.calloutStepIndex}>3</span>
                  <span>回到这里点击“导出 Cookies”，写入当前文件路径后再提交任务。</span>
                </div>
              </div>
            </div>
            <div className={styles.inlineActions}>
              <Button
                type="button"
                variant="ghost"
                disabled={cookieLoginBusy || Boolean(cookieSessionId)}
                onClick={() => void handleStartCookieLogin()}
              >
                {cookieLoginBusy && !cookieSessionId ? "打开中…" : "打开登录窗口"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={cookieLoginBusy || !cookieSessionId}
                onClick={() => void handleExportCookieLogin()}
              >
                导出 Cookies
              </Button>
              {cookieSessionId && (
                <Button
                  type="button"
                  variant="ghost"
                  disabled={cookieLoginBusy}
                  onClick={() => void handleCancelCookieLogin()}
                >
                  取消登录
                </Button>
              )}
            </div>
            {cookieLoginMessage && (
              <p className={styles.hint} style={{ marginTop: 8 }}>
                {cookieLoginMessage}
              </p>
            )}
          </div>
        )}

        {needsDownload && cookiesFile.trim() && (
          <div className={styles.callout}>
            将使用 cookies 文件：{cookiesFile.trim()}。浏览器可以保持打开。
          </div>
        )}

        {needsDownload && cookiesBrowser && (
          <div className={styles.callout}>
            未填写 cookies 文件时才会读取 {BROWSER_LABELS[cookiesBrowser] || cookiesBrowser} cookies；如果遇到锁库，请改用上方 cookies 文件路径。
          </div>
        )}

        {message && <div className={styles.callout}>{message}</div>}
        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.stickySubmit}>
          <Button type="submit" fullWidth disabled={submitting}>
            {submitting ? "提交中…" : "创建并开始任务"}
          </Button>
        </div>
      </form>
    </section>
  );
}
