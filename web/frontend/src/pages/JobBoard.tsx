import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchJson } from "../api/client";
import { JobRow } from "../components/job/JobRow";
import { Button } from "../components/ui/Button";
import type { JobListItem, JobListResponse, RuntimeStatus } from "../types/jobs";
import styles from "./pages.module.css";

type FilterKey = "all" | RuntimeStatus;

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "succeeded", label: "成功" },
  { key: "failed", label: "失败" },
  { key: "running", label: "进行中" },
];

export function JobBoard() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadJobs = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const payload = await fetchJson<JobListResponse>("/api/jobs");
      setJobs(payload.jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  const filteredJobs = useMemo(() => {
    if (filter === "all") return jobs;
    if (filter === "running") {
      return jobs.filter((job) => job.runtime_status === "running" || job.runtime_status === "queued");
    }
    return jobs.filter((job) => job.runtime_status === filter);
  }, [filter, jobs]);

  return (
    <section>
      <div className={styles.sectionHeader}>
        <div>
          <h2 className="display-sm" style={{ margin: 0 }}>
            任务
          </h2>
          <div className="caption">{jobs.length} 个任务</div>
        </div>
      </div>

      <div className={styles.filters} role="tablist" aria-label="任务筛选">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            className={`${styles.filterChip} ${filter === item.key ? styles.active : ""}`}
            onClick={() => setFilter(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error && <div className={styles.error}>加载失败：{error}</div>}

      {loading ? (
        <div className={styles.previewPlaceholder}>加载任务列表…</div>
      ) : filteredJobs.length === 0 ? (
        <div className={styles.empty}>
          <h3 className="display-sm">还没有任务</h3>
          <p>用 CLI 跑一个 job，或新建任务开始。</p>
          <Button fullWidth onClick={() => navigate("/jobs/new")}>
            新建任务
          </Button>
        </div>
      ) : (
        <div className={styles.jobList}>
          {filteredJobs.map((job) => (
            <JobRow key={job.id} job={job} refreshing={refreshing} />
          ))}
        </div>
      )}
    </section>
  );
}
