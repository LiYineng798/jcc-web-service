import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowLeft,
  Bell,
  Heart,
  MessageCircle,
  Bookmark,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FilePenLine,
  ShieldAlert,
  X,
} from "lucide-react";
import { useResource } from "@/lib/account-api";
import { AvatarCircles } from "./avatar-circles";
import "./account-dialogs.css";

type Content = { name: string; code: string; season_id: string };
type Moderation = {
  state: string;
  reason: string;
  review_note: string;
  prior_status: string;
  notice_state: string;
  revision: number;
  updated_at: string;
  submitted_at?: string;
  proposal: Content | null;
};
type RecordData = {
  lineup: Content & { id: number; version: number; status: string };
  moderation: Moderation | null;
  events: {
    id: number;
    action: string;
    reason: string;
    created_at: string;
    before: Content;
    after: Content;
  }[];
};
type EditorData = RecordData["lineup"] & {
  can_edit: boolean;
  moderation?: Moderation;
};
type Actors = { total:number; users:{nickname:string;avatar_config:Parameters<typeof window.jccAvatar.image>[0]}[] };
declare global { interface Window { JccNoticeView: { actors:(actors?:Actors,expanded?:boolean)=>HTMLElement; interaction:(item:Notice,target:HTMLElement)=>void; feedback:(data:FeedbackData,target:HTMLElement,admin?:boolean)=>void; }; } }
type Notice = {
  actors?:Actors;
  state: string;
  revision: number;
  notice_state: string;
  updated_at: string;
  id: string;
  category: string;
  kind: string;
  feedback_id: number | null;
  url: string;
  body: string;
  event_count: number;
  new_count: number;
  lineup_id: number;
  name: string;
  lineup_status: string;
};
type Notices = {
  items: Notice[];
  counts: { unread?: number; read?: number };
  unread_total: number;
  total: number;
  page: number;
  total_pages: number;
};
type Seasons = { seasons: { id: string; name: string }[] };
type Screen =
  | { kind: "notifications" }
  | { kind: "feedback"; id: number }
  | { kind: "interaction"; notice: Notice }
  | { kind: "moderation"; id: number; seed?: RecordData }
  | { kind: "edit"; id: number };
type Failure = Error & { status?: number };
type DialogContext = {
  open: (screen: Screen, opener?: HTMLElement) => void;
  dataRevision: number;
  unread: number;
  countError: boolean;
};
const Context = createContext<DialogContext | null>(null);
const labels: Record<string, string> = {
  normal: "公开",
  hidden: "已隐藏",
  banned: "已封禁",
  pending: "待审核",
  rejected: "已退回",
  approved: "审核通过",
  released: "已解除封禁",
  deleted: "已删除",
};
const actions: Record<string, string> = {
  ban: "封禁阵容",
  submit: "提交修改",
  approve: "审核通过",
  reject: "退回修改",
  release: "解除封禁",
};
const date = (value?: string) => value?.replace("T", " ").slice(0, 16) || "—";
const headers = (token: string) => ({
  "Content-Type": "application/json",
  "X-CSRF-Token": token,
});

export function useAccountDialogs() {
  const context = useContext(Context);
  if (!context) throw new Error("Profile dialogs require their provider");
  return context;
}

export function AccountDialogsProvider({
  token,
  children,
}: {
  token: string;
  children: React.ReactNode;
}) {
  const [entry, setEntry] = useState<Screen | null>(null);
  const [dataRevision, setDataRevision] = useState(0);
  const [noticeRevision, setNoticeRevision] = useState(0);
  const opener = useRef<HTMLElement | null>(null);
  const counts = useResource<Notices>(
    "/api/me/notifications?status=all&page=1&page_size=1",
    noticeRevision,
  );
  const open = useCallback((screen: Screen, source?: HTMLElement) => {
    opener.current = source || (document.activeElement as HTMLElement);
    setNoticeRevision((value) => value + 1);
    setEntry(screen);
  }, []);
  const noticesChanged = useCallback(
    () => setNoticeRevision((value) => value + 1),
    [],
  );
  const dataChanged = useCallback(() => {
    setDataRevision((value) => value + 1);
    noticesChanged();
  }, [noticesChanged]);
  const close = useCallback((saved = false) => {
    setEntry(null);
    if (location.hash === "#lineup-notifications")
      history.replaceState(
        history.state,
        "",
        location.pathname + location.search,
      );
    requestAnimationFrame(() => {
      const target =
        !saved && opener.current?.isConnected
          ? opener.current
          : document.querySelector<HTMLElement>(
              '.pf-tab[aria-selected="true"]',
            );
      target?.focus({ preventScroll: true });
    });
  }, []);
  return (
    <Context.Provider
      value={{
        open,
        dataRevision,
        unread: counts.data?.unread_total || 0,
        countError: Boolean(counts.error),
      }}
    >
      {children}
      {entry && (
        <DialogWorkspace
          entry={entry}
          token={token}
          close={close}
          dataChanged={dataChanged}
          noticesChanged={noticesChanged}
          noticeRevision={noticeRevision}
        />
      )}
    </Context.Provider>
  );
}

