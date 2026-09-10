import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { ArrowUpRight, RefreshCw, PackageCheck, RotateCcw } from 'lucide-react';
import { FileUpload, type FileUploadItem } from './components/ui/be-ui-file-upload';
import './package-ui.css';

type Active = { release_id: string | null; previous_release_id: string | null; revision: number; package_id?: string; game_version?: string; data_revision?: number };
type Job = { status: string; progress: number; message: string; stage: string; cancel_requested: number };
type Item = { id: string; package_id: string; season_id: string; game_version: string; data_revision: number; state: string; created_at: string; published_at: string | null; job_status: string };
type Change = { id: string; name: string; fields?: string[] };
type Diff = Record<string, { added: (Change | string)[]; removed: (Change | string)[]; changed: (Change | string)[] }>;
type Report = { counts?: Record<string, number>; warnings?: string[]; diff?: Diff; compared_active?: Active; notes?: { title: string; summary: string; sections: { title: string; items: string[] }[] }; sources?: Record<string, unknown>[]; inherited_count?: number; supplement_count?: number; images?: number };
type Detail = Item & { job: Job; report: Report; active: Active; manifest: { mechanics: { id: string; display_name: string; presentation: string }[] }; preview_url: string; simulator_url: string };
type Season = { season_id: string; display_name: string; game_version: string; active: Active };
type Event = { id: string; action: string; status: string; season_id: string; created_at: string; release_id: string | null };
type Listing = { items: Item[]; total: number; page: number; max_bytes: number; seasons: Season[]; events: Event[] };
type Confirmation = { kind: 'publish' | 'rollback'; seasonId: string; revision: number; target: string | null; label: string; warnings: string[] };

const BASE = '/api/admin/season-packages';
const labels: Record<string, string> = { champions: '弈子', traits: '羁绊', items: '装备', augments: '强化符文', board_units: '棋盘对象', mechanics: '赛季玩法', assets: '图片资源', queued: '等待校验', validating: '正在校验', ready: '待审核', rejected: '校验失败', cancelled: '已取消', upload: '上传', validated: '校验通过', publish: '发布', rollback: '回滚', cancel: '取消任务', retry: '重试', verifying: '验证中', completed: '完成', failed: '失败', superseded: '已被后续发布替代' };
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
      <p className="sp-muted">确认后，此赛季的资料库和模拟器将使用所选版本。系统会检查关键页面，失败时尝试恢复原版本。</p>
      {value.warnings.length > 0 && <><div className="sp-warning">{value.warnings.map(w => <p key={w}>{w}</p>)}</div><label className="sp-check"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />我已核对以上告警，并确认发布这些资料。</label></>}
      <div className="sp-actions"><Button onClick={close} disabled={busy}>取消</Button><Button primary onClick={confirm} disabled={busy || (value.warnings.length > 0 && !ack)}>{busy ? '正在切换并验证…' : '确认' + (value.kind === 'publish' ? '发布' : '回滚')}</Button></div>
    </div>
  </dialog>;
}

function DiffReport({ diff }: { diff: Diff }) {
  return <div>{Object.entries(diff).map(([key, value]) => <details key={key}>
    <summary>{text(key)} · 新增 {value.added.length} / 修改 {value.changed.length} / 移除 {value.removed.length}</summary>
    <div className="sp-table-wrap"><table><thead><tr><th>变化</th><th>名称 / 标识</th><th>字段</th></tr></thead><tbody>
      {(['added', 'changed', 'removed'] as const).flatMap(kind => value[kind].map(row => <tr key={`${kind}-${typeof row === 'string' ? row : row.id}`}>
        <td>{{ added: '新增', changed: '修改', removed: '移除' }[kind]}</td><td className="sp-break">{typeof row === 'string' ? row : `${row.name} (${row.id})`}</td><td className="sp-break">{typeof row === 'string' ? '—' : row.fields?.join('、') || '整条记录'}</td>
      </tr>))}
      {value.added.length + value.changed.length + value.removed.length === 0 && <tr><td colSpan={3}>无资料变化</td></tr>}
    </tbody></table></div>
  </details>)}</div>;
}

