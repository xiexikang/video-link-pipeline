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
  "/": "任务",
  "/jobs/new": "新建任务",
  "/settings": "环境诊断",
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
        <div className={styles.brand}>VLP</div>
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
          <div className={styles.mobileTitle}>{pageTitle}</div>
          <span
            className={[
              styles.apiDot,
              checking ? styles.pending : apiOnline ? styles.online : styles.offline,
            ].join(" ")}
            title={apiOnline ? "API 在线" : "API 离线"}
          />
        </header>

        <header className={styles.topBar}>
          <h1 className="display-lg" style={{ margin: 0 }}>
            {pageTitle}
          </h1>
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
