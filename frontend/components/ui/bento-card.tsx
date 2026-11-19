import React, { useEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  LayoutGroup,
  motion,
  useReducedMotion,
} from "motion/react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Bookmark,
  ChevronLeft,
  ChevronRight,
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
  Sun,
  UserRound,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useResource } from "@/lib/account-api";
import {
  AccountDialogsProvider,
  useAccountDialogs,
} from "@/components/ui/account-dialogs";

type AvatarConfig = {
  version: 1;
  preset: "strobi" | "freddy" | "citrus" | "nova" | "sunee" | "cloudee" | "sprout" | "bloom";
  expression: "neutral" | "happy" | "wink" | "sleepy" | "curious" | "surprised" | "shy" | "determined";
  color: string;
};
type User = {
  id: number;
  username: string;
  nickname: string;
  role: string;
  avatar_color: string;
  avatar_config?: AvatarConfig | null;
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
  feedback_id?: number;
  feedback_status?: string;
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
  // Deck figures are reported separately so lineup totals keep their meaning.
  decks?: {
    decks: number;
    published_decks: number;
    draft_decks: number;
    hidden_decks: number;
    received_likes: number;
    received_favorites: number;
    contributed_decks?: number;
    submissions_active?: number;
    submissions_needs_info?: number;
  };
};
type Deck = {
  id: number;
  name: string;
  plan_code: string;
  lineup_code: string;
  status: string;
  portal: { id: string; name: string };
  energy: number;
  energy_limit: number;
  copy_count: number;
  like_count: number;
  favorite_count: number;
  is_favorited: boolean;
  updated_at: string;
  published_at?: string | null;
  detail_url: string;
  author: { nickname: string; credit?: string };
  can_edit?: boolean;
  cards: ({ name: string } | null)[];
};
type DeckPage = { items: Deck[]; total: number; total_pages: number; page: number };
type Content = "lineups" | "decks";
type Failure = Error & { status?: number };
declare global {
  interface Window {
    JccAccount: {
      request: <T>(url: string, options?: RequestInit) => Promise<T>;
      copy: (lineup: Lineup, token: string) => Promise<void>;
      copyText: (text: string) => Promise<boolean>;
    };
    jccAvatar: {
      image: (
        configOrColor?: AvatarConfig | string | null,
        size?: number,
        alt?: string,
        key?: string,
      ) => HTMLElement;
      getAvatarDataUrl: (
        seed?: string,
        options?: { config?: AvatarConfig | null; color?: string; size?: number },
      ) => string;
      normalize: (configOrColor?: AvatarConfig | string | null) => AvatarConfig;
      presets: Record<AvatarConfig["preset"], { name: string }>;
      expressions: Record<AvatarConfig["expression"], { name: string }>;
      palettes: Record<string, { mid: string; name: string }>;
      feedback: (node: HTMLElement, kind?: "copy" | "like") => void;
    };
    jccAvatarEditor: {
      mount: (
        user: User,
        token: string,
        options: {
          trigger: HTMLButtonElement;
          onSave: (user: User) => void;
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
  { id: "overview", label: "个人概览", icon: LayoutDashboard },
  { id: "mine", label: "我的阵容", icon: Layers3 },
  { id: "favorites", label: "我的收藏", icon: Bookmark },
  { id: "views", label: "最近浏览", icon: Eye },
  { id: "copies", label: "最近复制", icon: Copy },
  { id: "reports", label: "我的失效反馈", icon: MessageSquare },
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
// "#mine/decks" opens a collection on its deck list; the tab itself is the first segment.
const tabFromHash = (): Tab =>
  TABS.find((tab) => `#${tab.id}` === location.hash.split("/")[0])?.id ||
  "overview";
const contentFromHash = (): Content =>
  location.hash.endsWith("/decks") ? "decks" : "lineups";
const deckStatusText: Record<string, string> = {
  draft: "草稿",
  published: "公开",
  hidden: "已隐藏",
};
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
  title = "还没有阵容",
  mine = false,
}: {
  title?: string;
  mine?: boolean;
}) {
  return (
    <div className="pf-empty">
      <Layers3 size={30} />
      <strong>{title}</strong>
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
        config: user.avatar_config,
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
      ownerId={session.data.user.id}
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
      onSave: (savedUser) => setUser(savedUser),
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
  function navigate(id: Tab, content: Content = "lineups") {
    const hash = content === "decks" ? `${id}/decks` : id;
    if (location.hash !== `#${hash}`) location.hash = hash;
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
          <span>金铲铲阵容库</span>
        </a>
        <div className="pf-side-identity">
          <Avatar user={user} size={36} />
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
              </button>
            ))}
          </LayoutGroup>
        </nav>
        <div className="pf-sidebar-bottom">
          {user.role !== "admin" && (
            <a
              className="pf-side-link"
              href={`/author/${encodeURIComponent(user.username)}`}
            >
              <UserRound size={18} />
              公开主页
            </a>
          )}
          <a className="pf-side-link" href="/">
            <ArrowLeft size={18} />
            返回阵容库
          </a>
          <button
            className="pf-side-link"
            disabled={loggingOut}
            onClick={logout}
          >
            <LogOut size={18} />
            {loggingOut ? "正在退出…" : "退出登录"}
          </button>
        </div>
      </aside>
      <div className="pf-main">
        <header className="pf-topbar">
          <h1 className="pf-title">{tab.label}</h1>
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
                  : "通知中心"
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
              发布
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
                <Overview token={token} navigate={navigate} />
              ) : (
                <Collection
                  key={active}
                  kind={active}
                  token={token}
                  navigate={navigate}
                />
              )}
            </motion.section>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function Overview({
  token,
  navigate,
}: {
  token: string;
  navigate: (id: Tab, content?: Content) => void;
}) {
  const dialogs = useAccountDialogs();
  const dashboard = useResource<Dashboard>(
    "/api/me/dashboard",
    dialogs.dataRevision,
  );
  const views = useResource<Lineup[]>("/api/me/recent-views");
  const data = dashboard.data;
  const decks = data?.decks;
  const count = (value?: number) =>
    data ? number(value || 0) : "—";
  const stats = [
    {
      label: "我的作品",
      value: data && data.published_lineups + (decks?.decks || 0),
      target: "mine" as Tab,
    },
    {
      label: "收到点赞",
      value: data && data.received_likes + (decks?.received_likes || 0),
    },
    {
      label: "收到收藏",
      value:
        data && data.received_favorites + (decks?.received_favorites || 0),
    },
    { label: "收到复制", value: data?.received_copies },
  ];
  return (
    <div className="pf-overview">
      {dashboard.error ? (
        <ErrorState error={dashboard.error} retry={dashboard.retry} />
      ) : (
        <div className="pf-stats" aria-busy={dashboard.loading}>
          {stats.map((stat) => {
            const body = (
              <>
                <span>{stat.label}</span>
                <strong>
                  {stat.value === undefined ? "—" : number(stat.value)}
                </strong>
              </>
            );
            return stat.target ? (
              <button
                className="pf-stat"
                key={stat.label}
                onClick={() => navigate(stat.target!)}
              >
                {body}
              </button>
            ) : (
              <article className="pf-stat" key={stat.label}>
                {body}
              </article>
            );
          })}
        </div>
      )}
      <div className="pf-bento-grid">
        <section className="pf-card pf-recent" aria-labelledby="pf-recent-title">
          <div className="pf-card-heading">
            <h2 id="pf-recent-title">最近浏览</h2>
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
            <Empty title="还没有浏览记录" />
          ) : (
            <div className="pf-recent-list">
              {views.data.slice(0, 3).map((item) => (
                <div className="pf-recent-row" key={item.id}>
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
        <section className="pf-card pf-notebook" aria-labelledby="pf-status-title">
          <div className="pf-card-heading">
            <h2 id="pf-status-title">状态</h2>
          </div>
          <div className="pf-notebook-lines">
            <button onClick={() => navigate("mine")}>
              <span>隐藏阵容</span>
              <strong>{count(data?.hidden_lineups)}</strong>
              <ChevronRight size={14} />
            </button>
            <button onClick={() => navigate("mine")}>
              <span>阵容待处理反馈</span>
              <strong>{count(data?.pending_reports_on_my_lineups)}</strong>
              <ChevronRight size={14} />
            </button>
            <button onClick={() => navigate("mine", "decks")}>
              <span>卡组草稿</span>
              <strong>{decks ? number(decks.draft_decks) : "—"}</strong>
              <ChevronRight size={14} />
            </button>
            <a href="/me/deck-submissions">
              <span>卡组投稿</span>
              <strong>
                {decks ? number(decks.submissions_active || 0) : "—"}
                {decks?.submissions_needs_info ? ` · ${number(decks.submissions_needs_info)} 待补充` : ""}
              </strong>
              <ChevronRight size={14} />
            </a>
            <button onClick={() => navigate("reports")}>
              <span>我的失效反馈</span>
              <strong>{count(data?.submitted_reports)}</strong>
              <ChevronRight size={14} />
            </button>
          </div>
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
  navigate,
}: {
  kind: Exclude<Tab, "overview">;
  token: string;
  navigate: (id: Tab, content?: Content) => void;
}) {
  const [page, setPage] = useState(1),
    [draft, setDraft] = useState(""),
    [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const paginated = kind === "mine" || kind === "favorites";
  const [content, setContent] = useState<Content>(
    paginated ? contentFromHash() : "lineups",
  );
  useEffect(() => {
    const sync = () => paginated && setContent(contentFromHash());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [paginated]);
  const decks = paginated && content === "decks";
  const url = decks
    ? `/api/orange-decks?tab=${kind}&page=${page}&page_size=${PAGE_SIZE}&q=${encodeURIComponent(query)}`
    : paginated
      ? `/api/lineups?view=${kind}&page=${page}&page_size=${PAGE_SIZE}&q=${encodeURIComponent(query)}`
      : kind === "reports"
        ? "/api/me/reports"
        : `/api/me/recent-${kind}`;
  const dialogs = useAccountDialogs();
  const result = useResource<Page | DeckPage | Lineup[] | Report[]>(
    url,
    dialogs.dataRevision,
  );
  const payload = paginated
    ? (result.data as Page | DeckPage | undefined)
    : undefined;
  const all: (Lineup | Deck | Report)[] = paginated
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
      {paginated && (
        <div className="pf-filters" role="group" aria-label="内容类型">
          {(
            [
              ["lineups", "阵容码"],
              ["decks", "大橘大利卡组"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              className={cn(content === id && "is-active")}
              aria-pressed={content === id}
              onClick={() => {
                setPage(1);
                navigate(kind, id);
                setContent(id);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}
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
              kind === "reports"
                ? "搜索阵容或反馈原因"
                : decks
                  ? "搜索卡组或卡名"
                  : "搜索阵容"
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
            ) : decks ? (
              <div className="pf-empty">
                <Layers3 size={30} />
                <strong>
                  {kind === "mine" ? "还没有你的卡组" : "还没有收藏卡组"}
                </strong>
                <a
                  className="pf-button"
                  href={
                    kind === "mine" ? "/lineup/new?type=deck" : "/?library=decks"
                  }
                >
                  {kind === "mine" ? "发布第一套卡组" : "浏览卡组库"}
                  <ArrowUpRight size={15} />
                </a>
              </div>
            ) : (
              <Empty
                mine={kind === "mine"}
                title={
                  kind === "reports"
                    ? "还没有失效反馈"
                    : kind === "favorites"
                      ? "还没有收藏阵容"
                      : kind === "mine"
                        ? "还没有你的阵容"
                        : "还没有记录"
                }
              />
            )
          ) : (
            <div className="pf-collection-grid">
              {items.map((item) =>
                "lineup_name" in item ? (
                  <ReportCard key={item.id} item={item} />
                ) : "portal" in item ? (
                  <DeckCard
                    key={item.id}
                    item={item}
                    kind={kind}
                    token={token}
                    refresh={result.retry}
                  />
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
          {total > 0 && (
            <Pager
              page={currentPage}
              pages={pages}
              total={total}
              onPage={changePage}
            />
          )}
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
        {item.rank_level && <span className="pf-rank">{item.rank_level}</span>}
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

function DeckCard({
  item,
  kind,
  token,
  refresh,
}: {
  item: Deck;
  kind: string;
  token: string;
  refresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [copyingCodes, setCopyingCodes] = useState<Record<string, boolean>>({});
  const names = item.cards.map((card) => card?.name || "—").join(" · ");
  const [copiedCount, setCopiedCount] = useState(0);
  async function copyCode(type: "plan" | "lineup", label: string, code: string) {
    setCopyingCodes(previous => ({ ...previous, [type]: true }));
    try {
      const ok = await window.JccAccount.copyText(code);
      window.jccNotify.show(ok ? `${label}已复制` : "复制失败，请到详情页手动复制", { variant: ok ? "success" : "error" });
      if (ok && item.status === "published") {
        try {
          // One action ID per copy gesture keeps a retried request from counting twice.
          const action_id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
          const data = await window.JccAccount.request<{ copy_count: number }>(`/api/orange-decks/${item.id}/copy?code_type=${type}&source=account`, {
            method: "POST", headers: { "X-CSRF-Token": token, "Content-Type": "application/json" }, body: JSON.stringify({ action_id }),
          });
          setCopiedCount(previous => Math.max(previous, data.copy_count));
        } catch {
          window.jccNotify.show(`${label}已复制，但次数未同步，请稍后刷新`, { variant: "warning" });
        }
      }
    } catch {
      window.jccNotify.show("复制失败，请到详情页手动复制", { variant: "error" });
    } finally { setCopyingCodes(previous => ({ ...previous, [type]: false })); }
  }
  // Both code slots always show, so cards share one height; a missing code is disabled and named.
  const codes = (
    <div className="pf-deck-codes" role="group" aria-label="复制游戏代码">
      {([["plan", "方案码", item.plan_code], ["lineup", "阵容码", item.lineup_code]] as const).map(([type, label, code]) => (
        <button
          key={type}
          className="pf-deck-code"
          disabled={!code || busy || copyingCodes[type]}
          aria-label={code ? `复制${label}：${item.name}` : `未提供${label}`}
          title={code ? `复制${label}` : `未提供${label}`}
          onClick={() => code && copyCode(type, label, code)}
        >
          <Copy size={13} />
          {label}
        </button>
      ))}
    </div>
  );
  return (
    <article className="pf-lineup-card pf-deck-card" data-deck-id={item.id}>
      <div className="pf-lineup-card-top">
        <span className={cn("pf-portal", `pf-portal-${item.portal.id}`)}>
          {item.portal.name}
        </span>
        <span className={cn("pf-status", `pf-status-${item.status}`)}>
          {kind === "mine"
            ? deckStatusText[item.status] || item.status
            : `能量 ${item.energy} / ${item.energy_limit}`}
        </span>
      </div>
      <h2>
        {item.status === "draft" ? (
          <a href={`/orange-decks/${item.id}/edit`}>{item.name}</a>
        ) : (
          <a href={item.detail_url}>{item.name}</a>
        )}
      </h2>
      <p className="pf-lineup-meta pf-deck-names" title={names}>{names}</p>
      <div className="pf-lineup-card-bottom">
        <span className="pf-interactions">
          <span>
            <Heart size={13} />
            {number(item.like_count)}
          </span>
          <span>
            <Bookmark size={13} />
            {number(item.favorite_count)}
          </span>
          <span title="卡组有效复制次数">
            <Copy size={13} />
            {number(Math.max(item.copy_count, copiedCount))}
          </span>
        </span>
        <div className="pf-card-actions">
          {codes}
          {kind === "mine" && item.can_edit === false ? (
            <a className="pf-button" href={item.detail_url} title="由你提供、管理员完善发布的卡组">
              我提供的
              <ChevronRight size={13} />
            </a>
          ) : kind === "mine" ? (
            <a className="pf-button" href={`/orange-decks/${item.id}/edit`}>
              编辑卡组
              <ChevronRight size={13} />
            </a>
          ) : (
            <>
              <button
                className="pf-icon-button pf-bookmarked"
                aria-label={`取消收藏：${item.name}`}
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await window.JccAccount.request(
                      `/api/orange-decks/${item.id}/favorite`,
                      {
                        method: "DELETE",
                        headers: { "X-CSRF-Token": token },
                      },
                    );
                    window.jccNotify.show("已取消收藏", { variant: "success" });
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
              <a className="pf-button" href={item.detail_url}>
                查看卡组
                <ArrowUpRight size={13} />
              </a>
            </>
          )}
        </div>
      </div>
    </article>
  );
}

function ReportCard({ item }: { item: Report }) {
  const dialogs = useAccountDialogs();
  return (
    <article className="pf-lineup-card pf-report-card">
      <div className="pf-lineup-card-top">
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
      {item.feedback_id && <button className="pf-button" onClick={event => dialogs.open({kind:"feedback",id:item.feedback_id!},event.currentTarget)}>{item.feedback_status === "in_progress" ? "核实中 · " : ""}查看进度与回复</button>}
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
