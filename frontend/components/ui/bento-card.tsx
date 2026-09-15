import React, { useEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  LayoutGroup,
  motion,
  useReducedMotion,
} from "motion/react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Eye,
  Heart,
  LayoutDashboard,
  Layers3,
  LogOut,
  MessageSquare,
  Moon,
  Palette,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useResource } from "@/lib/account-api";
import {
  AccountDialogsProvider,
  useAccountDialogs,
} from "@/components/ui/account-dialogs";

type User = {
  id: number;
  username: string;
  nickname: string;
  role: string;
  avatar_color: string;
};
type Lineup = {
  id: number;
  name: string;
  code: string;
  rank_level: string;
  status: string;
  like_count: number;
  copy_count: number;
  owner_nickname: string;
  season_name?: string;
  updated_at: string;
  history_at?: string;
};
type Report = {
  id: number;
  lineup_id: number;
  lineup_name: string;
  lineup_status: string;
  status: string;
  reason: string;
  created_at: string;
  handled_at?: string;
};
type Page = {
  items: Lineup[];
  total: number;
  total_pages: number;
  page: number;
};
type Dashboard = {
  published_lineups: number;
  hidden_lineups: number;
  received_likes: number;
  received_favorites: number;
  received_copies: number;
  submitted_reports: number;
  pending_reports_on_my_lineups: number;
};
type Failure = Error & { status?: number };
declare global {
  interface Window {
    JccAccount: {
      request: <T>(url: string, options?: RequestInit) => Promise<T>;
      copy: (lineup: Lineup, token: string) => Promise<void>;
    };
    jccAvatar: {
      getAvatarDataUrl: (
        key: string,
        options: { color: string; size: number },
      ) => string;
    };
    jccAvatarEditor: {
      mount: (
        user: User,
        token: string,
        options: {
          trigger: HTMLButtonElement;
          onSave: (color: string) => void;
        },
      ) => () => void;
    };
    jccNotify: {
      show: (
        message: string,
        options?: { variant: string; title?: string },
      ) => void;
    };
  }
}
const TABS = [
  {
    id: "overview",
    label: "个人概览",
    icon: LayoutDashboard,
    description: "你的阵容、灵感与每一次被认可。",
  },
  {
    id: "mine",
    label: "我的阵容",
    icon: Layers3,
    description: "管理你的创作，随时打磨下一套上分阵容。",
  },
  {
    id: "favorites",
    label: "我的收藏",
    icon: Bookmark,
    description: "收藏的好思路，下次开局时就在这里。",
  },
  {
    id: "views",
    label: "最近浏览",
    icon: Eye,
    description: "回到最近看过的阵容，接着研究。",
  },
  {
    id: "copies",
    label: "最近复制",
    icon: Copy,
    description: "快速找回最近用过的阵容码。",
  },
  {
    id: "reports",
    label: "我的失效反馈",
    icon: MessageSquare,
    description: "查看你提交的反馈与处理结果。",
  },
] as const;
type Tab = (typeof TABS)[number]["id"];
const PAGE_SIZE = 4;
const reportStatusText: Record<string, string> = {
  pending: "待处理",
  resolved: "已处理",
  dismissed: "已驳回",
};
const lineupStatusText: Record<string, string> = {
  normal: "公开",
  hidden: "已隐藏",
  deleted: "已删除",
  banned: "已封禁",
};
const number = (n: number) => new Intl.NumberFormat("zh-CN").format(n);
const time = (value?: string) =>
  value ? value.replace("T", " ").slice(0, 16) : "—";
const tabFromHash = (): Tab =>
  TABS.find((tab) => `#${tab.id}` === location.hash)?.id || "overview";
function resetContentScroll() {
  if (matchMedia("(max-width: 760px)").matches) window.scrollTo(0, 0);
  else document.querySelector(".pf-content")?.scrollTo(0, 0);
}

