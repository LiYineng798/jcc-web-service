import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { ArrowUpRight, RefreshCw, PackageCheck, RotateCcw, Upload, X, Download, ShieldCheck, ShieldAlert, Ban, Rocket, Undo2, LoaderCircle, CircleCheck, CircleAlert, ChevronRight, type LucideIcon } from 'lucide-react';
import { FileUpload, type FileUploadItem } from './components/ui/be-ui-file-upload';
import './package-ui.css';

type Active = { release_id: string | null; previous_release_id: string | null; revision: number; package_id?: string; game_version?: string; data_revision?: number };
type Job = { status: string; progress: number; message: string; stage: string; cancel_requested: number };
type Group = 'online' | 'processing' | 'pending' | 'history' | 'closed';
type Item = { id: string; package_id: string; season_id: string; game_version: string; data_revision: number; state: string; created_at: string; published_at: string | null; job_status: string; progress: number; grp: Group };
type Change = { id: string; name: string; fields?: string[] };
type Diff = Record<string, { added: (Change | string)[]; removed: (Change | string)[]; changed: (Change | string)[] }>;
type Report = { counts?: Record<string, number>; warnings?: string[]; diff?: Diff; compared_active?: Active; notes?: { title: string; summary: string; sections: { title: string; items: string[] }[] }; sources?: Record<string, unknown>[]; inherited_count?: number; supplement_count?: number; images?: number };
type Detail = Item & { job: Job; report: Report; active: Active; manifest: { mechanics: { id: string; display_name: string; presentation: string }[] }; preview_url: string; simulator_url: string };
type Stats = { total: number; processing: number; pending: number; rejected: number; latest_upload: string | null };
type Season = { season_id: string; display_name: string; game_version: string; active: Active; stats: Stats };
type Event = { id: string; action: string; status: string; season_id: string; created_at: string; release_id: string | null; previous_release_id: string | null;
  game_version: string | null; data_revision: number | null; previous_game_version: string | null; previous_data_revision: number | null; actor_name: string | null;
  detail: { message: string | null; warning_count: number; auto_restored: boolean | null; revision: number | null } };
type Listing = { items: Item[]; counts: Record<Group, number>; max_bytes: number; season_id: string | null; seasons: Season[]; events: Event[] };
type Settled = { items: Item[]; total: number; page: number; loading: boolean; open: boolean };
const SETTLED_EMPTY: Settled = { items: [], total: 0, page: 0, loading: false, open: false };
type Confirmation = { kind: 'publish' | 'rollback'; seasonId: string; revision: number; target: string | null; label: string; warnings: string[] };

const BASE = '/api/admin/season-packages';
const SEASON_KEY = 'jcc-season-packages-season';
const labels: Record<string, string> = { champions: '弈子', traits: '羁绊', items: '装备', augments: '强化符文', board_units: '棋盘对象', mechanics: '赛季玩法', assets: '图片资源', queued: '等待校验', validating: '正在校验', ready: '待审核', rejected: '校验失败', cancelled: '已取消', upload: '上传', validated: '校验通过', validation: '校验', publish: '发布', rollback: '回滚', cancel: '取消任务', retry: '重试', verifying: '验证中', completed: '完成', failed: '失败', superseded: '已被后续发布替代' };
const text = (key: string) => labels[key] || key;
const running = (status: string) => status === 'queued' || status === 'running';
const message = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试';

async function api<T>(path: string, csrf: string, data?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', signal,
    headers: data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: data === undefined ? undefined : JSON.stringify(data) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `请求失败（${response.status}）`);
  return body as T;
}

