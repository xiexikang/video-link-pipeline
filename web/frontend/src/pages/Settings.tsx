import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../api/client";
import type { DoctorResponse } from "../types/jobs";
import styles from "./pages.module.css";

const CARD_GROUPS: Record<string, string[]> = {
  FFmpeg: ["ffmpeg"],
  Selenium: ["selenium"],
  Cookies: ["cookie", "browser"],
  Output: ["output"],
};

function matchGroup(name: string, keywords: string[]): boolean {
  const lower = name.toLowerCase();
  return keywords.some((keyword) => lower.includes(keyword));
}

export function Settings() {
  const [data, setData] = useState<DoctorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchJson<DoctorResponse>("/api/doctor")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  const grouped = useMemo(() => {
    if (!data) return {} as Record<string, DoctorResponse["checks"]>;
    const buckets: Record<string, DoctorResponse["checks"]> = {
      FFmpeg: [],
      Selenium: [],
      Cookies: [],
      Output: [],
      Other: [],
    };

    for (const check of data.checks) {
      let placed = false;
      for (const [group, keywords] of Object.entries(CARD_GROUPS)) {
        if (matchGroup(check.name, keywords) || matchGroup(check.section, keywords)) {
          buckets[group].push(check);
          placed = true;
          break;
        }
      }
      if (!placed) buckets.Other.push(check);
    }
    return buckets;
  }, [data]);

  if (error) return <div className={styles.error}>诊断加载失败：{error}</div>;
  if (!data) return <div className={styles.previewPlaceholder}>加载环境诊断…</div>;

  const passedCount = data.checks.filter((check) => check.ok).length;

  return (
    <section>
      <div className={styles.heroPanel}>
        <div>
          <div className="caption">Environment</div>
          <h2 className="display-lg" style={{ margin: "6px 0 0" }}>
            先确认本机依赖正常，再跑实际任务
          </h2>
          <p className={styles.heroLead}>
            这里主要检查 FFmpeg、Selenium、浏览器 Cookies 和输出目录。环境先稳定，后续任务就不容易在半路失败。
          </p>
        </div>
        <div className={styles.heroMeta}>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{passedCount}</div>
            <div className={styles.statLabel}>通过检查</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{data.checks.length}</div>
            <div className={styles.statLabel}>检查总数</div>
          </div>
        </div>
      </div>
      <p className={styles.hint}>优先处理 Fail 项，再回到任务页发起下载或转录。</p>
      <div className={styles.settingsGrid}>
        {(["FFmpeg", "Selenium", "Cookies", "Output"] as const).map((group) => {
          const checks = grouped[group] ?? [];
          const ok = checks.length === 0 ? true : checks.every((check) => check.ok);
          return (
            <article key={group} className={styles.settingCard}>
              <div className={`${styles.statusLight} ${ok ? styles.pass : styles.fail}`}>
                {ok ? "Ready" : "Needs attention"}
              </div>
              <h3 className={styles.settingTitle}>{group}</h3>
              {checks.length === 0 ? (
                <p className={styles.settingDetail}>
                  {group === "Output" ? `目录：${data.output_dir}` : "暂无专项检查结果"}
                </p>
              ) : (
                checks.map((check) => (
                  <p key={check.name} className={styles.settingDetail}>
                    <strong>{check.name}</strong> — {check.detail}
                    {check.hint ? ` · ${check.hint}` : ""}
                  </p>
                ))
              )}
            </article>
          );
        })}
      </div>

      <div className={`${styles.configPath} mono`}>
        config: {data.config_source ?? "defaults/.env/environment"}
        <br />
        output: {data.output_dir}
      </div>
    </section>
  );
}