function ErrorState({ error, retry }: { error: Failure; retry: () => void }) {
  return (
    <div className="pf-empty" role="alert">
      <MessageSquare size={26} />
      <strong>
        {error.status === 401 || error.status === 403
          ? "登录状态已失效"
          : "暂时没有加载成功"}
      </strong>
      <p>{error.message}</p>
      {error.status === 401 || error.status === 403 ? (
        <a className="pf-button" href="/auth?next=%2Fme">
          重新登录
        </a>
      ) : (
        <button className="pf-button" onClick={retry}>
          重新加载
        </button>
      )}
    </div>
  );
}
function Loading() {
  return (
    <div className="pf-loading" role="status" aria-label="正在加载">
      <span />
      <span />
      <span />
    </div>
  );
}
function Empty({
  title = "这里还没有阵容",
  description = "去阵容库逛逛，发现一些新的上分思路。",
  mine = false,
}: {
  title?: string;
  description?: string;
  mine?: boolean;
}) {
  return (
    <div className="pf-empty">
      <Layers3 size={30} />
      <strong>{title}</strong>
      <p>{description}</p>
      <a className="pf-button" href={mine ? "/lineup/new" : "/"}>
        {mine ? "发布第一套阵容" : "探索阵容库"}
        <ArrowUpRight size={15} />
      </a>
    </div>
  );
}
function Avatar({ user, size = 40 }: { user: User; size?: number }) {
  return (
    <img
      className="pf-avatar"
      width={size}
      height={size}
      alt={`${user.nickname}的头像`}
      src={window.jccAvatar.getAvatarDataUrl("", {
        color: user.avatar_color,
        size,
      })}
    />
  );
}

export default function BentoCard() {
  const session = useResource<{ user: User | null; csrf_token: string }>(
    "/api/me",
  );
  if (session.error)
    return <ErrorState error={session.error} retry={session.retry} />;
  if (!session.data)
    return (
      <div className="profile-boot">
        <span className="profile-boot-mark">阵</span>
        <Loading />
      </div>
    );
  if (!session.data.user)
    return (
      <ErrorState
        error={Object.assign(new Error("请登录后查看你的个人中心"), {
          status: 401,
        })}
        retry={session.retry}
      />
    );
  return (
    <AccountDialogsProvider
      key={session.data.user.id}
      token={session.data.csrf_token}
    >
      <Profile user={session.data.user} token={session.data.csrf_token} />
    </AccountDialogsProvider>
  );
}

