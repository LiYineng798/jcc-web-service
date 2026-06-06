const TIER_ORDER = ['S', 'A', 'B', 'C', 'D'];
const COST_TABS = ['全部', '1费', '2费', '3费', '4费', '5费', '6费', '7费', '其他'];
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif'];

const state = {
  assets: [],
  selectedAssetId: '',
  selectedCost: '全部',
  assetSearch: '',
  comps: [],
  seasons: [],
  defaultSeasonId: '',
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  server: $('#serverInput'),
  token: $('#tokenInput'),
  loadSeasons: $('#loadSeasonsButton'),
  season: $('#seasonSelect'),
  message: $('#message'),
  imageInput: $('#imageInput'),
  folderInput: $('#folderInput'),
  assetSearch: $('#assetSearchInput'),
  costTabs: $('#costTabs'),
  assetGrid: $('#assetGrid'),
  addComp: $('#addCompButton'),
  compList: $('#compList'),
  previewGrid: $('#previewGrid'),
  jsonImportInput: $('#jsonImportInput'),
  fetchCurrent: $('#fetchCurrentButton'),
  exportButton: $('#exportButton'),
  uploadButton: $('#uploadButton'),
  jsonOutput: $('#jsonOutput'),
};

boot();

function boot() {
  renderCostTabs();
  addComp();
  bindEvents();
}

function bindEvents() {
  elements.loadSeasons.addEventListener('click', loadSeasons);
  elements.imageInput.addEventListener('change', importImages);
  elements.folderInput.addEventListener('change', importImages);
  elements.assetSearch.addEventListener('input', (event) => {
    state.assetSearch = event.target.value.trim().toLowerCase();
    renderAssets();
  });
  elements.addComp.addEventListener('click', addComp);
  elements.jsonImportInput.addEventListener('change', importJsonFile);
  elements.fetchCurrent.addEventListener('click', fetchCurrentLiveComps);
  elements.exportButton.addEventListener('click', () => {
    elements.jsonOutput.value = JSON.stringify(buildPayload(false), null, 2);
  });
  elements.uploadButton.addEventListener('click', uploadAll);
}

function showMessage(text) {
  elements.message.textContent = text;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error || '操作失败');
  return data;
}

async function loadSeasons() {
  try {
    showMessage('正在拉取赛季...');
    const server = elements.server.value.trim();
    const data = await api(`/api/seasons?server=${encodeURIComponent(server)}`);
    state.seasons = data.seasons || [];
    state.defaultSeasonId = data.default_season_id || state.seasons[0]?.id || '';
    renderSeasons();
    showMessage(`已拉取 ${state.seasons.length} 个赛季`);
  } catch (error) {
    showMessage(error.message);
  }
}

function renderSeasons() {
  elements.season.replaceChildren();
  state.seasons.forEach((season) => {
    const option = document.createElement('option');
    option.value = season.id;
    option.textContent = season.name || season.id;
    option.selected = season.id === state.defaultSeasonId;
    elements.season.append(option);
  });
}

function normalizeAssetKey(value) {
  return decodeURIComponent(String(value || '').split(/[\\/]/).pop()).trim().toLowerCase();
}

function assetByReference(value) {
  const key = normalizeAssetKey(value);
  if (!key) return null;
  return state.assets.find((asset) => (
    normalizeAssetKey(asset.name) === key ||
    normalizeAssetKey(asset.relativePath) === key ||
    normalizeAssetKey(asset.uploadedUrl) === key
  )) || null;
}

function createRemoteAsset(url, label = '') {
  const value = String(url || '').trim();
  if (!value) return '';
  const existing = assetByReference(value);
  if (existing) return existing.id;
  const id = crypto.randomUUID();
  const name = label || normalizeAssetKey(value) || value;
  const server = elements.server.value.trim().replace(/\/$/, '');
  const previewUrl = value.startsWith('/api/') && server ? `${server}${value}` : value;
  state.assets.push({
    id,
    name,
    relativePath: value,
    file: null,
    cost: inferCost(value),
    previewUrl,
    contentBase64: '',
    uploadedUrl: value,
  });
  return id;
}

function assetIdFromReference(value) {
  const matched = assetByReference(value);
  if (matched) return matched.id;
  const normalized = String(value || '').trim();
  if (/^(https?:\/\/|\/api\/)/.test(normalized)) return createRemoteAsset(normalized);
  return '';
}

