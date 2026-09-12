// Adapted from the supplied InteractiveLogsTable reference for JCC's real audit API.
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown, ChevronLeft, ChevronRight, Filter, Search, RefreshCw, ScrollText, X, ArrowDown, SlidersHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Log = {
  id: number; created_at: string; action: string; action_label: string; kind: string; kind_label: string;
  target_type: string; target_label: string; target_key: string | null; target_id: number | null;
  actor_user_id: number | null; actor_label: string; actor_username: string | null;
};
type Option = { value: string; label: string; count: number };
type Listing = {
  items: Log[]; total: number; total_all: number; page: number; page_size: number; total_pages: number;
  filters: { targets: Option[]; kinds: Option[] };
};
type Filters = { targets: string[]; kinds: string[]; start: string; end: string };
type Detail = Log & { before: unknown; after: unknown };
const EMPTY_FILTERS: Filters = { targets: [], kinds: [], start: '', end: '' };
const BASE = '/api/admin/audit-logs';
const target = (log: Log) => log.target_key || (log.target_id != null ? '#' + log.target_id : '全局');
const errorMessage = (error: unknown) => error instanceof Error ? error.message : '读取失败，请重试';

async function read<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, credentials: 'same-origin', cache: 'no-store' });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || (response.status === 401 ? '登录已过期，请重新登录管理员账号' : '读取失败，请稍后重试'));
  return body as T;
}