function DialogWorkspace({
  entry,
  token,
  close,
  dataChanged,
  noticesChanged,
  noticeRevision,
}: {
  entry: Screen;
  token: string;
  close: (saved?: boolean) => void;
  dataChanged: () => void;
  noticesChanged: () => void;
  noticeRevision: number;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const [stack, setStack] = useState<Screen[]>(() => {
    const incoming=new URLSearchParams(location.search).get('notice');
    return entry.kind==='notifications' && incoming?.match(/^moderation:\d+$/) ? [entry,{kind:'moderation',id:Number(incoming.split(':')[1])}] : [entry];
  });
  const listPosition=useRef({scroll:0,key:''});
  const restoring=useRef(false);
  const historyKey=useRef(`notice-${Date.now()}-${Math.random()}`);
  const closingFromHistory=useRef(false);
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false);
  const [discard, setDiscard] = useState<"close" | "back" | null>(null);
  const [noticeView, setNoticeView] = useState({ status: "all", category: "all", page: 1 });
  const screen = stack[stack.length - 1];
  const backgroundPointer = useRef(false);
  useEffect(() => {
    const back = () => {
      if (history.state?.jccAccountDetail === historyKey.current || stack.length < 2) return;
      if (closingFromHistory.current) { closingFromHistory.current=false;close();return; }
      // A browser Back must not discard an editor draft or interrupt a save.
      if (dirty || busy || stack.at(-1)?.kind === 'edit') {
        history.pushState({...history.state,jccAccountDetail:historyKey.current},'');
        if (!busy) leave('back');
        return;
      }
      restoring.current=true;
      setStack(value=>value.slice(0,-1));
    };
    window.addEventListener('popstate',back);
    return ()=>window.removeEventListener('popstate',back);
  },[stack,dirty,busy,close]);
  useEffect(() => {
    const node = dialog.current!;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    node.showModal();
    const url=new URL(location.href);
    if(url.searchParams.has('notice')){
      url.searchParams.delete('notice');history.replaceState(history.state,'',url);
    }
    return () => {
      node.close();
      document.body.style.overflow = previousOverflow;
    };
  }, []);
  useEffect(() => {
    if(screen.kind!=="notifications")body.current?.scrollTo(0, 0);
    dialog.current
      ?.querySelector<HTMLElement>(".pf-dialog-title")
      ?.focus({ preventScroll: true });
  }, [screen]);
  function leave(target: "close" | "back") {
    if (busy) return;
    if (dirty) {
      setDiscard(target);
      return;
    }
    finishLeave(target);
  }
  function finishLeave(target: "close" | "back") {
    setDirty(false);
    setDiscard(null);
    if(history.state?.jccAccountDetail===historyKey.current && (target==='close' || (stack.length===2 && stack[0].kind==='notifications'))){
      closingFromHistory.current=target==='close';history.back();return;
    }
    if (target === "close") close();
    else {restoring.current=true;setStack((value) => value.slice(0, -1));}
  }
  function go(next: Screen) {
    if(screen.kind==='notifications')listPosition.current={scroll:body.current?.scrollTop||0,key:document.activeElement?.closest('[data-notice-id]')?.getAttribute('data-notice-id')||''};
    if(screen.kind==='notifications')history.pushState({...history.state,jccAccountDetail:historyKey.current},'');
    setDirty(false);
    setStack((value) => [...value, next]);
  }
  function saved(record?: RecordData) {
    setDirty(false);
    setBusy(false);
    dataChanged();
    if (!record) {
      close(true);
      return;
    }
    setStack((value) => {
      const parent = value.at(-2);
      return [
        ...value.slice(0, parent?.kind === "moderation" ? -2 : -1),
        { kind: "moderation", id: record.lineup.id, seed: record },
      ];
    });
  }
  const title =
    screen.kind === "notifications"
      ? "通知中心"
      : screen.kind === "moderation"
        ? "封禁与重审详情"
        : screen.kind === "feedback" ? "反馈进度与回复" : screen.kind === "interaction" ? "收到的互动" : "编辑阵容";
  return (
    <dialog
      ref={dialog}
      className="pf-dialog"
      aria-labelledby="pfDialogTitle"
      onCancel={(event) => {
        event.preventDefault();
        leave(stack.length>1?"back":"close");
      }}
      onPointerDown={(event) => {
        backgroundPointer.current = event.target === event.currentTarget;
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && backgroundPointer.current)
          leave("close");
        backgroundPointer.current = false;
      }}
    >
      <header className="pf-dialog-header">
        <div className="pf-dialog-heading">
          <span className="pf-dialog-symbol">
            {screen.kind === "notifications" ? (
              <Bell size={22} />
            ) : screen.kind === "feedback" ? (
              <MessageCircle size={22} />
            ) : screen.kind === "interaction" ? (
              screen.notice.kind === "favorite" ? <Bookmark size={22} /> : screen.notice.kind === "copy" ? <Copy size={22} /> : <Heart size={22} />
            ) : screen.kind === "edit" ? (
              <FilePenLine size={22} />
            ) : (
              <ShieldAlert size={22} />
            )}
          </span>
          <div>

            <h2 className="pf-dialog-title" id="pfDialogTitle" tabIndex={-1}>
              {title}
            </h2>
          </div>
        </div>
        <button
          className="pf-icon-button"
          aria-label="关闭浮窗"
          disabled={busy}
          onClick={() => leave("close")}
        >
          <X size={20} />
        </button>
      </header>
      {stack.length > 1 && (
        <div className="pf-dialog-back">
          <button
            className="pf-text-button"
            disabled={busy}
            onClick={() => leave("back")}
          >
            <ArrowLeft size={14} />
            {stack.at(-2)?.kind === "notifications"
              ? "返回通知列表"
              : "返回处理详情"}
          </button>
        </div>
      )}
      {discard && (
        <div className="pf-discard" role="alert">
          <div>
            <strong>还有未保存的修改</strong>
            <p>继续编辑，或放弃本次修改后离开。</p>
          </div>
          <button
            className="pf-button"
            autoFocus
            onClick={() => setDiscard(null)}
          >
            继续编辑
          </button>
          <button className="pf-button" onClick={() => finishLeave(discard)}>
            放弃修改
          </button>
        </div>
      )}
      <div className="pf-dialog-body" ref={body}>
        {screen.kind === "notifications" ? (
          <NotificationList
            token={token}
            revision={noticeRevision}
            view={noticeView}
            setView={setNoticeView}
            changed={noticesChanged}
            go={go}
            restored={() => {if(restoring.current){restoring.current=false;requestAnimationFrame(()=>{body.current?.scrollTo(0,listPosition.current.scroll);body.current?.querySelector<HTMLElement>(`[data-notice-id="${listPosition.current.key}"] .pf-notice-open`)?.focus({preventScroll:true});});}}}
          />
        ) : screen.kind === "moderation" ? (
          <ModerationDetail
            key={`detail-${screen.id}-${screen.seed?.lineup.version || 0}`}
            screen={screen}
            token={token}
            changed={noticesChanged}
            go={go}
          />
        ) : screen.kind === "feedback" ? (
          <FeedbackDetail id={screen.id} token={token} changed={noticesChanged} />
        ) : screen.kind === "interaction" ? (
          <InteractionDetail item={screen.notice} token={token} changed={noticesChanged} />
        ) : (
          <Editor
            key={`edit-${screen.id}`}
            id={screen.id}
            token={token}
            setDirty={setDirty}
            setBusy={setBusy}
            saved={saved}
            cancel={() => leave(stack.length > 1 ? "back" : "close")}
          />
        )}
      </div>
    </dialog>
  );
}