function loadPayloadIntoEditor(payload, label = 'JSON') {
  if (!payload || typeof payload !== 'object' || !payload.tiers || typeof payload.tiers !== 'object') {
    throw new Error('JSON 格式不正确：缺少 tiers');
  }
  const importedComps = [];
  const missingRefs = new Set();
  TIER_ORDER.forEach((tier) => {
    const items = Array.isArray(payload.tiers[tier]) ? payload.tiers[tier] : [];
    items.forEach((item, index) => {
      const mainAssetId = assetIdFromReference(item.mainAvatar);
      if (item.mainAvatar && !mainAssetId) missingRefs.add(item.mainAvatar);
      const heroAssetIds = (Array.isArray(item.heroImages) ? item.heroImages : []).map((ref) => {
        const assetId = assetIdFromReference(ref);
        if (ref && !assetId) missingRefs.add(ref);
        return assetId;
      }).filter(Boolean);
      importedComps.push({
        id: String(item.id || `manual-${Date.now()}-${importedComps.length + 1}`),
        title: String(item.title || ''),
        tier: TIER_ORDER.includes(item.tier) ? item.tier : tier,
        jccCode: String(item.jccCode || ''),
        mainAssetId,
        heroAssetIds,
      });
    });
  });
  state.comps = importedComps.length ? importedComps : [{
    id: `manual-${Date.now()}-1`,
    title: '',
    tier: 'S',
    jccCode: '',
    mainAssetId: '',
    heroAssetIds: [],
  }];
  elements.jsonOutput.value = JSON.stringify(payload, null, 2);
  renderAssets();
  renderComps();
  renderPreview();
  const missingText = missingRefs.size ? `，${missingRefs.size} 个图片文件名未匹配，请先导入对应图片文件夹` : '';
  showMessage(`已导入 ${label}：${importedComps.length} 套阵容${missingText}`);
}

async function importJsonFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    loadPayloadIntoEditor(JSON.parse(text), file.name);
  } catch (error) {
    showMessage(error.message);
  } finally {
    event.target.value = '';
  }
}

async function fetchCurrentLiveComps() {
  try {
    const server = elements.server.value.trim();
    const seasonId = elements.season.value;
    if (!server) throw new Error('服务器地址不能为空');
    if (!seasonId) throw new Error('请先拉取并选择赛季');
    showMessage('正在获取服务器当前阵容...');
    const payload = await api(`/api/current-live-comps?server=${encodeURIComponent(server)}&season_id=${encodeURIComponent(seasonId)}`);
    loadPayloadIntoEditor(payload, '服务器当前阵容');
  } catch (error) {
    showMessage(error.message);
  }
}

function renderCostTabs() {
  elements.costTabs.replaceChildren();
  COST_TABS.forEach((cost) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `cost-tab${cost === state.selectedCost ? ' is-active' : ''}`;
    button.textContent = cost;
    button.addEventListener('click', () => {
      state.selectedCost = cost;
      renderCostTabs();
      renderAssets();
    });
    elements.costTabs.append(button);
  });
}

async function importImages(event) {
  const files = Array.from(event.target.files || []);
  let imported = 0;
  let skipped = 0;
  for (const file of files) {
    if (!isImageFile(file)) {
      skipped += 1;
      continue;
    }
    const id = crypto.randomUUID();
    const relativePath = file.webkitRelativePath || file.name;
    const cost = inferCost(relativePath);
    const contentBase64 = await readFileAsBase64(file);
    state.assets.push({
      id,
      name: file.name,
      relativePath,
      file,
      cost,
      previewUrl: URL.createObjectURL(file),
      contentBase64,
      uploadedUrl: '',
    });
    imported += 1;
  }
  renderAssets();
  showMessage(`已导入 ${imported} 张图片${skipped ? `，跳过 ${skipped} 个非图片文件` : ''}`);
  event.target.value = '';
}

function isImageFile(file) {
  if (file.type && file.type.startsWith('image/')) return true;
  const name = String(file.name || '').toLowerCase();
  return IMAGE_EXTENSIONS.some((suffix) => name.endsWith(suffix));
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      const value = String(reader.result || '');
      resolve(value.includes(',') ? value.split(',', 2)[1] : value);
    });
    reader.addEventListener('error', () => reject(reader.error || new Error('读取图片失败')));
    reader.readAsDataURL(file);
  });
}

function inferCost(name) {
  const normalized = String(name || '').toLowerCase();
  for (const cost of ['1', '2', '3', '4', '5', '6', '7']) {
    if (
      normalized.includes(`${cost}费`) ||
      normalized.includes(`cost-${cost}`) ||
      normalized.includes(`price-${cost}`) ||
      normalized.includes(`price_${cost}`) ||
      normalized.includes(`/price-${cost}/`) ||
      normalized.includes(`\\price-${cost}\\`)
    ) {
      return `${cost}费`;
    }
  }
  return '其他';
}