const fieldLabels: Record<string, string> = {
  username: '用户名', nickname: '昵称', email: '邮箱', role: '角色', status: '状态',
  password: '密码', password_hash: '密码摘要', title: '标题', name: '名称',
  season_id: '赛季', created_at: '创建时间', updated_at: '更新时间', description: '说明',
  setting_key: '设置项', setting_value: '设置值', message: '内容', is_active: '是否启用',
  admin_like_adjustment: '点赞调整', admin_copy_adjustment: '复制调整',
  created_count: '新增数量', duplicate_existing_count: '已有阵容', invalid_count: '无效数量',
  report_date: '报告日期', hide_lineup: '隐藏阵容', filename: '文件名', item_total: '阵容总数',
};
function Snapshot({ title, value }: { title: string; value: unknown }) {
  return <section className="al-snapshot"><h4>{title}</h4>
    {value == null ? <p className="al-snapshot-empty">未记录</p> :
      typeof value === 'object' && !Array.isArray(value) ? <dl>{Object.entries(value).map(([key, item]) =>
        <div key={key}><dt title={key}>{fieldLabels[key] || key}</dt><dd>{typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item ?? '—')}</dd></div>
      )}</dl> : <pre>{JSON.stringify(value, null, 2)}</pre>}
  </section>;
}
function LogDetails({ log }: { log: Log }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    read<Detail>(BASE + '/' + log.id, controller.signal).then(setDetail).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [log.id, retry]);
  return <div className="al-details" id={'audit-detail-' + log.id} role="region" aria-label={'日志 #' + log.id + ' 详情'}>
    <div className="al-detail-meta">
      <div><span>记录编号</span><strong className="al-mono">#{log.id}</strong></div>
      <div><span>完整时间</span><strong className="al-mono">{log.created_at}</strong></div>
      <div><span>操作账号</span><strong>{log.actor_username ? '@' + log.actor_username : log.actor_label}{log.actor_user_id != null && ' · #' + log.actor_user_id}</strong></div>
      <div><span>目标标识</span><strong className="al-mono">{log.target_type} · {target(log)}{log.target_key && log.target_id != null && ' · #' + log.target_id}</strong></div>
    </div>
    <div className="al-detail-caption"><Badge>{log.action}</Badge><span>历史快照与提交内容可能包含不同字段；敏感字段已隐藏。</span></div>
    {error ? <div role="alert" className="al-error">{error}<Button onClick={() => setRetry(n => n + 1)}>重试详情</Button></div> :
      !detail ? <p role="status" className="al-loading">正在读取操作详情…</p> :
      detail.before == null && detail.after == null ? <p className="al-no-snapshot">此操作未保存前后快照，操作信息见上方。</p> :
      <div className="al-snapshots"><Snapshot title="操作前记录" value={detail.before} /><Snapshot title="本次记录 / 提交内容" value={detail.after} /></div>}
  </div>;
}
function LogRow({ log, expanded, onToggle }: { log: Log; expanded: boolean; onToggle: () => void }) {
  const [date, time] = log.created_at.replace('T', ' ').split(' ');
  return <article className={'al-record' + (expanded ? ' is-expanded' : '')}>
    <button type="button" className="al-row" aria-expanded={expanded} aria-controls={'audit-detail-' + log.id} onClick={onToggle}>
      <span className="al-row-chevron"><ChevronDown size={15} /></span>
      <Badge className={'al-kind al-kind-' + log.kind}>{log.kind_label}</Badge>
      <time className="al-time al-mono" dateTime={log.created_at.replace(' ', 'T')}><strong>{time || '—'}</strong><small>{date}</small></time>
      <span className="al-action"><strong>{log.action_label}</strong><small title={log.action}>{log.action}</small></span>
      <span className="al-target"><strong>{log.target_label}</strong><small className="al-mono" title={target(log)}>{target(log)}</small></span>
      <span className="al-actor"><span className="al-actor-mark" aria-hidden="true">{Array.from(log.actor_label)[0]}</span><span title={log.actor_label}>{log.actor_label}</span></span>
    </button>
    <AnimatePresence initial={false}>
      {expanded && <motion.div key="detail" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: .18 }} className="al-expand">
        <LogDetails log={log} />
      </motion.div>}
    </AnimatePresence>
  </article>;
}
function FilterPanel({ filters, options, onChange, onClose }: { filters: Filters; options: Listing['filters']; onChange: (filters: Filters) => void; onClose: () => void }) {
  const toggle = (key: 'targets' | 'kinds', value: string) => onChange({ ...filters, [key]: filters[key].includes(value) ? filters[key].filter(item => item !== value) : [...filters[key], value] });
  return <aside className="al-filters" id="audit-filters" aria-label="日志筛选条件">
    <div className="al-filter-heading"><strong><SlidersHorizontal size={14} />筛选条件</strong><Button variant="ghost" onClick={() => onChange(EMPTY_FILTERS)}>重置</Button></div>
    {(['kinds', 'targets'] as const).map(key => <fieldset key={key}><legend>{key === 'kinds' ? '操作类型' : '操作对象'}</legend>
      {options[key].map(option => <button key={option.value} type="button" className="al-filter-option" aria-pressed={filters[key].includes(option.value)} onClick={() => toggle(key, option.value)}>
        <span className="al-check">{filters[key].includes(option.value) && <Check size={12} />}</span><span>{option.label}</span><small>{option.count}</small>
      </button>)}
    </fieldset>)}
    <fieldset className="al-date-filters"><legend>发生日期</legend><label>开始日期<Input aria-label="开始日期" type="date" value={filters.start} onChange={event => onChange({ ...filters, start: event.target.value })} /></label>
      <label>结束日期<Input aria-label="结束日期" type="date" value={filters.end} onChange={event => onChange({ ...filters, end: event.target.value })} /></label></fieldset>
    <p className="al-filter-note">数量为全部历史记录。多选同组条件可扩大范围。</p>
    <Button className="al-filter-done" onClick={onClose}>收起筛选，查看结果</Button>
  </aside>;
}
export function InteractiveLogsTable() {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [loadedKey, setLoadedKey] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const composing = useRef(false);
  const key = JSON.stringify({ search, filters, page, pageSize, refresh });
  const pending = loading || loadedKey !== key || query.trim() !== search;
  useEffect(() => {
    if (composing.current) return;
    const timer = window.setTimeout(() => { setSearch(query.trim()); setPage(1); }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setExpandedId(null);
    const params = new URLSearchParams({ q: search, page: String(page), page_size: String(pageSize), start: filters.start, end: filters.end });
    filters.targets.forEach(value => params.append('target_type', value));
    filters.kinds.forEach(value => params.append('kind', value));
    read<Listing>(BASE + '?' + params, controller.signal).then(result => {
      if (!controller.signal.aborted) { setData(result); setLoadedKey(key); }
    }).catch(error => {
      if (!controller.signal.aborted) { setError(errorMessage(error)); setLoadedKey(key); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [key]);
  const count = filters.targets.length + filters.kinds.length + Number(!!filters.start) + Number(!!filters.end);
  const active = count > 0 || !!query;
  const changeFilters = (value: Filters) => { setFilters(value); setPage(1); };
  const clear = () => { setQuery(''); setSearch(''); setFilters(EMPTY_FILTERS); setPage(1); searchRef.current?.focus(); };
  const options = data?.filters || { targets: [], kinds: [] };
  return <section className="al-panel" aria-labelledby="audit-title">
    <header className="al-header">
      <div className="al-heading"><span className="al-title-icon"><ScrollText size={21} /></span><div><div className="al-title-line"><h2 id="audit-title">操作记录</h2><Badge>{data ? data.total_all.toLocaleString() : '—'} 条</Badge></div><p>查看操作人、目标与详细变更记录</p></div></div>
      <span className="al-order"><ArrowDown size={13} />最近操作优先</span>
    </header>
    <div className="al-toolbar">
      <div className="al-search"><Search size={17} aria-hidden="true" /><Input ref={searchRef} type="search" aria-label="搜索审计日志" placeholder="搜索操作、操作人或目标标识…" value={query} maxLength={200} onCompositionStart={() => { composing.current = true; }} onCompositionEnd={event => { composing.current = false; setSearch(event.currentTarget.value.trim()); setPage(1); }} onChange={event => setQuery(event.target.value)} />
        {query && <Button variant="ghost" aria-label="清空搜索" onClick={() => { setQuery(''); setSearch(''); setPage(1); searchRef.current?.focus(); }}><X size={14} /></Button>}
      </div>
      <Button variant={showFilters ? 'default' : 'outline'} aria-expanded={showFilters} aria-controls="audit-filters" onClick={() => setShowFilters(value => !value)}><Filter size={15} />筛选{count > 0 && <span className="al-filter-count">{count}</span>}</Button>
      <Button className="al-refresh" aria-label="刷新日志" disabled={pending} onClick={() => setRefresh(n => n + 1)}><RefreshCw size={15} className={pending ? 'al-spin' : ''} /><span>刷新</span></Button>
    </div>
    {active && <div className="al-active-filters"><span>当前条件</span>
      {query && <Badge>搜索：{query}</Badge>}
      {(['kinds', 'targets'] as const).flatMap(group => filters[group].map(value => <button type="button" key={group + value} onClick={() => changeFilters({ ...filters, [group]: filters[group].filter(item => item !== value) })} aria-label={'移除筛选 ' + (options[group].find(item => item.value === value)?.label || value)}>{options[group].find(item => item.value === value)?.label || value}<X size={12} /></button>))}
      {(filters.start || filters.end) && <Badge>{filters.start || '不限'} 至 {filters.end || '不限'}</Badge>}
      <Button variant="ghost" onClick={clear}>清除全部</Button>
    </div>}
    <div className={'al-body' + (showFilters ? ' al-with-filters' : '')}>
      <AnimatePresence initial={false}>{showFilters && <motion.div key="filters" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }}><FilterPanel filters={filters} options={options} onChange={changeFilters} onClose={() => { setShowFilters(false); searchRef.current?.focus({ preventScroll: true }); }} /></motion.div>}</AnimatePresence>
      <div className="al-results" aria-busy={pending}>
        <div className="al-table-head" aria-hidden="true"><span /><span>类型</span><span>发生时间</span><span>操作内容</span><span>操作对象</span><span>操作人</span></div>
        <div className="al-result-status" role="status">{pending ? '正在读取日志…' : error ? '日志加载失败' : '找到 ' + (data?.total || 0) + ' 条记录'}</div>
        {error ? <div className="al-state"><ScrollText size={28} /><h3>暂时无法读取日志</h3><p role="alert">{error}</p><Button onClick={() => setRefresh(n => n + 1)}>重新加载</Button></div> :
          pending ? <div className="al-skeletons" aria-hidden="true">{Array.from({ length: 6 }, (_, i) => <div key={i}><span /><span /><span /></div>)}</div> :
          !data?.items.length ? <div className="al-state"><Search size={29} /><h3>{active ? '没有符合条件的记录' : '暂无审计日志'}</h3><p>{active ? '试试其他关键词，或减少筛选条件。' : '发生关键操作后，记录会出现在这里。'}</p>{active && <Button onClick={clear}>清除全部条件</Button>}</div> :
          <div className="al-records">{data.items.map(log => <LogRow key={log.id} log={log} expanded={expandedId === log.id} onToggle={() => setExpandedId(current => current === log.id ? null : log.id)} />)}</div>}
        <footer className="al-footer">
          <span>{error ? '未能读取记录' : !pending && data ? data.total ? '显示 ' + ((data.page - 1) * data.page_size + 1) + '–' + Math.min(data.page * data.page_size, data.total) + ' 条，共 ' + data.total + ' 条' : '共 0 条记录' : '正在读取'}</span>
          <div><label className="al-page-size"><select aria-label="每页条数" value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); }}><option value="20">20 条 / 页</option><option value="30">30 条 / 页</option><option value="50">50 条 / 页</option></select></label>
            <Button aria-label="上一页" disabled={pending || !!error || !data || data.page <= 1} onClick={() => setPage((data?.page || 1) - 1)}><ChevronLeft size={16} /></Button>
            <span className="al-page-number">{data?.page || 1} / {data?.total_pages || 1}</span>
            <Button aria-label="下一页" disabled={pending || !!error || !data || data.page >= data.total_pages} onClick={() => setPage((data?.page || 1) + 1)}><ChevronRight size={16} /></Button>
          </div>
        </footer>
      </div>
    </div>
  </section>;
}
