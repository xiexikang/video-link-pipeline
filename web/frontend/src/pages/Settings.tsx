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

  return (
    <section>
      <p className={styles.hint}>确认本机 prerequisites 是否就绪。</p>
      <div className={styles.settingsGrid}>
        {(["FFmpeg", "Selenium", "Cookies", "Output"] as const).map((group) => {
          const checks = grouped[group] ?? [];
          const ok = checks.length === 0 ? true : checks.every((check) => check.ok);
          return (
            <article key={group} className={styles.settingCard}>
              <div className={`${styles.statusLight} ${ok ? styles.pass : styles.fail}`}>
                {ok ? "Pass" : "Fail"}
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