function Button({ children, onClick, disabled = false, primary = false }: { children: ReactNode; onClick: () => void; disabled?: boolean; primary?: boolean }) {
  return <button type="button" className={`sp-btn${primary ? ' sp-primary' : ''}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

function ConfirmDialog({ value, busy, close, confirm }: { value: Confirmation; busy: boolean; close: () => void; confirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [ack, setAck] = useState(false);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} aria-labelledby="sp-confirm-title" onCancel={event => { event.preventDefault(); if (!busy) close(); }}>
    <div className="sp-stack">
      <h2 id="sp-confirm-title">{value.kind === 'publish' ? '发布这个版本' : '回滚资料版本'}</h2>
      <p className="sp-break">{value.label}</p>
      <p className="sp-muted">确认后，此赛季的资料库、模拟器和海报创作者都将使用所选版本。系统会检查关键页面，失败时尝试恢复原版本。</p>
      {value.warnings.length > 0 && <><div className="sp-warning">{value.warnings.map(w => <p key={w}>{w}</p>)}</div><label className="sp-check"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />我已核对以上告警，并确认发布这些资料。</label></>}
      <div className="sp-actions"><Button onClick={close} disabled={busy}>取消</Button><Button primary onClick={confirm} disabled={busy || (value.warnings.length > 0 && !ack)}>{busy ? '正在切换并验证…' : '确认' + (value.kind === 'publish' ? '发布' : '回滚')}</Button></div>
    </div>
  </dialog>;
}

const DIFF_PREVIEW = 200;

// Large reports (thousands of image rows) render nothing until a section is opened, then 200 rows at a time.
function DiffSection({ name, value }: { name: string; value: Diff[string] }) {
  const [open, setOpen] = useState(false);
  const [limit, setLimit] = useState(DIFF_PREVIEW);
  const rows = open ? (['added', 'changed', 'removed'] as const).flatMap(kind => value[kind].map(row => ({ kind, row }))) : [];
  const total = value.added.length + value.changed.length + value.removed.length;
  return <details onToggle={event => setOpen((event.target as HTMLDetailsElement).open)}>
    <summary><span>{text(name)}</span><span className="sp-diff-counts sp-num">{value.added.length > 0 && <b className="is-add">+{value.added.length}</b>}{value.changed.length > 0 && <b className="is-change">~{value.changed.length}</b>}{value.removed.length > 0 && <b className="is-remove">−{value.removed.length}</b>}{total === 0 && <span className="sp-muted">无变化</span>}</span></summary>
    {open && total > 0 && <div className="sp-table-wrap"><table><thead><tr><th>变化</th><th>名称 / 标识</th><th>字段</th></tr></thead><tbody>
      {rows.slice(0, limit).map(({ kind, row }) => <tr key={`${kind}-${typeof row === 'string' ? row : row.id}`}>
        <td>{{ added: '新增', changed: '修改', removed: '移除' }[kind]}</td><td className="sp-break">{typeof row === 'string' ? row : `${row.name} (${row.id})`}</td><td className="sp-break">{typeof row === 'string' ? '—' : row.fields?.join('、') || '整条记录'}</td>
      </tr>)}
    </tbody></table>{rows.length > limit && <button type="button" className="sp-more" onClick={() => setLimit(rows.length)}>显示全部 {rows.length} 条</button>}</div>}
  </details>;
}

function DiffReport({ diff }: { diff: Diff }) {
  return <div>{Object.entries(diff).map(([key, value]) => <DiffSection key={key} name={key} value={value} />)}</div>;
}

function onlineText(season: Season) {
  return season.active.release_id ? `线上 ${season.active.game_version} · r${season.active.data_revision}` : `基准版本 ${season.game_version}`;
}

function SeasonCounts({ stats }: { stats: Stats }) {
  const parts = [[stats.pending, '待审核', 'is-pending'], [stats.processing, '校验中', 'is-running'], [stats.rejected, '失败', 'is-error']] as const;
  const shown = parts.filter(([count]) => count > 0);
  return shown.length ? <span className="sp-counts">{shown.map(([count, label, tone]) => <Pill key={label} tone={tone}>{label} {count}</Pill>)}</span> : null;
}

function UploadDialog({ close, children }: { close: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="sp-upload-dialog" aria-labelledby="sp-upload-title" onCancel={event => { event.preventDefault(); close(); }}>
    <div className="sp-stack">
      <div className="sp-head" style={{ margin: 0 }}><div><h2 id="sp-upload-title">上传赛季更新包</h2><p className="sp-muted">赛季由包内清单决定；上传后自动切换到对应赛季并打开审核。</p></div><button type="button" className="sp-icon" aria-label="关闭上传" onClick={close}><X size={16} /></button></div>
      {children}
    </div>
  </dialog>;
}

function Pill({ tone = '', children }: { tone?: string; children: ReactNode }) {
  return <span className={`sp-pill ${tone}`}><i aria-hidden="true" />{children}</span>;
}

function statusTag(item: Item, online: boolean) {
  if (online) return <Pill tone="is-online">当前线上</Pill>;
  if (item.published_at && item.state === 'ready') return <Pill>历史版本</Pill>;
  const tone = item.state === 'ready' ? 'is-pending' : item.state === 'rejected' ? 'is-error' : running(item.job_status) ? 'is-running' : '';
  return <Pill tone={tone}>{text(item.state)}</Pill>;
}

const version = (game: string | null, revision: number | null) => game ? `${game} · r${revision}` : null;
const RESULTS: Record<string, [string, string]> = {
  completed: ['成功', 'is-online'], failed: ['失败', 'is-error'], cancelled: ['已取消', ''], verifying: ['验证中', 'is-running'], superseded: ['已被替代', ''],
};

// One plain sentence per event: what happened, to which version, and why it matters.
function describe(e: Event): { icon: LucideIcon; tone: string; title: string; note: string | null } {
  const target = version(e.game_version, e.data_revision);
  const previous = version(e.previous_game_version, e.previous_data_revision);
  const baseline = '随代码部署的基准版本';
  switch (e.action) {
    case 'upload': return { icon: Upload, tone: 'is-neutral', title: `上传更新包 ${target ?? ''}`, note: null };
    case 'validated': return { icon: ShieldCheck, tone: 'is-online', title: `校验通过 ${target ?? ''}`,
      note: e.detail.warning_count ? `${e.detail.warning_count} 条告警，发布前需逐条确认` : '没有告警，可以审核发布' };
    case 'validation': return { icon: ShieldAlert, tone: e.status === 'cancelled' ? 'is-neutral' : 'is-error',
      title: `${e.status === 'cancelled' ? '校验已取消' : '校验未通过'} ${target ?? ''}`, note: e.detail.message };
    case 'cancel': return { icon: Ban, tone: 'is-neutral', title: `请求取消校验 ${target ?? ''}`, note: null };
    case 'retry': return { icon: RotateCcw, tone: 'is-neutral', title: `重新排队校验 ${target ?? ''}`, note: null };
    case 'publish': return { icon: Rocket, tone: e.status === 'failed' ? 'is-error' : 'is-accent', title: `发布 ${target ?? ''}`,
      note: e.status === 'failed' ? `页面检查未通过，${e.detail.auto_restored ? '已自动恢复为 ' + (previous ?? baseline) : '未覆盖之后的发布'}` : `替换 ${previous ?? baseline}` };
    case 'rollback': return { icon: Undo2, tone: e.status === 'failed' ? 'is-error' : 'is-pending', title: `回滚到 ${target ?? baseline}`,
      note: e.status === 'failed' ? '页面检查未通过，回滚未生效' : previous ? `撤下 ${previous}` : null };
    default: return { icon: CircleAlert, tone: 'is-neutral', title: text(e.action), note: null };
  }
}

function dayLabel(stamp: string) {
  const day = stamp.slice(0, 10);
  const today = new Date();
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  if (day === iso(today)) return '今天';
  today.setDate(today.getDate() - 1);
  return day === iso(today) ? '昨天' : day;
}

function EventTimeline({ events, showSeason, seasonName, open }: { events: Event[]; showSeason: boolean; seasonName: (id: string) => string; open: (id: string) => void }) {
  const groups: [string, Event[]][] = [];
  for (const event of events) {
    const label = dayLabel(event.created_at);
    if (groups.at(-1)?.[0] !== label) groups.push([label, []]);
    groups.at(-1)![1].push(event);
  }
  return <div className="sp-timeline">{groups.map(([label, rows]) => <section key={label} aria-label={label}>
    <h3 className="sp-day">{label}</h3>
    <ol>{rows.map(e => {
      const { icon: Icon, tone, title, note } = describe(e);
      const [result, resultTone] = RESULTS[e.status] || [text(e.status), ''];
      const body = <>
        <span className={`sp-event-icon ${tone}`} aria-hidden="true">{e.status === 'verifying' ? <LoaderCircle size={15} className="sp-spin" /> : <Icon size={15} />}</span>
        <span className="sp-event-main">
          <span className="sp-event-line"><strong className="sp-num">{title.trim()}</strong><Pill tone={resultTone}>{result}</Pill></span>
          {note && <span className={`sp-event-note${e.status === 'failed' ? ' sp-error' : ''}`}>{note}</span>}
          <span className="sp-event-meta sp-num">{e.created_at.slice(11, 16)} · {e.actor_name || '后台任务'}{showSeason ? ` · ${seasonName(e.season_id)}` : ''}</span>
        </span>
        {e.release_id && <ChevronRight size={15} className="sp-event-go" aria-hidden="true" />}
      </>;
      return <li key={e.id}>{e.release_id ? <button type="button" className="sp-event" onClick={() => open(e.release_id!)} aria-label={`${title}，${result}，查看更新包`}>{body}</button> : <div className="sp-event">{body}</div>}</li>;
    })}</ol>
  </section>)}</div>;
}

function App({ csrfToken }: { csrfToken: string }) {
  const [files, setFiles] = useState<FileUploadItem[]>([]);
  const [listing, setListing] = useState<Listing | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [selected, setSelected] = useState('');
  const [season, setSeason] = useState(() => { try { return localStorage.getItem(SEASON_KEY) || ''; } catch { return ''; } });
  const [refresh, setRefresh] = useState(0);
  const [detailRefresh, setDetailRefresh] = useState(0);
  // Settled packages (history, rejected/cancelled) are fetched only when their section is opened.
  const [settled, setSettled] = useState<Record<'history' | 'closed', Settled>>({ history: SETTLED_EMPTY, closed: SETTLED_EMPTY });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('overview');
  // Narrow screens show one pane at a time; wide screens use view only for the middle pane.
  const [view, setView] = useState<'packages' | 'events' | 'detail'>('packages');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const uploads = useRef(new Map<string, XMLHttpRequest>());
  const alive = useRef(true);
  const mutation = useRef<AbortController | null>(null);
  const recordsRef = useRef<HTMLDivElement>(null);
  const reload = () => { setRefresh(n => n + 1); setDetailRefresh(n => n + 1); };

  useEffect(() => () => { alive.current = false; for (const xhr of uploads.current.values()) xhr.abort(); mutation.current?.abort(); }, []);
  // Listing: light payload, polled fast only while a validation runs, paused while the tab is hidden.
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      clearTimeout(timer);
      if (document.hidden) return;
      try {
        const query = season ? `?season_id=${encodeURIComponent(season)}` : '';
        const result = await api<Listing>(`${BASE}${query}`, csrfToken, undefined, controller.signal);
        if (controller.signal.aborted) return;
        setListing(result);
        setSelected(current => current || (result.items.find(i => i.grp === 'pending') || result.items.find(i => i.grp === 'processing') || result.items[0])?.id || '');
        timer = setTimeout(load, result.counts.processing ? 2500 : 15000);
      } catch (e) {
        if (controller.signal.aborted) return;
        // A remembered season may have been removed from the catalog; fall back to all seasons.
        if (season && message(e) === '赛季不存在') { chooseSeason(''); return; }
        setError(message(e)); timer = setTimeout(load, 15000);
      }
    }
    const resume = () => { if (!document.hidden) void load(); };
    document.addEventListener('visibilitychange', resume);
    void load();
    return () => { controller.abort(); clearTimeout(timer); document.removeEventListener('visibilitychange', resume); };
  }, [season, refresh, csrfToken]);

  // Detail (with the potentially large review report): fetched on selection or after a change, and
  // polled only while its own validation is running.
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const item = await api<Detail>(`${BASE}/${selected}`, csrfToken, undefined, controller.signal);
        if (controller.signal.aborted) return;
        setDetail(item);
        if (running(item.job.status)) timer = setTimeout(load, 2500);
      } catch (e) {
        if (!controller.signal.aborted) setError(message(e));
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, detailRefresh, csrfToken]);

  // Refetch the detail only when the listing shows it changed elsewhere (a publish, a finished job).
  useEffect(() => {
    if (!listing || !detail || detail.id !== selected) return;
    const live = listing.seasons.find(s => s.season_id === detail.season_id)?.active.revision;
    const row = listing.items.find(i => i.id === detail.id);
    if ((live !== undefined && live !== detail.active.revision) || (row && (row.state !== detail.state || row.job_status !== detail.job.status))) {
      setDetailRefresh(n => n + 1);
    }
  }, [listing]);

  // Expanded settled sections follow the season and any reload.
  const settledGeneration = useRef(0);
  useEffect(() => {
    settledGeneration.current += 1;
    setSettled(current => ({ history: { ...SETTLED_EMPTY, open: current.history.open }, closed: { ...SETTLED_EMPTY, open: current.closed.open } }));
  }, [season, refresh]);
  useEffect(() => {
    for (const group of ['history', 'closed'] as const) if (settled[group].open && settled[group].page === 0 && !settled[group].loading) void loadSettled(group, 1);
  }, [settled]);

  async function loadSettled(group: 'history' | 'closed', page: number) {
    const generation = settledGeneration.current;
    setSettled(current => ({ ...current, [group]: { ...current[group], loading: true } }));
    try {
      const query = new URLSearchParams({ group, page: String(page), ...(season ? { season_id: season } : {}) });
      const result = await api<{ items: Item[]; total: number; page: number }>(`${BASE}?${query}`, csrfToken);
      // A season switch or reload started a new list; drop this late response.
      if (!alive.current || generation !== settledGeneration.current) return;
      setSettled(current => ({ ...current, [group]: { ...current[group], loading: false, total: result.total, page,
        items: page === 1 ? result.items : [...current[group].items, ...result.items] } }));
    } catch (e) {
      if (alive.current) { setError(message(e)); setSettled(current => ({ ...current, [group]: { ...current[group], loading: false, page: Math.max(1, page) } })); }
    }
  }

  function chooseSeason(id: string) {
    try { if (id) localStorage.setItem(SEASON_KEY, id); else localStorage.removeItem(SEASON_KEY); } catch { /* Selection still works for this visit. */ }
    setSeason(id); setSelected(''); setDetail(null); setTab('overview'); setView('packages');
  }

  function upload(item: FileUploadItem) {
    if (!item.file) return;
    const update = (patch: Partial<FileUploadItem>) => { if (alive.current) setFiles(values => values.map(f => f.id === item.id ? { ...f, ...patch } : f)); };
    if (!item.name.toLowerCase().endsWith('.zip') || item.size > (listing?.max_bytes || 256 * 1024 ** 2)) {
      update({ status: 'error', error: '请选择限制大小以内的 ZIP 赛季更新包' }); return;
    }
    setError('');
    const xhr = new XMLHttpRequest();
    uploads.current.set(item.id, xhr);
    update({ status: 'uploading', progress: 0, error: undefined });
    xhr.open('POST', BASE);
    xhr.setRequestHeader('X-CSRF-Token', csrfToken);
    xhr.timeout = 10 * 60 * 1000;
    xhr.upload.onprogress = event => { if (event.lengthComputable) update({ progress: Math.round(event.loaded / event.total * 100) }); };
    xhr.onload = () => {
      uploads.current.delete(item.id);
      if (!alive.current) return;
      let result;
      try { result = JSON.parse(xhr.responseText); } catch { update({ status: 'error', error: `服务器未返回有效结果（${xhr.status}）` }); return; }
      if (xhr.status < 200 || xhr.status >= 300) { update({ status: 'error', error: result.error || `上传失败（${xhr.status}）` }); return; }
      update({ status: 'success', progress: 100 });
      if (season !== result.package.season_id) chooseSeason(result.package.season_id);
      setSelected(result.package.id); setDetail(null); setTab('overview'); setView('detail'); setUploadOpen(false); reload();
      setNotice(result.reused ? '这个包已经上传，已打开原任务。' : '文件已上传。服务端开始校验，通过后可预览和发布。');
    };
    xhr.onerror = xhr.ontimeout = () => { uploads.current.delete(item.id); update({ status: 'error', error: '连接中断或超时，可重试；相同更新包会自动去重。' }); };
    xhr.onabort = () => uploads.current.delete(item.id);
    const form = new FormData(); form.append('file', item.file); xhr.send(form);
  }

  async function action(path: string, data: unknown, success: string) {
    if (busy) return;
    setBusy(true); setError('');
    mutation.current = new AbortController();
    try {
      await api(path, csrfToken, data, mutation.current.signal);
      if (alive.current) { setNotice(success); setConfirmation(null); }
    } catch (e) { if (alive.current) { setError(message(e)); setConfirmation(null); } }
    finally { if (alive.current) { setBusy(false); reload(); } }
  }
  function confirm() {
    if (!confirmation) return;
    const c = confirmation;
    // Show the outcome banner right away instead of leaving the reviewer on the diff tab.
    setTab('overview');
    void action(c.kind === 'publish' ? `${BASE}/${c.target}/publish` : `/api/admin/seasons/${c.seasonId}/rollback`,
      { expected_revision: c.revision, release_id: c.target, acknowledge_warnings: true }, c.kind === 'publish' ? '版本已发布，关键页面检查通过。' : '已回滚，关键页面检查通过。');
  }
  const currentDetail = detail?.id === selected ? detail : null;
  const report = currentDetail?.report;
  const isActive = currentDetail?.active.release_id === selected;

  const seasons = listing?.seasons || [];
  const seasonName = (id: string) => seasons.find(s => s.season_id === id)?.display_name || id;
  const focus = seasons.find(s => s.season_id === season);
  const onlineOf = (item: Item) => seasons.find(s => s.season_id === item.season_id)?.active.release_id === item.id;
  const rollback = (s: Season) => setConfirmation({ kind: 'rollback', seasonId: s.season_id, revision: s.active.revision, target: s.active.previous_release_id, label: `${s.display_name} → ${s.active.previous_release_id ? '上一个已发布版本' : '随代码部署的基准版本'}`, warnings: [] });
  const totals = seasons.reduce((sum, s) => ({ total: sum.total + s.stats.total, processing: sum.processing + s.stats.processing, pending: sum.pending + s.stats.pending, rejected: sum.rejected + s.stats.rejected, latest_upload: null }), { total: 0, processing: 0, pending: 0, rejected: 0, latest_upload: null } as Stats);
  // Finished uploads are already in the list; start each dialog with a free drop zone.
  const openUpload = () => { setFiles(items => items.filter(item => item.status === 'uploading' || item.status === 'error')); setUploadOpen(true); };
  const openPackage = (id: string) => { setSelected(id); setTab('overview'); setView('detail'); };
  const middle = view === 'events' ? 'events' : 'packages';
  const stale = !!currentDetail && report?.compared_active?.revision !== currentDetail.active.revision;
  const banner = !currentDetail ? null
    : isActive ? { tone: 'is-online', icon: CircleCheck, title: '当前线上版本', text: '资料库、模拟器与海报创作者正在使用这个版本。' }
    : currentDetail.published_at && currentDetail.state === 'ready' ? { tone: '', icon: Undo2, title: '历史发布版本', text: '曾经发布过，可随时回滚到此版本。' }
    : currentDetail.state === 'ready' ? (stale ? { tone: 'is-pending', icon: RefreshCw, title: '需要重新比较', text: `线上版本已变化（比较基准修订 ${report?.compared_active?.revision}，当前 ${currentDetail.active.revision}），重新比较后才能发布。` }
      : { tone: 'is-pending', icon: PackageCheck, title: report?.warnings?.length ? `待审核 · ${report.warnings.length} 条告警` : '待审核，可以发布', text: report?.warnings?.length ? '请先核对下方告警和资料差异，再审核发布。' : '校验已通过，预览确认后即可发布。' })
    : currentDetail.state === 'rejected' ? { tone: 'is-error', icon: ShieldAlert, title: '校验未通过', text: currentDetail.job.message || '请查看原包并修正后重新上传。' }
    : currentDetail.state === 'cancelled' ? { tone: '', icon: Ban, title: '校验已取消', text: '可以重试校验，或上传新的更新包。' }
    : { tone: 'is-running', icon: LoaderCircle, title: '正在校验', text: currentDetail.job.message || '后台处理中，离开页面后任务仍会继续。' };
  const tabs = currentDetail?.state === 'ready' ? [['overview', '概览'], ['diff', '资料差异'], ['notes', '更新说明'], ['sources', '玩法与来源']] : [['overview', '概览']];

  const rail = <aside className="sp-pane sp-rail" aria-label="赛季">
    <div className="sp-pane-head"><h2>赛季</h2><button type="button" className="sp-icon" aria-label="刷新" onClick={reload}><RefreshCw size={15} /></button></div>
    <nav className="sp-pane-body sp-season-list" aria-label="按赛季查看更新包">
      {[{ id: '', name: '全部赛季', line: `${seasons.length} 个赛季 · ${totals.total} 个更新包`, stats: totals, live: undefined as boolean | undefined }, ...seasons.map(s => ({ id: s.season_id, name: s.display_name, line: onlineText(s), stats: s.stats, live: !!s.active.release_id }))].map(row =>
        <button type="button" key={row.id || 'all'} className="sp-season" aria-pressed={season === row.id} onClick={() => chooseSeason(row.id)}>
          <strong className="sp-break">{row.name}</strong><span className="sp-season-line sp-num">{row.live !== undefined && <i className={row.live ? 'is-live' : ''} aria-hidden="true" />}{row.line}</span><SeasonCounts stats={row.stats} />
        </button>)}
    </nav>
    <div className="sp-pane-foot"><Button primary onClick={openUpload}><Upload size={14} />上传更新包</Button></div>
  </aside>;

  const open = listing?.items || [];
  const byGroup = (group: Group) => open.filter(i => i.grp === group);
  const waiting = [...byGroup('processing'), ...byGroup('pending')];
  const counts = listing?.counts;
  const row = (item: Item, compact = false) => <button key={item.id} type="button" className={`sp-package${compact ? ' is-compact' : ''}`} aria-pressed={selected === item.id} onClick={() => openPackage(item.id)}>
    {!focus && <span className="sp-season-label">{seasonName(item.season_id)}</span>}
    <span className="sp-row"><strong className="sp-num">{item.game_version}<span className="sp-rev"> r{item.data_revision}</span></strong>
      {item.grp === 'processing' ? <Pill tone="is-running">校验中 {item.progress}%</Pill> : item.grp === 'pending' ? <Pill tone="is-pending">待审核</Pill>
        : item.grp === 'closed' ? <span className="sp-muted">{text(item.state)}</span> : null}</span>
    {!compact && <span className="sp-muted sp-num">{item.grp === 'online' && item.published_at ? `发布于 ${item.published_at.slice(5, 16)}` : `上传于 ${item.created_at.slice(5, 16)}`}</span>}
    {compact && <span className="sp-muted sp-num">{item.published_at ? `发布于 ${item.published_at.slice(0, 16)}` : `上传于 ${item.created_at.slice(0, 16)}`}</span>}
  </button>;
  const settledSection = (group: 'history' | 'closed', title: string, hint: string) => {
    const state = settled[group];
    const count = counts?.[group] || 0;
    if (!count) return null;
    return <section className={`sp-group is-settled${state.open ? ' is-open' : ''}`}>
      <button type="button" className="sp-group-toggle" aria-expanded={state.open} onClick={() => setSettled(current => ({ ...current, [group]: { ...current[group], open: !current[group].open } }))}>
        <ChevronRight size={14} aria-hidden="true" /><span>{title}</span><span className="sp-count sp-num">{count}</span><span className="sp-muted">{hint}</span>
      </button>
      {state.open && <div className="sp-records">
        {state.items.map(item => row(item, true))}
        {state.loading && <p className="sp-muted sp-foot-note">正在读取…</p>}
        {!state.loading && state.items.length < state.total && <button type="button" className="sp-more" onClick={() => void loadSettled(group, state.page + 1)}>再显示 {Math.min(20, state.total - state.items.length)} 个</button>}
      </div>}
    </section>;
  };

  const list = <section className="sp-pane sp-list" aria-labelledby="sp-list-title">
    <div className="sp-pane-head">
      <div className="sp-min"><h2 id="sp-list-title" className="sp-break">{focus ? focus.display_name : '全部赛季'}</h2><p className="sp-muted sp-break">{focus ? `${focus.season_id} · ${focus.active.release_id ? `线上 ${focus.active.game_version} · r${focus.active.data_revision} · 修订 ${focus.active.revision}` : `随代码部署的基准版本 ${focus.game_version}`}` : '按处理状态分组'}</p></div>
      {focus && focus.active.revision > 0 && <Button disabled={busy} onClick={() => rollback(focus)}><RotateCcw size={14} />回滚</Button>}
    </div>
    <div className="sp-segment" role="group" aria-label="列表内容">
      <button type="button" aria-pressed={middle === 'packages'} onClick={() => setView('packages')}>更新包{waiting.length ? <span className="sp-badge sp-num">{waiting.length}</span> : null}</button>
      <button type="button" aria-pressed={middle === 'events'} onClick={() => setView('events')}>操作记录</button>
    </div>
    <div className="sp-pane-body" ref={recordsRef}>
      {middle === 'packages' ? (!listing ? <p className="sp-muted">正在读取记录…</p>
        : !Object.values(listing.counts).some(Boolean) ? <p className="sp-empty">{focus ? `${focus.display_name}还没有更新包。` : '还没有更新包。'}<br />点击「上传更新包」开始。</p>
        : <div className="sp-groups">
          <section className="sp-group">
            <h3 className="sp-group-title"><span>待处理</span>{waiting.length > 0 && <span className="sp-count sp-num is-pending">{waiting.length}</span>}</h3>
            {waiting.length ? <div className="sp-records">{waiting.map(item => row(item))}</div> : <p className="sp-clear"><CircleCheck size={14} aria-hidden="true" />没有需要处理的更新包</p>}
          </section>
          {byGroup('online').length > 0 && <section className="sp-group">
            <h3 className="sp-group-title"><span>当前线上</span></h3>
            <div className="sp-records">{byGroup('online').map(item => row(item))}</div>
          </section>}
          {settledSection('history', '历史版本', '可回滚')}
          {settledSection('closed', '未通过 / 已取消', '不会发布')}
        </div>)
        : <EventTimeline events={listing?.events || []} showSeason={!focus} seasonName={seasonName} open={openPackage} />}
      {middle === 'events' && listing?.events.length === 0 && <p className="sp-empty">暂无操作记录。</p>}
      {middle === 'events' && !!listing?.events.length && <p className="sp-muted sp-foot-note">显示最近 30 条 · 点击记录查看对应更新包</p>}
    </div>
  </section>;

  const review = <section className="sp-pane sp-detail" aria-labelledby="sp-review-title">
    {!selected || !currentDetail ? <div className="sp-pane-body sp-placeholder"><h2 id="sp-review-title">版本审核</h2><p className="sp-muted">{selected ? '正在读取更新包…' : '在左侧选择一个更新包，查看处理结果、差异和预览。'}</p></div> : <>
      <div className="sp-pane-head sp-detail-head">
        <div className="sp-min">
          <p className="sp-eyebrow">{seasonName(currentDetail.season_id)}</p>
          <div className="sp-title-row"><h2 id="sp-review-title" className="sp-num">{currentDetail.game_version}<span> · 资料修订 r{currentDetail.data_revision}</span></h2>{statusTag(currentDetail, isActive)}</div>
          <p className="sp-muted sp-break sp-num">{currentDetail.package_id} · 上传于 {currentDetail.created_at}</p>
        </div>
      </div>
      <div className="sp-toolbar">
        {currentDetail.state === 'ready' && <Button primary disabled={busy || isActive || stale} onClick={() => setConfirmation({ kind: 'publish', seasonId: currentDetail.season_id, revision: currentDetail.active.revision, target: selected, label: currentDetail.package_id, warnings: report?.warnings || [] })}><PackageCheck size={14} />{isActive ? '已在线上' : stale ? '请先重新比较' : '审核并发布'}</Button>}
        {currentDetail.state === 'ready' && <Button disabled={busy} onClick={() => void action(`${BASE}/${selected}/compare`, {}, '差异已按最新线上版本重新计算。')}><RefreshCw size={14} />重新比较</Button>}
        {currentDetail.state === 'ready' && <a className="sp-btn" href={currentDetail.preview_url} target="_blank" rel="noreferrer">预览资料库<ArrowUpRight size={14} /></a>}
        {currentDetail.state === 'ready' && <a className="sp-btn" href={currentDetail.simulator_url} target="_blank" rel="noreferrer">预览模拟器<ArrowUpRight size={14} /></a>}
        {!!currentDetail.published_at && !isActive && <Button disabled={busy} onClick={() => setConfirmation({ kind: 'rollback', seasonId: currentDetail.season_id, revision: currentDetail.active.revision, target: selected, label: `恢复至 ${currentDetail.package_id}`, warnings: [] })}><RotateCcw size={14} />回滚到此版本</Button>}
        {running(currentDetail.job.status) && <Button disabled={busy || !!currentDetail.job.cancel_requested} onClick={() => void action(`${BASE}/${selected}/cancel`, {}, '已请求取消校验。')}>{currentDetail.job.cancel_requested ? '正在取消…' : '取消校验'}</Button>}
        {['failed', 'cancelled'].includes(currentDetail.job.status) && <Button disabled={busy} onClick={() => void action(`${BASE}/${selected}/retry`, {}, '任务已重新排队。')}><RotateCcw size={14} />重试校验</Button>}
        <a className="sp-btn" href={`${BASE}/${selected}/download`}><Download size={14} />原包</a>
      </div>
      <div className="sp-tabs" role="group" aria-label="审核内容">{tabs.map(([key, label]) => <button type="button" aria-pressed={tab === key} onClick={() => setTab(key)} key={key}>{label}{key === 'overview' && !!report?.warnings?.length && <span className="sp-dot" aria-label={`${report.warnings.length} 条告警`} />}</button>)}</div>
      <div className="sp-pane-body sp-stack">
        {(tab === 'overview' || currentDetail.state !== 'ready') && banner && <>
          <div role="status" className={`sp-banner ${banner.tone}`}>
            <span className="sp-banner-icon" aria-hidden="true">{running(currentDetail.job.status) ? <LoaderCircle size={18} className="sp-spin" /> : <banner.icon size={18} />}</span>
            <span className="sp-min"><strong>{banner.title}</strong><span className="sp-banner-text">{banner.text}</span></span>
            {running(currentDetail.job.status) && <span className="sp-banner-progress sp-num">{currentDetail.job.progress}%<progress value={currentDetail.job.progress} max={100} aria-label="处理进度" /></span>}
          </div>
          {!!report?.warnings?.length && <div className="sp-warning"><h3><CircleAlert size={15} aria-hidden="true" />发布前需确认的告警 · {report.warnings.length}</h3><ul>{report.warnings.map(w => <li key={w}>{w}</li>)}</ul></div>}
          {currentDetail.state === 'ready' && <div><h3 className="sp-section">本包内容</h3><div className="sp-metrics">{Object.entries(report?.counts || {}).map(([key, value]) => <div className="sp-metric" key={key}><span>{text(key)}</span><strong className="sp-num">{value}</strong></div>)}</div></div>}
        </>}
        {tab === 'diff' && report?.diff && <div><p className="sp-muted">比较基准：线上修订 {report.compared_active?.revision}。切换过线上版本后需重新比较。</p><DiffReport key={currentDetail.id} diff={report.diff} /></div>}
        {tab === 'notes' && report?.notes && <div className="sp-stack"><h3>{report.notes.title}</h3><p>{report.notes.summary}</p>{report.notes.sections.map((s, i) => <div key={i}><h3>{s.title}</h3>{s.items.map((item, j) => <p key={j}>· {item}</p>)}</div>)}<p className="sp-muted">随包说明保留在版本记录中，网站的「更新公告」可单独编辑发布。</p></div>}
        {tab === 'sources' && <div className="sp-stack"><div><h3>本版本玩法</h3>{currentDetail.manifest.mechanics.length ? currentDetail.manifest.mechanics.map(m => <p key={m.id}>{m.display_name} <span className="sp-muted">{m.id} · {m.presentation}</span></p>) : <p className="sp-muted">本赛季没有特殊玩法。</p>}</div><p className="sp-muted">共 {report?.images || 0} 张图片，{report?.supplement_count || 0} 个补充字段，其中 {report?.inherited_count || 0} 个沿用历史版本、尚未核验。</p><details><summary>查看完整来源记录（{report?.sources?.length || 0}）</summary><pre>{JSON.stringify(report?.sources || [], null, 2)}</pre></details></div>}
      </div>
    </>}
  </section>;

  return <>
    {(error || notice) && <div role={error ? 'alert' : 'status'} className={`sp-notice${error ? ' sp-error' : ''}`}><span>{error || notice}</span><button type="button" className="sp-icon" aria-label="关闭提示" onClick={() => { setError(''); setNotice(''); }}><X size={14} /></button></div>}
    <div className="sp-compact-bar">
      <select aria-label="选择赛季" value={season} onChange={e => chooseSeason(e.target.value)}>
        <option value="">全部赛季{totals.pending ? `（待审核 ${totals.pending}）` : ''}</option>
        {seasons.map(s => <option key={s.season_id} value={s.season_id}>{s.display_name}{s.stats.pending ? `（待审核 ${s.stats.pending}）` : ''}</option>)}
      </select>
      <Button primary onClick={openUpload}><Upload size={14} />上传</Button>
      <div className="sp-segment" role="group" aria-label="显示内容">
        <button type="button" aria-pressed={view === 'packages'} onClick={() => setView('packages')}>更新包</button>
        <button type="button" aria-pressed={view === 'detail'} onClick={() => setView('detail')}>审核</button>
        <button type="button" aria-pressed={view === 'events'} onClick={() => setView('events')}>操作记录</button>
      </div>
    </div>
    <div className="sp-workspace" data-view={view}>{rail}{list}{review}</div>
    {uploadOpen && <UploadDialog close={() => setUploadOpen(false)}>
      <FileUpload variant="centered" value={files} onValueChange={setFiles} onFilesAdded={items => items.forEach(upload)} onRetry={upload}
        onRemove={item => uploads.current.get(item.id)?.abort()} accept=".zip,application/zip" multiple={false} maxFiles={1}
        title="将更新包拖到这里" description={`支持 ZIP，最大 ${Math.round((listing?.max_bytes || 256 * 1024 ** 2) / 1024 ** 2)} MB`} browseLabel="选择更新包" />
      <p className="sp-muted">文件包含资料、图片、玩法配置、更新说明与来源。上传成功后还需完成校验和发布；关闭窗口不会中断正在进行的上传。</p>
    </UploadDialog>}
    {confirmation && <ConfirmDialog value={confirmation} busy={busy} close={() => setConfirmation(null)} confirm={confirm} />}
  </>;
}

let root: Root | undefined;
export function mount(element: HTMLElement, options: { csrfToken: string }) { unmount(); root = createRoot(element); root.render(<App csrfToken={options.csrfToken} />); }
export function unmount() { root?.unmount(); root = undefined; }
