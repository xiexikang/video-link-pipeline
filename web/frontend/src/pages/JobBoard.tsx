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

  const stats = useMemo(() => {
    const running = jobs.filter((job) => job.runtime_status === "running" || job.runtime_status === "queued").length;
    const failed = jobs.filter((job) => job.runtime_status === "failed").length;
    const completed = jobs.filter((job) => job.runtime_status === "succeeded").length;
    return { running, failed, completed };
  }, [jobs]);

  return (
    <section>
      <div className={styles.heroPanel}>
        <div>
          <div className="caption">Pipeline overview</div>
          <h2 className="display-lg" style={{ margin: "6px 0 0" }}>
            统一查看每个任务当前走到哪一步
          </h2>
          <p className={styles.heroLead}>
            这里集中展示下载、转录、摘要三个阶段的进度。失败任务能快速定位，已有产物也能继续复用。
          </p>
        </div>
        <div className={styles.heroMeta}>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{jobs.length}</div>
            <div className={styles.statLabel}>任务总数</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{stats.running}</div>
            <div className={styles.statLabel}>进行中</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{stats.completed}</div>
            <div className={styles.statLabel}>已完成</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{stats.failed}</div>
            <div className={styles.statLabel}>需要处理</div>
          </div>
        </div>
      </div>

      <div className={styles.sectionHeader}>
        <div>
          <h2 className="display-sm" style={{ margin: 0 }}>
            任务列表
          </h2>
          <div className={styles.hint}>按运行状态筛选，进入详情页查看日志、诊断信息和产物预览。</div>
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
          <p>先发起一次下载、转录或摘要任务，这里就会开始显示进度和结果。</p>
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