function Profile({ user: initialUser, token }: { user: User; token: string }) {
  const dialogs = useAccountDialogs();
  const [user, setUser] = useState(initialUser);
  const [active, setActive] = useState<Tab>(tabFromHash);
  const [theme, setTheme] = useState(
    document.documentElement.dataset.theme || "light",
  );
  const [loggingOut, setLoggingOut] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();
  const tab = TABS.find((item) => item.id === active)!;
  useEffect(() => {
    if (!trigger.current) return;
    return window.jccAvatarEditor.mount(initialUser, token, {
      trigger: trigger.current,
      onSave: (color) =>
        setUser((value) => ({ ...value, avatar_color: color })),
    });
  }, [initialUser, token]);
  useEffect(() => {
    const change = () => {
      if (location.hash === "#lineup-notifications") {
        dialogs.open({ kind: "notifications" });
        return;
      }
      if (location.hash === "#avatar") trigger.current?.click();
      setActive(tabFromHash());
    };
    if (location.hash === "#lineup-notifications") change();
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(resetContentScroll, [active]);
  function navigate(id: Tab) {
    if (active !== id) location.hash = id;
  }
  function toggleTheme() {
    const value = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = value;
    localStorage.setItem("theme", value);
    setTheme(value);
  }
  async function logout() {
    setLoggingOut(true);
    try {
      await window.JccAccount.request("/api/logout", { method: "POST" });
      location.replace("/");
    } catch (error) {
      window.jccNotify.show((error as Error).message, { variant: "error" });
      setLoggingOut(false);
    }
  }
  return (
    <div className="pf-shell">
      <aside className="pf-sidebar" aria-label="个人中心侧栏">
        <a className="pf-brand" href="/" aria-label="返回金铲铲阵容库">
          <span className="pf-brand-mark">阵</span>
          <span>
            金铲铲阵容库<small>YOUR PLAYBOOK</small>
          </span>
        </a>
        <div className="pf-side-identity">
          <Avatar user={user} size={44} />
          <span>
            <strong>{user.nickname}</strong>
            <small>@{user.username}</small>
          </span>
          <button
            ref={trigger}
            id="editAvatar"
            className="pf-icon-button"
            aria-label="调整头像"
          >
            <Palette size={17} />
          </button>
        </div>
        <p className="pf-nav-caption">个人空间</p>
        <nav className="pf-tabs" role="tablist" aria-label="个人中心栏目">
          <LayoutGroup id="profile-navigation">
            {TABS.map((item, i) => (
              <button
                key={item.id}
                id={`tab-${item.id}`}
                role="tab"
                aria-selected={active === item.id}
                aria-controls="profile-panel"
                tabIndex={active === item.id ? 0 : -1}
                className={cn("pf-tab", active === item.id && "is-active")}
                onClick={() => navigate(item.id)}
                onKeyDown={(event) => {
                  let index: number | undefined;
                  if (event.key === "ArrowDown" || event.key === "ArrowRight")
                    index = (i + 1) % TABS.length;
                  if (event.key === "ArrowUp" || event.key === "ArrowLeft")
                    index = (i + TABS.length - 1) % TABS.length;
                  if (event.key === "Home") index = 0;
                  if (event.key === "End") index = TABS.length - 1;
                  if (index !== undefined) {
                    event.preventDefault();
                    navigate(TABS[index].id);
                    document.getElementById(`tab-${TABS[index].id}`)?.focus();
                  }
                }}
              >
                {active === item.id && (
                  <motion.span
                    className="pf-tab-indicator"
                    layoutId="sidebar-pill"
                    transition={{ duration: reducedMotion ? 0 : 0.22 }}
                  />
                )}
                <item.icon size={18} />
                <span>{item.label}</span>
                {active === item.id && <span className="pf-active-dot" />}
              </button>
            ))}
          </LayoutGroup>
        </nav>
        <div className="pf-sidebar-bottom">
          <div className="pf-side-note">
            <Sparkles size={18} />
            <p>
              好阵容，值得被看见。<small>把你的上分思路分享给更多弈士。</small>
            </p>
            <a href="/lineup/new">
              发布阵容
              <Plus size={15} />
            </a>
          </div>
          <a className="pf-side-link" href="/">
            <ArrowLeft size={17} />
            返回阵容库
          </a>
          <button
            className="pf-side-link"
            disabled={loggingOut}
            onClick={logout}
          >
            <LogOut size={17} />
            {loggingOut ? "正在退出…" : "退出登录"}
          </button>
        </div>
      </aside>
      <div className="pf-main">
        <header className="pf-topbar">
          <div className="pf-breadcrumb">
            <span>个人中心</span>
            <ChevronRight size={13} />
            <strong>{tab.label}</strong>
          </div>
          <div className="pf-top-actions">
            <button
              className="pf-icon-button pf-notice-bell"
              onClick={(event) =>
                dialogs.open({ kind: "notifications" }, event.currentTarget)
              }
              aria-label={
                dialogs.unread
                  ? `查看通知，${dialogs.unread} 条未读`
                  : "查看通知"
              }
              title={
                dialogs.countError
                  ? "通知数量暂时不可用，点击重试"
                  : "阵容处理通知"
              }
            >
              <Bell size={18} />
              {dialogs.unread > 0 && (
                <span className="pf-notice-count">
                  {dialogs.unread > 99 ? "99+" : dialogs.unread}
                </span>
              )}
            </button>
            <button
              className="pf-icon-button"
              onClick={toggleTheme}
              aria-label={
                theme === "dark" ? "切换为白天模式" : "切换为夜间模式"
              }
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <a className="pf-button pf-primary" href="/lineup/new">
              <Plus size={16} />
              发布阵容
            </a>
          </div>
        </header>
        <div className="pf-content" ref={scroll}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.section
              id="profile-panel"
              role="tabpanel"
              aria-labelledby={`tab-${active}`}
              tabIndex={0}
              key={active}
              initial={reducedMotion ? false : { opacity: 0, y: 7 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.14 }}
            >
              {active === "overview" ? (
                <Overview
                  user={user}
                  token={token}
                  navigate={navigate}
                  editAvatar={() => trigger.current?.click()}
                />
              ) : (
                <>
                  <div className="pf-workspace-heading">
                    <p className="pf-eyebrow">
                      MY PLAYBOOK /{" "}
                      {String(TABS.findIndex((t) => t.id === active)).padStart(
                        2,
                        "0",
                      )}
                    </p>
                    <h1>{tab.label}</h1>
                    <p>{tab.description}</p>
                  </div>
                  <Collection key={active} kind={active} token={token} />
                </>
              )}
            </motion.section>
          </AnimatePresence>
          <footer className="pf-footer">
            <span>每一套阵容，都有你的思考。</span>
            <span>金铲铲阵容库</span>
          </footer>
        </div>
      </div>
    </div>
  );
}

function Overview({
  user,
  token,
  navigate,
  editAvatar,
}: {
  user: User;
  token: string;
  navigate: (id: Tab) => void;
  editAvatar: () => void;
}) {
  const dialogs = useAccountDialogs();
  const dashboard = useResource<Dashboard>(
    "/api/me/dashboard",
    dialogs.dataRevision,
  );
  const views = useResource<Lineup[]>("/api/me/recent-views");
  const data = dashboard.data;
  return (
    <div className="pf-overview">
      <div className="pf-profile-banner">
        <div className="pf-profile-copy">
          <p className="pf-eyebrow">PLAYER PROFILE</p>
          <div className="pf-profile-person">
            <button
              className="pf-avatar-button"
              onClick={editAvatar}
              aria-label="编辑个人头像"
            >
              <Avatar user={user} size={78} />
              <span>
                <Palette size={12} />
              </span>
            </button>
            <div>
              <div className="pf-profile-name">
                <h1>{user.nickname}</h1>
                <span className="pf-role">
                  <ShieldCheck size={12} />
                  {user.role === "admin" ? "管理员" : "弈士"}
                </span>
              </div>
              <p className="pf-handle">@{user.username}</p>
              <p className="pf-motto">把每一次灵感，变成下一次上分。</p>
            </div>
          </div>
          <div className="pf-profile-links">
            <button onClick={editAvatar}>
              调整头像
              <ArrowUpRight size={13} />
            </button>
            {user.role !== "admin" && (
              <a href={`/author/${encodeURIComponent(user.username)}`}>
                公开主页
                <ArrowUpRight size={13} />
              </a>
            )}
          </div>
        </div>
        <div className="pf-banner-art" aria-hidden="true">
          <div className="pf-art-orbit" />
          <div className="pf-art-board">
            {Array.from({ length: 9 }, (_, i) => (
              <span key={i} />
            ))}
          </div>
          <span className="pf-art-caption">EVERY MOVE MATTERS</span>
        </div>
      </div>
      <div className="pf-section-label">
        <h2>我的数据</h2>
        <span>来自你的阵容与互动</span>
      </div>
      {dashboard.error ? (
        <ErrorState error={dashboard.error} retry={dashboard.retry} />
      ) : (
        <div className="pf-stats" aria-busy={dashboard.loading}>
          {[
            {
              label: "已发布阵容",
              value: data?.published_lineups,
              icon: Layers3,
              note: "包含隐藏与封禁阵容",
              target: "mine" as Tab,
            },
            {
              label: "收到点赞",
              value: data?.received_likes,
              icon: Heart,
              note: "来自弈士的认可",
            },
            {
              label: "收到收藏",
              value: data?.received_favorites,
              icon: Bookmark,
              note: "你的思路被珍藏",
            },
            {
              label: "收到复制",
              value: data?.received_copies,
              icon: ArrowDownToLine,
              note: "阵容被带入下一局",
            },
          ].map((stat) => (
            <article className="pf-stat" key={stat.label}>
              <div>
                <span>{stat.label}</span>
                <stat.icon size={17} />
              </div>
              <strong>
                {stat.value === undefined ? "—" : number(stat.value)}
              </strong>
              <small>{stat.note}</small>
              {stat.target && (
                <button
                  className="pf-stat-link"
                  aria-label="查看我的阵容"
                  onClick={() => navigate(stat.target!)}
                >
                  <ArrowUpRight size={16} />
                </button>
              )}
            </article>
          ))}
        </div>
      )}
      <div className="pf-bento-grid">
        <section className="pf-card pf-recent">
          <div className="pf-card-heading">
            <div>
              <h2>继续你的上分思路</h2>
              <p>最近浏览 · 灵感无需从头找起</p>
            </div>
            <button
              className="pf-text-button"
              onClick={() => navigate("views")}
            >
              全部
              <ArrowRight size={14} />
            </button>
          </div>
          {views.error ? (
            <ErrorState error={views.error} retry={views.retry} />
          ) : views.loading ? (
            <Loading />
          ) : !views.data?.length ? (
            <Empty title="你的下一套阵容，从这里开始" />
          ) : (
            <div className="pf-recent-list">
              {views.data.slice(0, 3).map((item, i) => (
                <div className="pf-recent-row" key={item.id}>
                  <span className="pf-index">0{i + 1}</span>
                  <div>
                    <a href={`/lineup/${item.id}`}>{item.name}</a>
                    <p>
                      {item.owner_nickname} · {time(item.history_at)}
                    </p>
                  </div>
                  <CopyButton item={item} token={token} compact />
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="pf-card pf-notebook">
          <div className="pf-card-heading">
            <div>
              <h2>创作备忘</h2>
              <p>把阵容状态，一起照顾好</p>
            </div>
            <Layers3 size={18} />
          </div>
          <div className="pf-notebook-lines">
            <button onClick={() => navigate("mine")}>
              <span>
                <Eye size={15} />
                隐藏阵容
              </span>
              <strong>{data ? number(data.hidden_lineups) : "—"}</strong>
              <ChevronRight size={14} />
            </button>
            <button onClick={() => navigate("mine")}>
              <span>
                <MessageSquare size={15} />
                我的阵容待处理反馈
              </span>
              <strong>
                {data ? number(data.pending_reports_on_my_lineups) : "—"}
              </strong>
              <ChevronRight size={14} />
            </button>
            <button onClick={() => navigate("reports")}>
              <span>
                <Check size={15} />
                我提交的失效反馈
              </span>
              <strong>{data ? number(data.submitted_reports) : "—"}</strong>
              <ChevronRight size={14} />
            </button>
          </div>
          <button
            className="pf-notebook-footer"
            onClick={(event) =>
              dialogs.open({ kind: "notifications" }, event.currentTarget)
            }
          >
            <Bell size={15} />
            <span>查看阵容处理通知</span>
            <ChevronRight size={15} />
          </button>
        </section>
      </div>
    </div>
  );
}

function CopyButton({
  item,
  token,
  compact = false,
}: {
  item: Lineup;
  token: string;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  return (
    <button
      className={cn("pf-button pf-copy", compact && "pf-copy-compact")}
      disabled={busy}
      aria-label={`复制阵容码：${item.name}`}
      onClick={async () => {
        if (inFlight.current) return;
        inFlight.current = true;
        setBusy(true);
        try {
          await window.JccAccount.copy(item, token);
        } catch (error) {
          window.jccNotify.show((error as Error).message, { variant: "error" });
        } finally {
          inFlight.current = false;
          setBusy(false);
        }
      }}
    >
      <Copy size={14} />
      <span>{busy ? "正在复制…" : compact ? "复制" : "复制阵容码"}</span>
    </button>
  );
}
function Pager({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (n: number) => void;
}) {
  return (
    <nav className="pf-pagination" aria-label="列表分页">
      <span>共 {number(total)} 条</span>
      <div>
        <button
          className="pf-icon-button"
          aria-label="上一页"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft size={17} />
        </button>
        <span>
          第 {page} / {Math.max(1, pages)} 页
        </span>
        <button
          className="pf-icon-button"
          aria-label="下一页"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight size={17} />
        </button>
      </div>
    </nav>
  );
}

function Collection({
  kind,
  token,
}: {
  kind: Exclude<Tab, "overview">;
  token: string;
}) {
  const [page, setPage] = useState(1),
    [draft, setDraft] = useState(""),
    [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const paginated = kind === "mine" || kind === "favorites";
  const url = paginated
    ? `/api/lineups?view=${kind}&page=${page}&page_size=${PAGE_SIZE}&q=${encodeURIComponent(query)}`
    : kind === "reports"
      ? "/api/me/reports"
      : `/api/me/recent-${kind}`;
  const dialogs = useAccountDialogs();
  const result = useResource<Page | Lineup[] | Report[]>(
    url,
    dialogs.dataRevision,
  );
  const payload = paginated ? (result.data as Page | undefined) : undefined;
  const all = paginated
    ? payload?.items || []
    : ((result.data || []) as (Lineup | Report)[]).filter((item) => {
        const name = "lineup_name" in item ? item.lineup_name : item.name;
        return (
          `${name} ${"reason" in item ? item.reason : item.owner_nickname}`
            .toLocaleLowerCase()
            .includes(query.toLocaleLowerCase()) &&
          (filter === "all" || item.status === filter)
        );
      });
  const total = payload?.total ?? all.length;
  const pages = payload?.total_pages ?? Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.min(page, Math.max(1, pages));
  const items = paginated
    ? all
    : all.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  useEffect(() => {
    if (payload && page > Math.max(1, payload.total_pages))
      setPage(Math.max(1, payload.total_pages));
  }, [payload, page]);
  const changePage = (value: number) => {
    setPage(value);
    resetContentScroll();
  };
  return (
    <div className="pf-collection">
      <form
        className="pf-searchbar"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(draft.trim());
          setPage(1);
        }}
      >
        <div className="pf-search-input">
          <Search size={17} />
          <input
            type="search"
            aria-label="搜索当前栏目"
            placeholder={
              kind === "reports" ? "搜索阵容名称、反馈原因…" : "搜索阵容名称…"
            }
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          {(draft || query) && (
            <button
              type="button"
              className="pf-icon-button"
              aria-label="清空搜索"
              onClick={() => {
                setDraft("");
                setQuery("");
                setPage(1);
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>
        <button className="pf-button" type="submit">
          搜索
        </button>
      </form>
      {kind === "reports" && (
        <div className="pf-filters" role="group" aria-label="反馈状态">
          {[["all", "全部"], ...Object.entries(reportStatusText)].map(
            ([id, label]) => (
              <button
                key={id}
                className={cn(filter === id && "is-active")}
                aria-pressed={filter === id}
                onClick={() => {
                  setFilter(id);
                  setPage(1);
                }}
              >
                {label}
              </button>
            ),
          )}
        </div>
      )}
      {(kind === "views" || kind === "copies") && (
        <p className="pf-history-note">
          <Clock3 size={13} />
          按最近{kind === "views" ? "浏览" : "复制"}时间排列 ·
          展示账号保留的近期记录
        </p>
      )}
      {result.error ? (
        <ErrorState error={result.error} retry={result.retry} />
      ) : result.loading ? (
        <Loading />
      ) : (
        <>
          {!items.length ? (
            query || filter !== "all" ? (
              <div className="pf-empty">
                <Search size={28} />
                <strong>没有找到匹配的内容</strong>
                <p>换一个关键词，或清除筛选再看看。</p>
                <button
                  className="pf-button"
                  onClick={() => {
                    setDraft("");
                    setQuery("");
                    setFilter("all");
                    setPage(1);
                  }}
                >
                  清除筛选
                </button>
              </div>
            ) : (
              <Empty
                mine={kind === "mine"}
                title={
                  kind === "reports"
                    ? "还没有提交过失效反馈"
                    : kind === "favorites"
                      ? "把喜欢的阵容，留在这里"
                      : kind === "mine"
                        ? "第一套阵容，等你分享"
                        : "这里还没有近期记录"
                }
                description={
                  kind === "reports"
                    ? "阵容有问题时，可从阵容库提交失效反馈。"
                    : undefined
                }
              />
            )
          ) : (
            <div className="pf-collection-grid">
              {items.map((item) =>
                "lineup_name" in item ? (
                  <ReportCard key={item.id} item={item} />
                ) : (
                  <LineupCard
                    key={item.id}
                    item={item}
                    kind={kind}
                    token={token}
                    refresh={result.retry}
                  />
                ),
              )}
            </div>
          )}
          <Pager
            page={currentPage}
            pages={pages}
            total={total}
            onPage={changePage}
          />
        </>
      )}
    </div>
  );
}

function LineupCard({
  item,
  kind,
  token,
  refresh,
}: {
  item: Lineup;
  kind: string;
  token: string;
  refresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const dialogs = useAccountDialogs();
  return (
    <article className="pf-lineup-card" data-lineup-id={item.id}>
      <div className="pf-lineup-card-top">
        <span className="pf-rank">{item.rank_level || "阵容"}</span>
        <span className={cn("pf-status", `pf-status-${item.status}`)}>
          {kind === "mine"
            ? lineupStatusText[item.status] || item.status
            : item.season_name || "阵容"}
        </span>
      </div>
      <h2>
        {item.status === "banned" && kind === "mine" ? (
          <button
            className="pf-title-button"
            onClick={(event) =>
              dialogs.open(
                { kind: "moderation", id: item.id },
                event.currentTarget,
              )
            }
          >
            {item.name}
          </button>
        ) : (
          <a href={`/lineup/${item.id}`}>{item.name}</a>
        )}
      </h2>
      <p className="pf-lineup-meta">
        {kind === "mine" ? "更新于" : item.owner_nickname + " ·"}{" "}
        {time(item.history_at || item.updated_at)}
      </p>
      <div className="pf-lineup-card-bottom">
        <span className="pf-interactions">
          <span>
            <Heart size={13} />
            {number(item.like_count)}
          </span>
          <span>
            <Copy size={13} />
            {number(item.copy_count)}
          </span>
        </span>
        <div className="pf-card-actions">
          {kind === "mine" ? (
            <button
              className="pf-button"
              onClick={(event) =>
                dialogs.open(
                  {
                    kind: item.status === "banned" ? "moderation" : "edit",
                    id: item.id,
                  },
                  event.currentTarget,
                )
              }
            >
              {item.status === "banned" ? "查看封禁与重审" : "编辑阵容"}
              <ChevronRight size={13} />
            </button>
          ) : (
            <>
              {kind === "favorites" && (
                <button
                  className="pf-icon-button pf-bookmarked"
                  aria-label={`取消收藏：${item.name}`}
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await window.JccAccount.request(
                        `/api/lineups/${item.id}/favorite`,
                        {
                          method: "DELETE",
                          headers: { "X-CSRF-Token": token },
                        },
                      );
                      window.jccNotify.show("已取消收藏", {
                        variant: "success",
                      });
                      refresh();
                    } catch (error) {
                      window.jccNotify.show((error as Error).message, {
                        variant: "error",
                      });
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <Bookmark size={15} />
                </button>
              )}
              <CopyButton item={item} token={token} />
            </>
          )}
        </div>
      </div>
    </article>
  );
}

function ReportCard({ item }: { item: Report }) {
  return (
    <article className="pf-lineup-card pf-report-card">
      <div className="pf-lineup-card-top">
        <span className="pf-lineup-meta">失效反馈</span>
        <span className={cn("pf-status", `pf-status-${item.status}`)}>
          {reportStatusText[item.status] || item.status}
        </span>
      </div>
      <h2>
        {["deleted", "banned", "hidden"].includes(item.lineup_status) ? (
          item.lineup_name
        ) : (
          <a href={`/lineup/${item.lineup_id}`}>{item.lineup_name}</a>
        )}
      </h2>
      <p className="pf-report-reason">{item.reason}</p>
      <div className="pf-report-meta">
        <span>
          阵容状态：{lineupStatusText[item.lineup_status] || item.lineup_status}
        </span>
        <span>提交：{time(item.created_at)}</span>
        {item.handled_at && <span>处理：{time(item.handled_at)}</span>}
      </div>
    </article>
  );
}
