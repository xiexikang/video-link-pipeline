import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ClipboardList, Plus, Settings } from "lucide-react";
import { checkHealth } from "../../api/client";
import { Button } from "../ui/Button";
import styles from "./layout.module.css";

const NAV_ITEMS = [
  { to: "/", label: "看板", icon: ClipboardList, end: true },
  { to: "/jobs/new", label: "新建", icon: Plus, end: false },
  { to: "/settings", label: "设置", icon: Settings, end: false },
] as const;

const PAGE_TITLES: Record<string, string> = {
  "/": "任务看板",
  "/jobs/new": "新建任务",
  "/settings": "环境诊断",
};

const PAGE_DESCRIPTIONS: Record<string, string> = {
  "/": "集中查看任务进度、失败状态和产物产出。",
  "/jobs/new": "从链接或本地文件发起一次新的处理流程。",
  "/settings": "检查下载、浏览器登录、转码和输出目录是否可用。",
};

function ApiStatus({ online, checking }: { online: boolean; checking: boolean }) {
  const dotClass = [
    styles.apiDot,
    checking ? styles.pending : online ? styles.online : styles.offline,
  ].join(" ");
  return (
    <div className={styles.apiStatus}>
      <span className={dotClass} aria-hidden />
      <span>{checking ? "连接中" : online ? "API 在线" : "API 离线"}</span>
    </div>
  );
}

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [apiOnline, setApiOnline] = useState(false);
  const [checking, setChecking] = useState(true);

  const isDetail = /^\/jobs\/[^/]+$/.test(location.pathname) && location.pathname !== "/jobs/new";
  const pageTitle = isDetail
    ? "任务详情"
    : (PAGE_TITLES[location.pathname] ?? "VLP");
  const pageDescription = isDetail
    ? "查看当前阶段、日志输出和可复用产物。"
    : (PAGE_DESCRIPTIONS[location.pathname] ?? "本地视频处理控制台");

  useEffect(() => {
    let active = true;
    const poll = async () => {
      setChecking(true);
      const ok = await checkHealth();
      if (active) {
        setApiOnline(ok);
        setChecking(false);
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const showBack = isDetail || location.pathname === "/jobs/new";

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brandBlock}>
          <div className={styles.brandMark}>VLP</div>
          <div className={styles.brandText}>
            <div className={styles.brand}>Video Link Pipeline</div>
          </div>
        </div>
        <nav className={styles.nav} aria-label="主导航">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => [styles.navLink, isActive ? styles.active : ""].join(" ")}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <ApiStatus online={apiOnline} checking={checking} />
      </aside>

      <aside className={styles.iconRail}>
        <nav className={styles.nav} aria-label="图标导航">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={item.label}
              className={({ isActive }) =>
                [styles.navLink, styles.iconOnly, isActive ? styles.active : ""].join(" ")
              }
            >
              <item.icon size={20} />
            </NavLink>
          ))}
        </nav>
        <ApiStatus online={apiOnline} checking={checking} />
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.mobileHeader}>
          {showBack ? (
            <button
              type="button"
              className={styles.backButton}
              aria-label="返回看板"
              onClick={() => navigate("/")}
            >
              <ArrowLeft size={20} />
            </button>
          ) : (
            <span style={{ width: "var(--touch-min)" }} />
          )}
          <div className={styles.mobileTitleWrap}>
            <div className={styles.mobileTitle}>{pageTitle}</div>
          </div>
          <span
            className={[
              styles.apiDot,
              checking ? styles.pending : apiOnline ? styles.online : styles.offline,
            ].join(" ")}
            title={apiOnline ? "API 在线" : "API 离线"}
          />
        </header>

        <header className={styles.topBar}>
          <div className={styles.topBarIntro}>
            <div className="caption">VLP Console</div>
            <h1 className="display-lg" style={{ margin: 0 }}>
              {pageTitle}
            </h1>
            <p className={styles.topBarCopy}>{pageDescription}</p>
          </div>
          <div className={styles.pageActions}>
            {location.pathname === "/" && (
              <>
                <Button variant="ghost" onClick={() => window.location.reload()}>
                  刷新列表
                </Button>
                <Button onClick={() => navigate("/jobs/new")}>新建任务</Button>
              </>
            )}
          </div>
        </header>

        <main className="app-main">
          <div
            className={[
              styles.contentWrap,
              isDetail || location.pathname === "/settings" ? styles.readingWidth : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <Outlet />
          </div>
        </main>
      </div>

      <nav className={styles.bottomTabBar} aria-label="底部导航">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [styles.tabItem, isActive && !showBack ? styles.active : ""].join(" ")
            }
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