function renderAssets() {
  elements.assetGrid.replaceChildren();
  const assets = state.assets.filter((asset) => {
    const matchesCost = state.selectedCost === '全部' || asset.cost === state.selectedCost;
    const haystack = `${asset.name || ''} ${asset.relativePath || ''}`.toLowerCase();
    const matchesSearch = !state.assetSearch || haystack.includes(state.assetSearch);
    return matchesCost && matchesSearch;
  });
  if (!assets.length) {
    const empty = document.createElement('div');
    empty.className = 'asset-empty';
    empty.textContent = state.assets.length ? '没有匹配的图片' : '还没有导入图片';
    elements.assetGrid.append(empty);
    return;
  }
  assets.forEach((asset) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = `asset-card${asset.id === state.selectedAssetId ? ' is-selected' : ''}`;
    card.innerHTML = `
      <img src="${asset.previewUrl}" alt="${escapeHtml(asset.name)}" />
      <div class="asset-meta">${escapeHtml(asset.cost)}<br>${escapeHtml(asset.relativePath || asset.name)}</div>
    `;
    card.addEventListener('click', () => {
      state.selectedAssetId = asset.id;
      renderAssets();
    });
    elements.assetGrid.append(card);
  });
}

function addComp() {
  state.comps.push({
    id: `manual-${Date.now()}-${state.comps.length + 1}`,
    title: '',
    tier: 'S',
    jccCode: '',
    mainAssetId: '',
    heroAssetIds: [],
  });
  renderComps();
  renderPreview();
}

function renderComps() {
  elements.compList.replaceChildren();
  state.comps.forEach((comp, index) => {
    const card = document.createElement('article');
    card.className = 'comp-card';
    card.innerHTML = `
      <div class="comp-actions">
        <strong>阵容 ${index + 1}</strong>
        <button type="button" data-action="remove">删除</button>
      </div>
      <div class="comp-grid">
        <label class="field"><span>ID</span><input data-field="id" value="${escapeHtml(comp.id)}" /></label>
        <label class="field"><span>等级</span><select data-field="tier">${TIER_ORDER.map((tier) => `<option value="${tier}" ${tier === comp.tier ? 'selected' : ''}>${tier}</option>`).join('')}</select></label>
        <label class="field"><span>名称</span><input data-field="title" value="${escapeHtml(comp.title)}" placeholder="例如：机甲九五" /></label>
        <label class="field"><span>阵容码</span><input data-field="jccCode" value="${escapeHtml(comp.jccCode)}" placeholder="#..." /></label>
      </div>
      <div class="image-slot" data-action="set-main">
        <strong>主图</strong>
        ${renderEditableAssetThumb(comp.mainAssetId, 'remove-main') || '<span class="comp-meta">选中左侧图片后点击这里</span>'}
      </div>
      <div class="image-slot" data-action="add-hero">
        <strong>英雄图片</strong>
        <div class="hero-strip">${comp.heroAssetIds.map((assetId, heroIndex) => renderEditableAssetThumb(assetId, 'remove-hero', heroIndex)).join('') || '<span class="comp-meta">选中左侧图片后点击这里添加</span>'}</div>
      </div>
    `;
    card.querySelectorAll('[data-field]').forEach((input) => {
      input.addEventListener('input', () => {
        comp[input.dataset.field] = input.value;
        renderPreview();
      });
    });
    card.querySelector('[data-action="remove"]').addEventListener('click', () => {
      state.comps.splice(index, 1);
      renderComps();
      renderPreview();
    });
    card.querySelector('[data-action="set-main"]').addEventListener('click', () => {
      if (!state.selectedAssetId) return showMessage('请先选择一张图片');
      comp.mainAssetId = state.selectedAssetId;
      renderComps();
      renderPreview();
    });
    card.querySelector('[data-action="add-hero"]').addEventListener('click', () => {
      if (!state.selectedAssetId) return showMessage('请先选择一张图片');
      if (!comp.heroAssetIds.includes(state.selectedAssetId)) comp.heroAssetIds.push(state.selectedAssetId);
      renderComps();
      renderPreview();
    });
    card.querySelectorAll('[data-action="remove-main"]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        comp.mainAssetId = '';
        renderComps();
        renderPreview();
      });
    });
    card.querySelectorAll('[data-action="remove-hero"]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        comp.heroAssetIds.splice(Number(button.dataset.heroIndex), 1);
        renderComps();
        renderPreview();
      });
    });
    elements.compList.append(card);
  });
}