function App({ csrfToken }: { csrfToken: string }) {
  const [files, setFiles] = useState<FileUploadItem[]>([]);
  const [listing, setListing] = useState<Listing | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [selected, setSelected] = useState('');
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('diff');
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const uploads = useRef(new Map<string, XMLHttpRequest>());
  const alive = useRef(true);
  const mutation = useRef<AbortController | null>(null);
  const reload = () => setRefresh(n => n + 1);

  useEffect(() => () => { alive.current = false; for (const xhr of uploads.current.values()) xhr.abort(); mutation.current?.abort(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const result = await api<Listing>(`${BASE}?page=${page}`, csrfToken, undefined, controller.signal);
        if (controller.signal.aborted) return;
        setListing(result);
        if (!selected && result.items.length) setSelected(result.items[0].id);
        if (selected) {
          const item = await api<Detail>(`${BASE}/${selected}`, csrfToken, undefined, controller.signal);
          if (controller.signal.aborted) return;
          setDetail(item);
        }
        timer = setTimeout(load, result.items.some(i => running(i.job_status)) ? 2500 : 15000);
      } catch (e) {
        if (!controller.signal.aborted) { setError(message(e)); timer = setTimeout(load, 15000); }
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [page, selected, refresh, csrfToken]);

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
      setSelected(result.package.id); setDetail(null); setPage(1); reload();
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
    void action(c.kind === 'publish' ? `${BASE}/${c.target}/publish` : `/api/admin/seasons/${c.seasonId}/rollback`,
      { expected_revision: c.revision, release_id: c.target, acknowledge_warnings: true }, c.kind === 'publish' ? '版本已发布，关键页面检查通过。' : '已回滚，关键页面检查通过。');
  }
  const currentDetail = detail?.id === selected ? detail : null;
  const report = currentDetail?.report;
  const isActive = currentDetail?.active.release_id === selected;

  return <>
    {error && <div role="alert" className="sp-notice sp-error">{error}</div>}
    {notice && <div role="status" className="sp-notice">{notice}</div>}
    <div className="sp-layout">
      <div className="sp-stack">
        <section className="sp-panel sp-stack" aria-labelledby="sp-upload-title">
          <div><h2 id="sp-upload-title">上传赛季更新包</h2><p className="sp-muted">本地准备完整资料，在这里审核并发布。</p></div>
          <FileUpload variant="centered" value={files} onValueChange={setFiles} onFilesAdded={items => items.forEach(upload)} onRetry={upload}
            onRemove={item => uploads.current.get(item.id)?.abort()} accept=".zip,application/zip" multiple={false} maxFiles={1}
            title="将更新包拖到这里" description={`支持 ZIP，最大 ${Math.round((listing?.max_bytes || 256 * 1024 ** 2) / 1024 ** 2)} MB`} browseLabel="选择更新包" />
          <p className="sp-muted">文件包含资料、图片、玩法配置、更新说明与来源。上传成功后还需完成校验和发布；移除文件行仅清理本次上传列表。</p>
        </section>
        <section className="sp-panel">
          <div className="sp-head"><h2>更新包记录</h2><Button onClick={reload}><RefreshCw size={14} />刷新</Button></div>
          <div className="sp-stack">{!listing ? <p className="sp-muted">正在读取记录…</p> : listing.items.length === 0 ? <p className="sp-muted">还没有更新包。上传后，处理进度和发布记录会保存在这里。</p> : listing.items.map(item => <button key={item.id} type="button" className="sp-package" aria-pressed={selected === item.id} onClick={() => { setSelected(item.id); setTab('diff'); }}>
            <span className="sp-head" style={{ margin: 0 }}><strong>{item.season_id.toUpperCase()} · {item.game_version} · r{item.data_revision}</strong><span className="sp-tag">{listing.seasons.find(s => s.season_id === item.season_id)?.active.release_id === item.id ? '当前线上' : item.published_at && item.state === 'ready' ? '历史版本' : text(item.state)}</span></span>
            <span className="sp-muted sp-break">{item.package_id}</span><span className="sp-muted">{item.created_at}</span>
          </button>)}</div>
          {!!listing?.total && <div className="sp-actions" style={{ marginTop: 16 }}><Button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</Button><span className="sp-muted">{page} / {Math.ceil(listing.total / 20)}</span><Button disabled={page * 20 >= listing.total} onClick={() => setPage(p => p + 1)}>下一页</Button></div>}
        </section>
      </div>
      <div className="sp-stack">
        <section className="sp-panel sp-stack" aria-labelledby="sp-review-title">
          <div className="sp-head" style={{ margin: 0 }}><h2 id="sp-review-title">{currentDetail ? '检查更新内容' : '版本审核'}</h2>{currentDetail && <span className="sp-tag">{isActive ? '当前线上' : text(currentDetail.state)}</span>}</div>
          {!selected ? <p className="sp-muted">选择一个更新包，查看处理结果、差异和预览。</p> : !currentDetail ? <p className="sp-muted">正在读取更新包…</p> : <>
            <div><h3 className="sp-break">{currentDetail.package_id}</h3><p className="sp-muted">{currentDetail.season_id.toUpperCase()} · 游戏版本 {currentDetail.game_version} · 资料修订 {currentDetail.data_revision}</p></div>
            <div role="status"><p className={currentDetail.state === 'rejected' ? 'sp-error' : 'sp-muted'}>{currentDetail.job.message || '等待后台处理。离开页面后任务仍会继续。'}</p><progress className="sp-progress" value={currentDetail.job.progress} max={100} aria-label="服务端校验进度" /></div>
            <div className="sp-actions">
              {running(currentDetail.job.status) && <Button disabled={busy || !!currentDetail.job.cancel_requested} onClick={() => void action(`${BASE}/${selected}/cancel`, {}, '已请求取消校验。')}>{currentDetail.job.cancel_requested ? '正在取消…' : '取消校验'}</Button>}
              {['failed', 'cancelled'].includes(currentDetail.job.status) && <Button disabled={busy} onClick={() => void action(`${BASE}/${selected}/retry`, {}, '任务已重新排队。')}><RotateCcw size={14} />重试校验</Button>}
              <a className="sp-btn" href={`${BASE}/${selected}/download`}>下载原包</a>
            </div>
            {currentDetail.state === 'ready' && <>
              <div className="sp-metrics">{Object.entries(report?.counts || {}).map(([key, value]) => <div className="sp-metric" key={key}><span className="sp-muted">{text(key)}</span><strong>{value}</strong></div>)}</div>
              {!!report?.warnings?.length && <div className="sp-warning">{report.warnings.map(w => <p key={w}>{w}</p>)}</div>}
              <div className="sp-actions"><a className="sp-btn" href={currentDetail.preview_url} target="_blank" rel="noreferrer">预览资料库<ArrowUpRight size={14} /></a><a className="sp-btn" href={currentDetail.simulator_url} target="_blank" rel="noreferrer">预览模拟器<ArrowUpRight size={14} /></a></div>
              <div className="sp-tabs" aria-label="审核内容">{[['diff', '资料差异'], ['notes', '更新说明'], ['sources', '玩法与来源']].map(([key, label]) => <button type="button" className={`sp-btn ${tab === key ? 'sp-primary' : ''}`} aria-pressed={tab === key} onClick={() => setTab(key)} key={key}>{label}</button>)}</div>
              {tab === 'diff' && report?.diff && <div><p className="sp-muted">比较基准：线上修订 {report.compared_active?.revision}。切换过线上版本后需重新比较。</p><DiffReport diff={report.diff} /></div>}
              {tab === 'notes' && report?.notes && <div className="sp-stack"><h3>{report.notes.title}</h3><p>{report.notes.summary}</p>{report.notes.sections.map((s, i) => <div key={i}><h3>{s.title}</h3>{s.items.map((item, j) => <p key={j}>· {item}</p>)}</div>)}<p className="sp-muted">随包说明保留在版本记录中，网站的「更新公告」可单独编辑发布。</p></div>}
              {tab === 'sources' && <div className="sp-stack"><div><h3>本版本玩法</h3>{currentDetail.manifest.mechanics.length ? currentDetail.manifest.mechanics.map(m => <p key={m.id}>{m.display_name} <span className="sp-muted">{m.id} · {m.presentation}</span></p>) : <p className="sp-muted">本赛季没有特殊玩法。</p>}</div><p className="sp-muted">共 {report?.images || 0} 张图片，{report?.supplement_count || 0} 个补充字段，其中 {report?.inherited_count || 0} 个沿用历史版本、尚未核验。</p><details><summary>查看完整来源记录（{report?.sources?.length || 0}）</summary><pre>{JSON.stringify(report?.sources || [], null, 2)}</pre></details></div>}
              <div className="sp-actions"><Button disabled={busy} onClick={() => void action(`${BASE}/${selected}/compare`, {}, '差异已按最新线上版本重新计算。')}><RefreshCw size={14} />重新比较</Button>
                <Button primary disabled={busy || isActive || report?.compared_active?.revision !== currentDetail.active.revision} onClick={() => setConfirmation({ kind: 'publish', seasonId: currentDetail.season_id, revision: currentDetail.active.revision, target: selected, label: currentDetail.package_id, warnings: report?.warnings || [] })}><PackageCheck size={14} />{isActive ? '已在线上' : report?.compared_active?.revision !== currentDetail.active.revision ? '请先重新比较' : '审核并发布'}</Button>
                {!!currentDetail.published_at && !isActive && <Button disabled={busy} onClick={() => setConfirmation({ kind: 'rollback', seasonId: currentDetail.season_id, revision: currentDetail.active.revision, target: selected, label: `恢复至 ${currentDetail.package_id}`, warnings: [] })}>回滚到此版本</Button>}
              </div>
            </>}
          </>}
        </section>
        <section className="sp-panel"><div className="sp-head"><h2>线上版本</h2><span className="sp-muted">各赛季独立切换</span></div><div className="sp-stack">{listing?.seasons.map(s => <div key={s.season_id} className="sp-head" style={{ margin: 0 }}><div><h3>{s.display_name}</h3><p className="sp-muted">{s.active.release_id ? `${s.active.game_version} · r${s.active.data_revision} · 线上修订 ${s.active.revision}` : `随代码部署的基准版本 · ${s.game_version}`}</p></div>{s.active.revision > 0 && <Button disabled={busy} onClick={() => setConfirmation({ kind: 'rollback', seasonId: s.season_id, revision: s.active.revision, target: s.active.previous_release_id, label: `${s.display_name} → ${s.active.previous_release_id ? '上一个已发布版本' : '随代码部署的基准版本'}`, warnings: [] })}><RotateCcw size={14} />回滚</Button>}</div>)}</div></section>
        <section className="sp-panel"><h2>最近操作</h2><div className="sp-table-wrap"><table><thead><tr><th>时间</th><th>赛季</th><th>操作</th><th>结果</th></tr></thead><tbody>{listing?.events.map(e => <tr key={e.id}><td>{e.created_at}</td><td>{e.season_id}</td><td>{text(e.action)}</td><td>{text(e.status)}</td></tr>)}</tbody></table>{listing?.events.length === 0 && <p className="sp-muted">暂无操作记录。</p>}</div></section>
      </div>
    </div>
    {confirmation && <ConfirmDialog value={confirmation} busy={busy} close={() => setConfirmation(null)} confirm={confirm} />}
  </>;
}

let root: Root | undefined;
export function mount(element: HTMLElement, options: { csrfToken: string }) { unmount(); root = createRoot(element); root.render(<App csrfToken={options.csrfToken} />); }
export function unmount() { root?.unmount(); root = undefined; }