function Loading() {
  return (
    <div className="pf-loading" role="status" aria-label="浮窗内容加载中">
      <span />
      <span />
      <span />
    </div>
  );
}
function FailureView({ error, retry }: { error: Failure; retry: () => void }) {
  return (
    <div className="pf-empty" role="alert">
      <ShieldAlert size={26} />
      <strong>暂时无法加载</strong>
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
function Status({ value }: { value: string }) {
  return (
    <span className={`pf-dialog-status pf-dialog-status-${value}`}>
      {labels[value] || value}
    </span>
  );
}

function NotificationList({
  token,
  revision,
  view,
  setView,
  changed,
  go,
  restored,
}: {
  restored:()=>void;
  token: string;
  revision: number;
  view: { status: string; category: string; page: number };
  setView: React.Dispatch<
    React.SetStateAction<{ status: string; category: string; page: number }>
  >;
  changed: () => void;
  go: (screen: Screen) => void;
}) {
  const result = useResource<Notices>(
    `/api/me/notifications?category=${view.category}&status=${view.status}&page=${view.page}&page_size=6`,
    revision,
  );
  useEffect(() => {
    if (result.data && result.data.page !== view.page)
      setView((value) => ({ ...value, page: result.data!.page }));
  }, [result.data, view.page, setView]);
  useEffect(()=>{if(result.data&&!result.loading)restored();},[result.data,result.loading]);
  return (
    <section className="pf-inbox">
      <div className="pf-inbox-toolbar">
        <div className="pf-inbox-filters" role="group" aria-label="通知分类">
          {[["all","全部"],["interaction","互动"],["feedback","反馈"],["moderation","审核"]].map(([value,label]) => (
            <button key={value} aria-pressed={view.category === value} onClick={() => setView(v => ({...v,category:value,page:1}))}>{label}</button>
          ))}
        </div>
        <select className="pf-inbox-status" aria-label="通知状态" value={view.status} onChange={e=>setView(v=>({...v,status:e.target.value,page:1}))}>
          <option value="all">全部状态</option><option value="unread">仅未读</option><option value="read">已读</option>
        </select>
      </div>
      {result.error ? (
        <FailureView error={result.error} retry={result.retry} />
      ) : result.loading ? (
        <Loading />
      ) : (
        <>
          <div className="pf-notice-list">
            {result.data?.items.length ? (
              result.data.items.map((item) => (
                <NoticeRow
                  key={`${item.id}-${item.revision}-${item.notice_state}`}
                  item={item}
                  token={token}
                  changed={changed}
                  go={go}
                />
              ))
            ) : (
              <div className="pf-empty">
                <Bell size={28} />
                <strong>
                  {view.status === "unread"
                    ? "没有未读通知"
                    : view.status === "read"
                      ? "还没有已读通知"
                      : "暂时没有通知"}
                </strong>
                <p>收到互动、反馈回复或审核结果时会在这里展示。</p>
              </div>
            )}
          </div>
          <div className="pf-pagination">
            <span>共 {result.data?.total || 0} 条通知</span>
            <div>
              <button
                className="pf-icon-button"
                aria-label="通知上一页"
                disabled={view.page <= 1}
                onClick={() =>
                  setView((value) => ({ ...value, page: value.page - 1 }))
                }
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                {result.data?.page || 1} / {result.data?.total_pages || 1}
              </span>
              <button
                className="pf-icon-button"
                aria-label="通知下一页"
                disabled={view.page >= (result.data?.total_pages || 1)}
                onClick={() =>
                  setView((value) => ({ ...value, page: value.page + 1 }))
                }
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function NoticeRow({
  item,
  token,
  changed,
  go,
}: {
  item: Notice;
  token: string;
  changed: () => void;
  go: (screen: Screen) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const controller = useRef(new AbortController());
  useEffect(() => () => controller.current.abort(), []);
  const next = item.notice_state === "unread" ? "read" : "unread";
  return (
    <article
      className={`pf-notice-row ${item.notice_state === "unread" ? "is-unread" : ""}`}
      data-notice-id={item.id}
    >
      <button
        className="pf-notice-open"
        onClick={() => go(item.kind === "feedback" ? {kind:"feedback",id:item.feedback_id!} : item.kind === "moderation" ? { kind: "moderation", id: item.lineup_id } : {kind:"interaction",notice:item})}
      >
        <span className={`nc-icon nc-${item.kind}`}>
          {item.kind === "favorite" ? <Bookmark size={19} /> : item.kind === "copy" ? <Copy size={19} /> : item.kind === "like" ? <Heart size={19} /> : item.kind === "feedback" ? <MessageCircle size={19} /> : ["approved", "released"].includes(item.state) ? (
            <Check size={19} />
          ) : item.state === "pending" ? (
            <Clock3 size={19} />
          ) : (
            <ShieldAlert size={19} />
          )}
        </span>
        <span className="pf-notice-text">
          <strong>{item.name}</strong>
          <span>
            {item.kind === "moderation" ? <Status value={item.state} /> : <span className="pf-dialog-status">{item.kind === "feedback" ? "反馈进度" : ({like:"收到点赞",favorite:"收到收藏",copy:"收到复制"} as Record<string,string>)[item.kind]}</span>}
            <time>{date(item.updated_at)}</time>
          </span>
          <p>
            {item.body}
          </p>
          {item.category==='interaction'&&<ActorStack actors={item.actors}/>}
        </span>
        <ChevronRight size={16} />
      </button>
      <button
        className="pf-read-button"
        disabled={busy}
        aria-label={next === "read" ? "标记已读" : "标记未读"}
        title={next === "read" ? "标记已读" : "标记未读"}
        onClick={async () => {
          if (busy) return;
          setBusy(true);
          setError("");
          try {
            await window.JccAccount.request(
              `/api/me/notifications/${item.id}`,
              {
                method: "PUT",
                headers: headers(token),
                body: JSON.stringify({ status: next, revision: item.revision }),
                signal: controller.current.signal,
              },
            );
            if (!controller.current.signal.aborted) changed();
          } catch (failure) {
            if (!controller.current.signal.aborted)
              setError((failure as Error).message);
          } finally {
            if (!controller.current.signal.aborted) setBusy(false);
          }
        }}
      >
        <span />
      </button>
      {error && (
        <p className="pf-form-error" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}

function ActorStack({actors}:{actors?:Actors}) {
  if (!actors?.users.length) return null;
  const names=actors.users.slice(0,2).map(user=>user.nickname).join('、');
  return <span className="nc-people">
    <AvatarCircles
      avatarUrls={actors.users.map(user=>window.jccAvatar.getAvatarDataUrl('',{config:window.jccAvatar.normalize(user.avatar_config)}))}
      avatarNames={actors.users.map(user=>user.nickname)}
      numPeople={Math.max(0,actors.total-actors.users.length)}
    />
    <span className="nc-people-caption">{names}{actors.total>2?` 等 ${actors.total} 位棋友`:''}</span>
  </span>;
}
type FeedbackData = {
  title:string;content:string;status:string;
  notification:{id:string;revision:number;notice_state:string}|null;
  events:{id:number;actor_role:string;status:string;body:string;created_at:string}[];
};
function useMarkDisplayed(notice:{id:string;revision:number;notice_state:string}|null|undefined, token:string, changed:()=>void) {
  useEffect(() => {
    if (!notice || notice.notice_state !== "unread") return;
    const controller = new AbortController();
    window.JccAccount.request(`/api/me/notifications/${notice.id}`, {
      method:"PUT",headers:headers(token),body:JSON.stringify({status:"read",revision:notice.revision}),signal:controller.signal,
    }).then(() => {if(!controller.signal.aborted)changed();}).catch(() => {});
    return () => controller.abort();
  }, [notice?.id,notice?.revision,notice?.notice_state,token,changed]);
}
function FeedbackDetail({id,token,changed}:{id:number;token:string;changed:()=>void}) {
  const result=useResource<FeedbackData>(`/api/me/feedback/${id}`);
  const ref=useRef<HTMLDivElement>(null);
  useMarkDisplayed(result.data?.notification,token,changed);
  useEffect(()=>{if(result.data&&ref.current)window.JccNoticeView.feedback(result.data,ref.current);},[result.data,result.loading]);
  if(result.error)return <FailureView error={result.error} retry={result.retry}/>;
  if(result.loading||!result.data)return <Loading/>;
  return <><div ref={ref}/><button className="pf-text-button nc-refresh" onClick={result.retry}>刷新进度</button></>;
}
function InteractionDetail({item,token,changed}:{item:Notice;token:string;changed:()=>void}) {
  const ref=useRef<HTMLDivElement>(null);
  useMarkDisplayed(item,token,changed);
  useEffect(()=>{if(ref.current)window.JccNoticeView.interaction(item,ref.current);},[item]);
  return <div ref={ref}/>;
}

function ContentBlock({
  title,
  content,
  seasons,
  original,
}: {
  title: string;
  content: Content;
  seasons: Seasons["seasons"];
  original?: Content;
}) {
  return (
    <section className="pf-record-content">
      <h3>{title}</h3>
      {(["name", "season_id", "code"] as const).map((key) => (
        <div
          key={key}
          className={
            original && original[key] !== content[key] ? "is-changed" : ""
          }
        >
          <small>
            {{ name: "阵容名称", code: "阵容码", season_id: "所属赛季" }[key]}
            {original && original[key] !== content[key] && " · 已修改"}
          </small>
          {key === "code" ? (
            <pre>{content[key]}</pre>
          ) : (
            <p>
              {key === "season_id"
                ? seasons.find((season) => season.id === content[key])?.name ||
                  content[key]
                : content[key]}
            </p>
          )}
        </div>
      ))}
    </section>
  );
}

function ModerationDetail({
  screen,
  token,
  changed,
  go,
}: {
  screen: Extract<Screen, { kind: "moderation" }>;
  token: string;
  changed: () => void;
  go: (screen: Screen) => void;
}) {
  const result = useResource<RecordData>(
    `/api/lineups/${screen.id}/moderation`,
  );
  const seasons = useResource<Seasons>("/api/lineup-seasons");
  const record = result.data || screen.seed;
  const [markError, setMarkError] = useState("");
  const loadedRevision = record?.moderation?.revision;
  useEffect(() => {
    setMarkError("");
    if (!record?.moderation || record.moderation.notice_state !== "unread")
      return;
    const controller = new AbortController();
    setMarkError("");
    window.JccAccount.request(`/api/me/lineup-notifications/${screen.id}`, {
      method: "PUT",
      headers: headers(token),
      body: JSON.stringify({ status: "read", revision: loadedRevision }),
      signal: controller.signal,
    })
      .then(() => {
        if (!controller.signal.aborted) changed();
      })
      .catch((error) => {
        if (!controller.signal.aborted) setMarkError(error.message);
      });
    return () => controller.abort();
  }, [record, loadedRevision, screen.id, token, changed]);
  if (!record)
    return result.error ? (
      <FailureView error={result.error} retry={result.retry} />
    ) : (
      <Loading />
    );
  const { lineup, moderation: m, events } = record;
  const catalog = seasons.data?.seasons || [];
  return (
    <section className="pf-moderation-detail">
      <div className="pf-record-heading">
        <div>
          <Status
            value={
              lineup.status === "deleted"
                ? "deleted"
                : m?.state || lineup.status
            }
          />
          <h3>{lineup.name}</h3>
          <p>
            #{lineup.id} · {date(m?.updated_at)}
          </p>
        </div>
        {lineup.status === "banned" && m?.state !== "pending" ? (
          <button
            className="pf-button pf-primary"
            onClick={() => go({ kind: "edit", id: lineup.id })}
          >
            <FilePenLine size={15} />
            修改并申请重审
          </button>
        ) : ["normal", "hidden"].includes(lineup.status) ? (
          <button
            className="pf-button"
            onClick={() => go({ kind: "edit", id: lineup.id })}
          >
            <FilePenLine size={15} />
            编辑阵容
          </button>
        ) : null}
      </div>
      {m && (
        <div className="pf-moderation-reason">
          <strong>封禁原因</strong>
          <p>{m.reason}</p>
          {m.review_note && (
            <>
              <strong>最新处理说明</strong>
              <p>{m.review_note}</p>
            </>
          )}
        </div>
      )}
      {m?.state === "pending" && (
        <p className="pf-dialog-hint">
          <Clock3 size={16} />
          修改已提交，等待管理员审核。审核期间不能再次修改。
        </p>
      )}
      {lineup.status === "deleted" ? (
        <p className="pf-dialog-hint">阵容已删除，处理记录仍然保留。</p>
      ) : (
        m && (
          <p className="pf-dialog-hint">
            {lineup.status === "banned"
              ? `审核通过或解除封禁后恢复为「${labels[m.prior_status] || m.prior_status}」。`
              : `阵容当前为「${labels[lineup.status] || lineup.status}」状态。`}
          </p>
        )
      )}
      {markError && (
        <div className="pf-form-error" role="alert">
          已读状态未更新：{markError}
          <button className="pf-text-button" onClick={result.retry}>
            重新加载最新通知
          </button>
        </div>
      )}
      {result.error && record && (
        <div className="pf-form-error" role="alert">
          修改已提交，但最新详情加载失败。
          <button className="pf-text-button" onClick={result.retry}>
            重新加载
          </button>
        </div>
      )}
      {seasons.error && (
        <p className="pf-dialog-hint">赛季名称暂时不可用，以下显示赛季编号。</p>
      )}
      <div className={m?.proposal ? "pf-record-comparison" : ""}>
        <ContentBlock
          title={m?.proposal ? "原阵容" : "阵容内容"}
          content={lineup}
          seasons={catalog}
        />
        {m?.proposal && (
          <ContentBlock
            title="提交的修改"
            content={m.proposal}
            original={lineup}
            seasons={catalog}
          />
        )}
      </div>
      <details className="pf-record-history">
        <summary>
          处理记录 <span>{events.length}</span>
        </summary>
        {events.length ? (
          events.map((event) => (
            <article key={event.id}>
              <div>
                <strong>{actions[event.action] || event.action}</strong>
                <time>{date(event.created_at)}</time>
              </div>
              {event.reason && <p>{event.reason}</p>}
              {event.action === "submit" && (
                <details>
                  <summary>查看本次提交内容</summary>
                  <ContentBlock
                    title="提交版本"
                    content={event.after}
                    original={event.before}
                    seasons={catalog}
                  />
                </details>
              )}
            </article>
          ))
        ) : (
          <p>暂无处理记录</p>
        )}
      </details>
    </section>
  );
}

function Editor({
  id,
  token,
  setDirty,
  setBusy,
  saved,
  cancel,
}: {
  id: number;
  token: string;
  setDirty: (value: boolean) => void;
  setBusy: (value: boolean) => void;
  saved: (record?: RecordData) => void;
  cancel: () => void;
}) {
  const data = useResource<EditorData>(`/api/lineups/${id}`);
  const catalog = useResource<Seasons>("/api/lineup-seasons");
  if (data.error || catalog.error)
    return (
      <FailureView
        error={(data.error || catalog.error)!}
        retry={() => {
          data.retry();
          catalog.retry();
        }}
      />
    );
  if (!data.data || !catalog.data) return <Loading />;
  if (!data.data.can_edit)
    return (
      <FailureView error={new Error("你无权编辑该阵容")} retry={data.retry} />
    );
  return (
    <EditorForm
      key={data.data.version}
      lineup={data.data}
      seasons={catalog.data.seasons}
      token={token}
      setDirty={setDirty}
      setBusy={setBusy}
      saved={saved}
      cancel={cancel}
      reload={data.retry}
    />
  );
}

function EditorForm({
  lineup,
  seasons,
  token,
  setDirty,
  setBusy,
  saved,
  cancel,
  reload,
}: {
  lineup: EditorData;
  seasons: Seasons["seasons"];
  token: string;
  setDirty: (value: boolean) => void;
  setBusy: (value: boolean) => void;
  saved: (record?: RecordData) => void;
  cancel: () => void;
  reload: () => void;
}) {
  const restricted = lineup.status === "banned",
    pending = restricted && lineup.moderation?.state === "pending";
  const initial = (restricted && lineup.moderation?.proposal) || lineup;
  const [name, setName] = useState(initial.name),
    [code, setCode] = useState(initial.code);
  const initialSeason = seasons.some((item) => item.id === initial.season_id)
    ? initial.season_id
    : "";
  const [season, setSeason] = useState(initialSeason);
  const [hidden, setHidden] = useState(lineup.status === "hidden");
  const [saving, setSaving] = useState(false),
    [error, setError] = useState<Failure | null>(null);
  const [replaceDraft, setReplaceDraft] = useState(false);
  const inFlight = useRef(false);
  const dirty =
    name !== initial.name ||
    code !== initial.code ||
    season !== initialSeason ||
    hidden !== (lineup.status === "hidden");
  useEffect(() => {
    setDirty(dirty && !pending);
    return () => setDirty(false);
  }, [dirty, pending, setDirty]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty || saving) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, saving]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current || pending) return;
    setError(null);
    const matches = [...code.matchAll(/[#＃]([A-Za-z0-9]+)/g)]
      .map((item) => item[1])
      .sort((a, b) => b.length - a.length);
    if (!name.trim() || !season || !matches.length) {
      setError(new Error("请填写名称、选择赛季，并粘贴包含 # 阵容码的内容。"));
      return;
    }
    inFlight.current = true;
    setSaving(true);
    setBusy(true);
    let response: RecordData | undefined;
    try {
      const payload = {
        name: name.trim(),
        code: `#${matches[0]}`,
        season_id: season,
        version: lineup.version,
        ...(!restricted ? { status: hidden ? "hidden" : "normal" } : {}),
      };
      const result = await window.JccAccount.request<RecordData>(
        restricted
          ? `/api/lineups/${lineup.id}/revision`
          : `/api/lineups/${lineup.id}`,
        {
          method: restricted ? "POST" : "PUT",
          headers: headers(token),
          body: JSON.stringify(payload),
        },
      );
      if (restricted) response = result;
    } catch (failure) {
      setError(failure as Failure);
      inFlight.current = false;
      setSaving(false);
      setBusy(false);
      return;
    }
    setBusy(false);
    setDirty(false);
    window.jccNotify.show(
      restricted ? "修改已提交，等待管理员审核" : "阵容已更新",
      { variant: "success" },
    );
    saved(response);
  }
  return (
    <form
      className="pf-edit-form"
      onSubmit={submit}
      aria-label={restricted ? "重审编辑表单" : "阵容编辑表单"}
    >
      <p className="pf-dialog-intro">
        {pending
          ? "你的修改正在审核，以下为本次提交内容。"
          : restricted
            ? "修改名称、阵容码或赛季后提交，审核通过后才会替换原内容。"
            : "修改后直接保存，关闭浮窗即可继续管理阵容。"}
      </p>
      {restricted && (
        <div className="pf-moderation-reason">
          <strong>封禁原因</strong>
          <p>{lineup.moderation?.reason}</p>
          {lineup.moderation?.review_note && (
            <>
              <strong>退回说明</strong>
              <p>{lineup.moderation.review_note}</p>
            </>
          )}
        </div>
      )}
      <fieldset disabled={saving || pending}>
        <label className="pf-edit-field" htmlFor="pfEditName">
          阵容名称
          <input
            id="pfEditName"
            required
            maxLength={80}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="pf-edit-field" htmlFor="pfEditCode">
          阵容码
          <textarea
            id="pfEditCode"
            required
            maxLength={20000}
            rows={5}
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
          <small>支持粘贴分享文案，保存时自动提取有效阵容码。</small>
        </label>
        <div className="pf-edit-bottom">
          <label className="pf-edit-field" htmlFor="pfEditSeason">
            所属赛季
            <select
              id="pfEditSeason"
              required
              value={season}
              onChange={(event) => setSeason(event.target.value)}
            >
              <option value="" disabled>
                {seasons.length ? "请选择赛季" : "暂无可用赛季"}
              </option>
              {seasons.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            {!seasons.some((item) => item.id === initial.season_id) && (
              <small>原赛季已不可用，请重新选择后保存。</small>
            )}
          </label>
          {!restricted && (
            <label className="pf-edit-visibility">
              <span>
                <strong>隐藏阵容</strong>
                <small>开启后不在公开列表展示</small>
              </span>
              <input
                type="checkbox"
                checked={hidden}
                onChange={(event) => setHidden(event.target.checked)}
              />
            </label>
          )}
        </div>
      </fieldset>
      {error && (
        <div className="pf-form-error" role="alert">
          <p>{error.message}</p>
          {error.status === 409 && (
            <>
              <p>你的输入已保留。重新加载会替换为服务器上的最新内容。</p>
              {replaceDraft ? (
                <div className="pf-edit-actions">
                  <button
                    type="button"
                    className="pf-button"
                    onClick={() => setReplaceDraft(false)}
                  >
                    保留当前输入
                  </button>
                  <button
                    type="button"
                    className="pf-button"
                    onClick={() => {
                      setDirty(false);
                      reload();
                    }}
                  >
                    放弃输入并加载
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="pf-text-button"
                  onClick={() => setReplaceDraft(true)}
                >
                  重新加载最新阵容
                </button>
              )}
            </>
          )}
        </div>
      )}
      <footer className="pf-edit-footer">
        <span>
          {pending
            ? "等待管理员审核"
            : restricted
              ? "提交后，原阵容继续保持封禁"
              : dirty
                ? "有未保存的修改"
                : "当前内容已同步"}
        </span>
        <div>
          <button
            className="pf-button"
            type="button"
            disabled={saving}
            onClick={cancel}
          >
            {pending ? "关闭" : "取消"}
          </button>
          <button
            className="pf-button pf-primary"
            type="submit"
            disabled={saving || pending || !seasons.length}
          >
            {saving
              ? "正在保存…"
              : pending
                ? "审核中"
                : restricted
                  ? "提交修改并申请重审"
                  : "保存修改"}
          </button>
        </div>
      </footer>
    </form>
  );
}