function renderAssetThumb(assetId) {
  const asset = state.assets.find((item) => item.id === assetId);
  if (!asset) return '';
  return `<img class="hero-thumb" src="${asset.previewUrl}" alt="${escapeHtml(asset.name)}" title="${escapeHtml(asset.name)}" />`;
}

function renderEditableAssetThumb(assetId, action, heroIndex = '') {
  const asset = state.assets.find((item) => item.id === assetId);
  if (!asset) return '';
  return `
    <span class="thumb-wrap">
      <img class="hero-thumb" src="${asset.previewUrl}" alt="${escapeHtml(asset.name)}" title="${escapeHtml(asset.name)}" />
      <button class="thumb-remove" type="button" data-action="${action}" data-hero-index="${heroIndex}" aria-label="移除${escapeHtml(asset.name)}">×</button>
    </span>
  `;
}

function renderPreview() {
  elements.previewGrid.replaceChildren();
  state.comps.forEach((comp) => {
    const main = state.assets.find((asset) => asset.id === comp.mainAssetId);
    const card = document.createElement('article');
    card.className = 'preview-card';
    card.innerHTML = `
      <div class="preview-head">
        ${main ? `<img class="preview-avatar" src="${main.previewUrl}" alt="">` : '<div class="preview-avatar"></div>'}
        <div>
          <span class="tier-badge">${escapeHtml(comp.tier)}</span>
          <h3 class="preview-title">${escapeHtml(comp.title || '未命名阵容')}</h3>
          <p class="comp-meta">${escapeHtml(comp.jccCode || '暂无阵容码')}</p>
        </div>
      </div>
      <div class="hero-strip">${comp.heroAssetIds.map(renderAssetThumb).join('')}</div>
    `;
    elements.previewGrid.append(card);
  });
}

function buildPayload(useUploadedUrls = true) {
  const tiers = Object.fromEntries(TIER_ORDER.map((tier) => [tier, []]));
  state.comps.forEach((comp) => {
    const main = state.assets.find((asset) => asset.id === comp.mainAssetId);
    const heroes = comp.heroAssetIds.map((id) => state.assets.find((asset) => asset.id === id)).filter(Boolean);
    tiers[comp.tier].push({
      id: comp.id.trim(),
      title: comp.title.trim(),
      tier: comp.tier,
      jccCode: comp.jccCode.trim(),
      mainAvatar: useUploadedUrls ? main?.uploadedUrl || '' : main?.name || '',
      heroImages: heroes.map((asset) => useUploadedUrls ? asset.uploadedUrl || '' : asset.name),
    });
  });
  return {
    meta: { source: 'manual-live-comps-tool' },
    tiers,
  };
}

async function uploadAsset(asset) {
  if (asset.uploadedUrl) return asset.uploadedUrl;
  if (!asset.contentBase64) throw new Error(`${asset.name} 没有可上传的图片内容，请重新导入本地图片`);
  const result = await api('/api/upload-image', {
    method: 'POST',
      body: JSON.stringify({
        server: elements.server.value.trim(),
        token: elements.token.value.trim(),
        filename: asset.name,
        content_base64: asset.contentBase64,
      }),
    });
  asset.uploadedUrl = result.url;
  return asset.uploadedUrl;
}

async function uploadAll() {
  try {
    const usedAssetIds = new Set();
    state.comps.forEach((comp) => {
      if (comp.mainAssetId) usedAssetIds.add(comp.mainAssetId);
      comp.heroAssetIds.forEach((id) => usedAssetIds.add(id));
    });
    const usedAssets = state.assets.filter((asset) => usedAssetIds.has(asset.id));
    showMessage(`正在上传 ${usedAssets.length} 张图片...`);
    for (const asset of usedAssets) {
      await uploadAsset(asset);
    }
    const payload = buildPayload(true);
    elements.jsonOutput.value = JSON.stringify(payload, null, 2);
    showMessage('正在上传阵容 JSON...');
    const result = await api('/api/upload-live-comps', {
      method: 'POST',
      body: JSON.stringify({
        server: elements.server.value.trim(),
        token: elements.token.value.trim(),
        season_id: elements.season.value,
        payload,
      }),
    });
    showMessage(`上传完成：${result.total ?? 0} 套阵容`);
  } catch (error) {
    showMessage(error.message);
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
