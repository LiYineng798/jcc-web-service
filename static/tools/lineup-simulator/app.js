const DATA_ROOT = "/static/season-data";
const DATA_VERSION = document.querySelector("#simulatorRoot")?.dataset.seasonDataVersion || "0";
const UI_ROOT = "/static/tools/lineup-simulator/ui";
const STORAGE_PREFIX = "jcc-simulator-v2:";
const MAX_HISTORY = 40;
const MAX_EXPORT_TRAITS = 8;
const MAX_POSTER_TRAITS = 9;
const POSTER_WIDTH = 1200;
const POSTER_HEIGHT = 1600;
const POSTER_DEFAULT_TITLE = "我的阵容";
const POSTER_SITE_URL = "jcc.np5.top";
const ITEM_CATEGORIES = [
  { id: "normal", label: "普通", source: ["completed"] },
  { id: "component", label: "散件", source: ["component"] },
  { id: "emblem", label: "纹章", source: ["emblem"] },
  { id: "artifact", label: "神器", source: ["artifact"] },
  { id: "radiant", label: "光明", source: ["radiant"] },
  { id: "support", label: "辅助", source: ["support"] },
  { id: "consumable", label: "消耗", source: ["consumable"] },
  { id: "other", label: "其他", source: ["other"] },
];

function availableItemCategories() {
  const populated = new Set(state.items.map((item) => item.category));
  return ITEM_CATEGORIES.filter((category) => category.source.some((source) => populated.has(source)));
}
const COST_COLORS = {
  1: "rgb(175, 175, 175)",
  2: "rgb(28, 195, 152)",
  3: "rgb(7, 165, 241)",
  4: "rgb(213, 105, 230)",
  5: "rgb(255, 183, 1)",
  7: "rgb(255, 183, 1)",
};
const TRAIT_STYLE_INDEX = { bronze: 1, silver: 2, gold: 3, prismatic: 4 };
const TRAIT_STYLE_COLORS = {
  0: "#667080",
  1: "#b66e3d",
  2: "#aab3bd",
  3: "#d7a934",
  4: "#7fd2e8",
  unique: "#d7a934",
};

const elements = {
  root: document.querySelector("#simulatorRoot"),
  seasonSwitcher: document.querySelector("#seasonSwitcher"),
  seasonMeta: document.querySelector("#seasonMeta"),
  board: document.querySelector("#boardGrid"),
  unitCount: document.querySelector("#unitCount"),
  totalCost: document.querySelector("#totalCost"),
  boardStatus: document.querySelector("#boardStatus"),
  activeTraitCount: document.querySelector("#activeTraitCount"),
  traitSummary: document.querySelector("#traitSummary"),
  componentSummary: document.querySelector("#componentSummary"),
  selectedHelp: document.querySelector("#selectedHelp"),
  itemTabs: document.querySelector("#itemTabs"),
  itemSearch: document.querySelector("#itemSearch"),
  itemGrid: document.querySelector("#itemGrid"),
  heroSearch: document.querySelector("#heroSearch"),
  costFilters: document.querySelector("#costFilters"),
  traitFilterPicker: document.querySelector("#traitFilterPicker"),
  traitFilterButton: document.querySelector("#traitFilterButton"),
  traitFilterIcon: document.querySelector("#traitFilterIcon"),
  traitFilterLabel: document.querySelector("#traitFilterLabel"),
  traitFilterMenu: document.querySelector("#traitFilterMenu"),
  traitFilterClear: document.querySelector("#traitFilterClear"),
  heroGroups: document.querySelector("#heroGroups"),
  showNames: document.querySelector("#showNamesToggle"),
  undo: document.querySelector("#undoButton"),
  redo: document.querySelector("#redoButton"),
  reset: document.querySelector("#resetButton"),
  exportImage: document.querySelector("#exportImageButton"),
  exportPoster: document.querySelector("#exportPosterButton"),
  share: document.querySelector("#shareButton"),
  import: document.querySelector("#importButton"),
  export: document.querySelector("#exportButton"),
  boardCapture: document.querySelector("#boardCapture"),
  popover: document.querySelector("#detailPopover"),
  toast: document.querySelector("#toast"),
  dialog: document.querySelector("#codeDialog"),
  dialogTitle: document.querySelector("#codeDialogTitle"),
  dialogHint: document.querySelector("#codeDialogHint"),
  code: document.querySelector("#formationCode"),
  confirmCode: document.querySelector("#confirmCodeButton"),
  exportImageDialog: document.querySelector("#exportImageDialog"),
  exportIncludeTraits: document.querySelector("#exportIncludeTraits"),
  exportTransparentBackground: document.querySelector("#exportTransparentBackground"),
  confirmExportImage: document.querySelector("#confirmExportImageButton"),
  posterExportDialog: document.querySelector("#posterExportDialog"),
  posterTitle: document.querySelector("#posterTitle"),
  posterTitleCount: document.querySelector("#posterTitleCount"),
  posterChampionPicker: document.querySelector("#posterChampionPicker"),
  posterPreview: document.querySelector("#posterPreview"),
  confirmExportPoster: document.querySelector("#confirmExportPosterButton"),
};

const state = {
  catalog: [],
  season: null,
  champions: [],
  traits: [],
  items: [],
  championById: new Map(),
  traitById: new Map(),
  itemById: new Map(),
  board: Array(28).fill(null),
  selectedItemId: null,
  itemCategory: "normal",
  heroSearch: "",
  itemSearch: "",
  costFilter: "all",
  traitFilters: new Set(),
  showNames: true,
  history: [],
  historyIndex: -1,
  dragging: null,
  dialogMode: "import",
  posterChampionId: null,
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function seasonAsset(path) {
  if (!path || !state.season) return "";
  return `${DATA_ROOT}/${encodeURIComponent(state.season.season_id)}/${path}?v=${encodeURIComponent(state.season.version_id)}`;
}

function compareSeasons(a, b) {
  const statusScore = (season) => season.status === "active" ? 2 : season.status === "draft" ? 1 : 0;
  return statusScore(b) - statusScore(a)
    || String(b.effective_at || "").localeCompare(String(a.effective_at || ""))
    || String(b.game_version || "").localeCompare(String(a.game_version || ""), undefined, { numeric: true });
}

function normalizeText(value) {
  return String(value || "").trim().toLocaleLowerCase("zh-CN");
}

function normalizeChampion(raw) {
  return {
    id: String(raw.id),
    name: raw.name || "未知弈子",
    aliases: raw.aliases || [],
    cost: Number(raw.cost) || 0,
    traitIds: (raw.trait_ids || []).map(String),
    availability: raw.availability || { type: "shop", description: null, rules: [] },
    icon: seasonAsset(raw.images?.icon?.optimized_local_path || raw.images?.icon?.local_path),
    posterIcon: seasonAsset(raw.images?.icon?.local_path || raw.images?.icon?.optimized_local_path),
    splash: seasonAsset(raw.images?.splash?.local_path || raw.images?.icon?.local_path),
    skill: raw.skills?.[0] || null,
    stats: raw.stats_by_star?.["1"] || {},
  };
}

function normalizeTrait(raw) {
  return {
    id: String(raw.id),
    name: raw.name || "未知羁绊",
    category: raw.category || "other",
    description: raw.description || "",
    breakpoints: [...(raw.breakpoints || [])].sort((a, b) => Number(a.min_units) - Number(b.min_units)),
    icon: seasonAsset(raw.image?.optimized_local_path || raw.image?.local_path),
    tags: raw.tags || [],
  };
}

function normalizeItem(raw) {
  const rawGrantedTraitId = raw.category === "emblem"
    ? raw.extensions?.trait_id ?? raw.extensions?.fetter_id
    : null;
  return {
    id: String(raw.id),
    name: raw.name || "未知装备",
    category: raw.category || "other",
    description: raw.description || "",
    stats: raw.stats?.raw || "",
    effects: raw.effects || [],
    unique: Boolean(raw.unique),
    recipe: raw.recipe || { type: "none", component_ids: [] },
    grantedTraitId: rawGrantedTraitId == null || rawGrantedTraitId === "" ? null : String(rawGrantedTraitId),
    icon: seasonAsset(raw.image?.optimized_local_path || raw.image?.local_path),
  };
}

async function fetchJson(path) {
  const response = await fetch(path, {
    cache: "no-cache",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`资料加载失败 (${response.status})`);
  return response.json();
}

async function loadCatalog() {
  await refreshCatalog();
  renderSeasonSwitcher();
  const hashPayload = readHashPayload();
  const requestedId = hashPayload?.season || localStorage.getItem(`${STORAGE_PREFIX}season`);
  const initial = state.catalog.find((season) => season.season_id === requestedId)
    || state.catalog.find((season) => season.status === "active")
    || state.catalog[0];
  if (!initial) throw new Error("资料库中没有可用赛季");
  await loadSeason(initial.season_id, hashPayload);
}

async function refreshCatalog() {
  const catalog = await fetchJson(`${DATA_ROOT}/catalog.json?v=${encodeURIComponent(DATA_VERSION)}`);
  state.catalog = [...(catalog.seasons || [])].sort(compareSeasons);
}

async function loadSeason(seasonId, importedPayload = null) {
  const season = state.catalog.find((item) => item.season_id === seasonId);
  if (!season) throw new Error("赛季不存在");
  state.season = season;
  state.selectedItemId = null;
  state.traitFilters.clear();
  state.heroSearch = "";
  state.itemSearch = "";
  state.costFilter = "all";
  state.itemCategory = "normal";
  elements.heroSearch.value = "";
  elements.itemSearch.value = "";
  setLoading(true);
  try {
    const stamp = encodeURIComponent(`${season.version_id}-${DATA_VERSION}`);
    const [championData, traitData, itemData] = await Promise.all([
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/champions.json?v=${stamp}`),
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/traits.json?v=${stamp}`),
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/items.json?v=${stamp}`),
    ]);
    state.champions = (championData.champions || []).map(normalizeChampion).sort((a, b) => a.cost - b.cost || a.name.localeCompare(b.name, "zh-CN"));
    state.traits = (traitData.traits || []).map(normalizeTrait).sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name, "zh-CN"));
    state.items = (itemData.items || []).map(normalizeItem);
    const availableCategories = availableItemCategories();
    if (!availableCategories.some((category) => category.id === state.itemCategory)) {
      state.itemCategory = availableCategories[0]?.id || "normal";
    }
    state.championById = new Map(state.champions.map((item) => [item.id, item]));
    state.traitById = new Map(state.traits.map((item) => [item.id, item]));
    state.itemById = new Map(state.items.map((item) => [item.id, item]));
    const payload = importedPayload?.season === seasonId ? importedPayload : readStoredFormation(seasonId);
    state.board = hydrateBoard(payload?.board);
    state.showNames = payload?.showNames !== false;
    elements.showNames.checked = state.showNames;
    state.history = [];
    state.historyIndex = -1;
    pushHistory();
    localStorage.setItem(`${STORAGE_PREFIX}season`, seasonId);
    renderAll();
  } finally {
    setLoading(false);
  }
}

function hydrateBoard(rawBoard) {
  const board = Array(28).fill(null);
  if (!Array.isArray(rawBoard)) return board;
  rawBoard.slice(0, 28).forEach((slot, index) => {
    if (!slot || !state.championById.has(String(slot.championId))) return;
    board[index] = {
      championId: String(slot.championId),
      items: (slot.items || []).map(String).filter((id) => state.itemById.has(id)).slice(0, 3),
    };
  });
  return board;
}

function setLoading(isLoading) {
  elements.root.toggleAttribute("aria-busy", isLoading);
  if (isLoading) elements.seasonMeta.textContent = "正在加载赛季资料...";
}

function renderAll() {
  renderSeasonSwitcher();
  renderFilters();
  renderHeroes();
  renderItems();
  renderBoard();
  persist();
  window.lucide?.createIcons();
}

function renderSeasonSwitcher() {
  elements.seasonSwitcher.innerHTML = state.catalog.map((season) => `
    <button class="season-button ${season.season_id === state.season?.season_id ? "is-active" : ""}" type="button" data-season-id="${escapeHtml(season.season_id)}">
      ${escapeHtml(season.set_variant ? `S${season.set_number}${season.set_variant}` : `S${season.set_number}`)}
      ${season.status === "draft" ? "<small>预览</small>" : ""}
    </button>`).join("");
  if (state.season) {
    elements.seasonMeta.textContent = `${state.season.display_name} · ${state.season.game_version} · ${state.champions.length} 名弈子`;
  }
}

function renderFilters() {
  const costs = [...new Set(state.champions.map((hero) => hero.cost))].sort((a, b) => a - b);
  elements.costFilters.innerHTML = ["all", ...costs].map((cost) => {
    const active = String(state.costFilter) === String(cost);
    const color = cost === "all" ? "var(--accent)" : costColor(cost);
    return `<button class="cost-filter ${active ? "is-active" : ""}" type="button" data-cost="${cost}" style="--filter-color:${color}">${cost === "all" ? "全部" : `${cost}费`}</button>`;
  }).join("");
  const selectedTraitId = [...state.traitFilters][0] || "all";
  const championCountByTrait = new Map();
  state.champions.forEach((hero) => hero.traitIds.forEach((traitId) => {
    championCountByTrait.set(traitId, (championCountByTrait.get(traitId) || 0) + 1);
  }));
  const selectedTrait = state.traitById.get(selectedTraitId) || null;
  elements.traitFilterIcon.innerHTML = selectedTrait?.icon
    ? `<img src="${escapeHtml(selectedTrait.icon)}" alt="" />`
    : '<i data-lucide="shapes"></i>';
  elements.traitFilterLabel.textContent = selectedTrait?.name || "全部羁绊";
  const traitGroups = [
    { id: "origin", label: "特质" },
    { id: "class", label: "职业" },
  ];
  elements.traitFilterMenu.innerHTML = `
    <button class="trait-filter-option ${selectedTraitId === "all" ? "is-selected" : ""}" type="button" role="option" aria-selected="${selectedTraitId === "all"}" data-trait-filter="all">
      <span class="trait-option-icon all-traits"><i data-lucide="shapes"></i></span>
      <span>全部羁绊</span><small>${state.traits.length}</small>
    </button>
    ${traitGroups.map((group) => {
      const options = state.traits.filter((trait) => trait.category === group.id && championCountByTrait.has(trait.id));
      return options.length ? `<div class="trait-filter-group"><span class="trait-filter-group-label">${group.label}</span>${options.map((trait) => `
        <button class="trait-filter-option ${selectedTraitId === trait.id ? "is-selected" : ""}" type="button" role="option" aria-selected="${selectedTraitId === trait.id}" data-trait-filter="${escapeHtml(trait.id)}">
          <span class="trait-option-icon">${trait.icon ? `<img src="${escapeHtml(trait.icon)}" alt="" />` : ""}</span>
          <span>${escapeHtml(trait.name)}</span><small>${championCountByTrait.get(trait.id)}</small>
        </button>`).join("")}</div>` : "";
    }).join("")}`;
  const filteringByTrait = selectedTraitId !== "all";
  elements.traitFilterClear.hidden = !filteringByTrait;
  elements.traitFilterPicker.classList.toggle("is-filtering", filteringByTrait);
  elements.itemTabs.innerHTML = availableItemCategories().map((category) => `
    <button class="item-tab ${state.itemCategory === category.id ? "is-active" : ""}" type="button" role="tab" aria-selected="${state.itemCategory === category.id}" data-item-category="${category.id}">${category.label}</button>
  `).join("");
  window.lucide?.createIcons();
}

function renderHeroes() {
  const query = normalizeText(state.heroSearch);
  const costs = [...new Set(state.champions.map((hero) => hero.cost))].sort((a, b) => a - b);
  const groups = costs.map((cost) => {
    if (state.costFilter !== "all" && Number(state.costFilter) !== cost) return "";
    const heroes = state.champions.filter((hero) => hero.cost === cost && (!query || normalizeText([hero.name, ...hero.aliases].join(" ")).includes(query)));
    if (!heroes.length) return "";
    return `<section class="hero-cost-group" aria-label="${cost}费弈子">
      <div class="cost-heading" style="--cost-color:${costColor(cost)}"><span class="cost-dot"></span><span><strong>${cost}</strong>费用</span></div>
      <div class="hero-grid">${heroes.map(heroButtonHtml).join("")}</div>
    </section>`;
  }).join("");
  elements.heroGroups.innerHTML = groups || '<div class="empty-state">没有符合条件的弈子</div>';
}

function heroButtonHtml(hero) {
  const traitMismatch = state.traitFilters.size > 0 && ![...state.traitFilters].every((id) => hero.traitIds.includes(id));
  const unlocked = hero.availability?.type === "unlock";
  return `<button class="hero-button ${traitMismatch ? "is-dimmed" : ""}" type="button" draggable="true" data-hero-id="${escapeHtml(hero.id)}" style="--hero-color:${costColor(hero.cost)}" aria-label="上阵 ${escapeHtml(hero.name)}"${traitMismatch ? ' title="不属于当前筛选羁绊"' : ""}>
    <img src="${escapeHtml(hero.icon)}" alt="" loading="lazy" decoding="async" />
    <span>${escapeHtml(hero.name)}</span>
    ${unlocked ? `<img class="hero-unlock" src="${UI_ROOT}/unlock.png" alt="解锁弈子" />` : ""}
  </button>`;
}

function renderItems() {
  const categories = availableItemCategories();
  const category = categories.find((item) => item.id === state.itemCategory) || categories[0];
  const query = normalizeText(state.itemSearch);
  const items = category
    ? state.items.filter((item) => category.source.includes(item.category) && (!query || normalizeText(item.name).includes(query)))
    : [];
  elements.itemGrid.innerHTML = items.length ? items.map((item) => `
    <button class="item-button ${state.selectedItemId === item.id ? "is-selected" : ""}" type="button" draggable="true" data-item-id="${escapeHtml(item.id)}" aria-label="选择 ${escapeHtml(item.name)}">
      <img src="${escapeHtml(item.icon)}" alt="" loading="lazy" decoding="async" />
    </button>`).join("") : '<div class="empty-state">该分类暂无装备</div>';
  updateSelectedItemStatus();
}

function renderBoard() {
  elements.board.classList.toggle("hide-names", !state.showNames);
  elements.board.innerHTML = state.board.map((slot, index) => boardSlotHtml(slot, index)).join("");
  const units = state.board.filter(Boolean);
  elements.unitCount.textContent = String(units.length);
  elements.totalCost.textContent = String(units.reduce((total, slot) => total + (state.championById.get(slot.championId)?.cost || 0), 0));
  elements.boardStatus.textContent = units.length ? `${units.length} 名弈子已上阵` : "阵容未配置";
  renderTraitSummary();
  renderComponentSummary();
  elements.undo.disabled = state.historyIndex <= 0;
  elements.redo.disabled = state.historyIndex >= state.history.length - 1;
  elements.exportPoster.disabled = units.length === 0;
}

function boardSlotHtml(slot, index) {
  if (!slot) return `<button class="hex-cell" type="button" role="gridcell" data-slot-index="${index}" aria-label="空棋格 ${index + 1}"><span class="hex-floor"></span></button>`;
  const hero = state.championById.get(slot.championId);
  if (!hero) return `<button class="hex-cell" type="button" role="gridcell" data-slot-index="${index}"><span class="hex-floor"></span></button>`;
  const items = slot.items.map((itemId, itemIndex) => {
    const item = state.itemById.get(itemId);
    return item ? `<span class="unit-item" data-item-id="${escapeHtml(item.id)}" data-slot-index="${index}" data-item-index="${itemIndex}"><img src="${escapeHtml(item.icon)}" alt="${escapeHtml(item.name)}" /></span>` : "";
  }).join("");
  return `<button class="hex-cell has-unit ${items ? "has-items" : ""}" type="button" role="gridcell" draggable="true" data-slot-index="${index}" data-hero-id="${escapeHtml(hero.id)}" aria-label="${escapeHtml(hero.name)}">
    <span class="hex-floor"></span>
    <span class="unit-portrait" style="--unit-color:${costColor(hero.cost)}"><img class="unit-portrait-image" src="${escapeHtml(hero.icon)}" alt="" /></span>
    <span class="unit-items">${items}</span>
    <span class="unit-name">${escapeHtml(hero.name)}</span>
    ${hero.availability?.type === "unlock" ? `<span class="unlock-mark" title="解锁弈子"><img src="${UI_ROOT}/unlock.png" alt="" /></span>` : ""}
  </button>`;
}

function getTraitCounts() {
  const contributors = new Map();
  state.board.filter(Boolean).forEach((slot) => {
    const hero = state.championById.get(slot.championId);
    hero?.traitIds.forEach((traitId) => {
      if (!contributors.has(traitId)) contributors.set(traitId, new Set());
      contributors.get(traitId).add(hero.id);
    });
    slot.items.forEach((itemId) => {
      const traitId = state.itemById.get(itemId)?.grantedTraitId;
      if (!traitId || !state.traitById.has(traitId)) return;
      if (!contributors.has(traitId)) contributors.set(traitId, new Set());
      contributors.get(traitId).add(hero.id);
    });
  });
  return new Map([...contributors].map(([traitId, heroIds]) => [traitId, heroIds.size]));
}

function traitState(trait, count) {
  const active = trait.breakpoints.filter((point) => count >= Number(point.min_units)).at(-1) || null;
  const next = trait.breakpoints.find((point) => count < Number(point.min_units)) || null;
  const unique = active?.style === "unique"
    || trait.category === "unique"
    || trait.tags.some((tag) => normalizeText(tag).includes("unique") || String(tag).includes("独特"));
  const styleIndex = active && unique ? "unique" : active ? (TRAIT_STYLE_INDEX[active.style] || Math.min(4, trait.breakpoints.indexOf(active) + 1)) : 0;
  return { active, next, unique, styleIndex };
}

function traitTierRank(status) {
  if (!status?.active) return 0;
  if (status.styleIndex === "unique") return 5;
  return Number(status.styleIndex) || 1;
}

function compareTraitRows(a, b) {
  return traitTierRank(b.status) - traitTierRank(a.status)
    || b.count - a.count
    || a.trait.name.localeCompare(b.trait.name, "zh-CN");
}

function renderTraitSummary() {
  const counts = getTraitCounts();
  const rows = [...counts].map(([traitId, count]) => {
    const trait = state.traitById.get(traitId);
    return trait ? { trait, count, status: traitState(trait, count) } : null;
  }).filter(Boolean).sort(compareTraitRows);
  elements.activeTraitCount.textContent = String(rows.filter((row) => row.status.active).length);
  elements.traitSummary.innerHTML = rows.length ? rows.map(({ trait, count, status }) => {
    const breakpointText = trait.breakpoints.length
      ? trait.breakpoints.map((breakpoint) => breakpoint.min_units).join(" > ")
      : "独特";
    const background = status.styleIndex === "unique" ? `${UI_ROOT}/unique.svg` : `${UI_ROOT}/${status.styleIndex}.svg`;
    return `<div class="trait-row" style="--trait-color:${TRAIT_STYLE_COLORS[status.styleIndex]}" data-trait-id="${escapeHtml(trait.id)}" data-tier-rank="${traitTierRank(status)}">
      <span class="trait-badge"><img class="trait-badge-frame" src="${background}" alt="" />${trait.icon ? `<img class="trait-badge-icon" src="${escapeHtml(trait.icon)}" alt="" />` : ""}</span>
      <span class="trait-copy"><strong>${escapeHtml(trait.name)}</strong><small>${escapeHtml(breakpointText)}</small></span>
      <span class="trait-count">${count}</span>
    </div>`;
  }).join("") : '<div class="empty-state compact">添加弈子后显示羁绊</div>';
}

function renderComponentSummary() {
  const counts = new Map();
  state.board.filter(Boolean).flatMap((slot) => slot.items).forEach((itemId) => {
    const item = state.itemById.get(itemId);
    (item?.recipe?.component_ids || []).forEach((componentId) => counts.set(String(componentId), (counts.get(String(componentId)) || 0) + 1));
  });
  elements.componentSummary.innerHTML = counts.size ? [...counts].map(([itemId, count]) => {
    const item = state.itemById.get(itemId);
    return item ? `<span class="component-stack" data-item-id="${escapeHtml(item.id)}"><img src="${escapeHtml(item.icon)}" alt="${escapeHtml(item.name)}" /><b>${count}</b></span>` : "";
  }).join("") : '<span class="muted">暂无装备</span>';
}

function updateSelectedItemStatus() {
  const item = state.itemById.get(state.selectedItemId);
  elements.selectedHelp.hidden = !item;
  elements.selectedHelp.textContent = item ? `待装备：${item.name}` : "";
}

function costColor(cost) {
  return COST_COLORS[cost] || COST_COLORS[5];
}

function firstEmptySlot() {
  return state.board.findIndex((slot) => slot === null);
}

function addChampion(championId) {
  const index = firstEmptySlot();
  if (index < 0) return showToast("棋盘已满");
  mutate(() => { state.board[index] = { championId, items: [] }; });
}

function equipItem(slotIndex, itemId) {
  const slot = state.board[slotIndex];
  if (!slot) return showToast("请先在该位置上阵弈子");
  if (slot.items.length >= 3) return showToast("每名弈子最多携带 3 件装备");
  mutate(() => { slot.items.push(itemId); });
}

function moveUnit(fromIndex, toIndex) {
  if (fromIndex === toIndex) return;
  mutate(() => {
    const target = state.board[toIndex];
    state.board[toIndex] = state.board[fromIndex];
    state.board[fromIndex] = target;
  });
}

function mutate(callback) {
  callback();
  pushHistory();
  renderBoard();
  persist();
}

function snapshot() {
  return JSON.stringify({ board: state.board, showNames: state.showNames });
}

function pushHistory() {
  const next = snapshot();
  if (state.history[state.historyIndex] === next) return;
  state.history = state.history.slice(0, state.historyIndex + 1);
  state.history.push(next);
  if (state.history.length > MAX_HISTORY) state.history.shift();
  state.historyIndex = state.history.length - 1;
}

function applyHistory(index) {
  if (index < 0 || index >= state.history.length) return;
  state.historyIndex = index;
  const value = JSON.parse(state.history[index]);
  state.board = hydrateBoard(value.board);
  state.showNames = value.showNames !== false;
  elements.showNames.checked = state.showNames;
  renderBoard();
  persist();
}

function formationPayload() {
  return { version: 2, season: state.season.season_id, showNames: state.showNames, board: state.board };
}

function persist() {
  if (!state.season) return;
  localStorage.setItem(`${STORAGE_PREFIX}${state.season.season_id}`, JSON.stringify(formationPayload()));
}

function readStoredFormation(seasonId) {
  try { return JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}${seasonId}`) || "null"); }
  catch { return null; }
}

function encodePayload(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function decodePayload(code) {
  const normalized = code.trim().replace(/^.*#lineup=/, "").replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

function readHashPayload() {
  const match = location.hash.match(/^#lineup=(.+)$/);
  if (!match) return null;
  try { return decodePayload(match[1]); }
  catch { return null; }
}

function openCodeDialog(mode) {
  state.dialogMode = mode;
  elements.dialogTitle.textContent = mode === "import" ? "导入阵容" : "导出阵容";
  elements.dialogHint.textContent = mode === "import" ? "粘贴阵容码" : "当前阵容码";
  elements.code.value = mode === "import" ? "" : encodePayload(formationPayload());
  elements.code.readOnly = mode === "export";
  elements.confirmCode.textContent = mode === "import" ? "确认导入" : "复制阵容码";
  elements.dialog.showModal();
  elements.code.focus();
  if (mode === "export") elements.code.select();
}

async function handleCodeConfirm() {
  if (state.dialogMode === "export") {
    await copyText(elements.code.value);
    elements.dialog.close();
    return showToast("阵容码已复制");
  }
  try {
    const payload = decodePayload(elements.code.value);
    if (!payload.season || !Array.isArray(payload.board)) throw new Error();
    if (payload.season !== state.season.season_id) await loadSeason(payload.season, payload);
    else {
      state.board = hydrateBoard(payload.board);
      state.showNames = payload.showNames !== false;
      elements.showNames.checked = state.showNames;
      pushHistory();
      renderBoard();
      persist();
    }
    elements.dialog.close();
    showToast("阵容已导入");
  } catch {
    showToast("阵容码无效或版本不受支持");
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  const area = document.createElement("textarea");
  area.value = text;
  document.body.append(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

async function shareFormation() {
  const url = `${location.origin}${location.pathname}#lineup=${encodePayload(formationPayload())}`;
  await copyText(url);
  history.replaceState(null, "", url);
  showToast("阵容链接已复制");
}

function buildImageCapture(includeTraits, transparentBackground) {
  const capture = document.createElement("div");
  capture.className = `lineup-image-capture ${includeTraits ? "with-traits" : "board-only"}`;
  capture.classList.toggle("is-transparent", transparentBackground);
  if (includeTraits) {
    const traitPanel = document.createElement("aside");
    traitPanel.className = "lineup-image-traits";
    traitPanel.innerHTML = `<div class="lineup-image-trait-title"><span>SYNERGIES</span><strong>阵容羁绊</strong></div>`;
    const traitSummary = elements.traitSummary.cloneNode(true);
    traitSummary.querySelectorAll(".trait-row").forEach((row, index) => {
      if (index >= MAX_EXPORT_TRAITS) row.remove();
    });
    traitPanel.append(traitSummary);
    capture.append(traitPanel);
  }
  const boardPanel = document.createElement("section");
  boardPanel.className = "lineup-image-board";
  boardPanel.append(elements.board.cloneNode(true));
  capture.append(boardPanel);
  document.body.append(capture);
  return capture;
}

async function exportBoardImage(includeTraits = true, transparentBackground = false) {
  if (!window.htmlToImage?.toPng || !elements.boardCapture) throw new Error("图片导出组件未加载");
  elements.exportImage.disabled = true;
  elements.confirmExportImage.disabled = true;
  showToast("正在生成阵容图...");
  const capture = buildImageCapture(includeTraits, transparentBackground);
  try {
    await document.fonts?.ready;
    const dataUrl = await window.htmlToImage.toPng(capture, {
      backgroundColor: transparentBackground ? "transparent" : "#0d101a",
      cacheBust: true,
      pixelRatio: 2,
      style: { position: "static", left: "auto", top: "auto", zIndex: "auto" },
    });
    const link = document.createElement("a");
    link.download = `${state.season.season_id}-lineup.png`;
    link.href = dataUrl;
    link.click();
    elements.exportImageDialog.close();
    showToast("阵容图已保存");
  } finally {
    capture.remove();
    elements.exportImage.disabled = false;
    elements.confirmExportImage.disabled = false;
  }
}

function posterChampionCandidates() {
  const seen = new Set();
  return state.board.flatMap((slot, index) => {
    if (!slot || seen.has(slot.championId)) return [];
    const hero = state.championById.get(slot.championId);
    if (!hero) return [];
    seen.add(slot.championId);
    return [{ hero, index }];
  });
}

function defaultPosterChampionId() {
  return posterChampionCandidates()
    .sort((a, b) => b.hero.cost - a.hero.cost || a.index - b.index)[0]?.hero.id || null;
}

function normalizedPosterTitle() {
  return String(elements.posterTitle.value || "").trim().slice(0, 24) || POSTER_DEFAULT_TITLE;
}

function posterTitleClass(title) {
  if (title.length > 16) return "is-very-long";
  if (title.length > 12) return "is-long";
  return "";
}

function posterTraitRows() {
  return [...getTraitCounts()].map(([traitId, count]) => {
    const trait = state.traitById.get(traitId);
    if (!trait) return null;
    const status = traitState(trait, count);
    return status.active ? { trait, count, status } : null;
  }).filter(Boolean).sort(compareTraitRows);
}

function posterTraitHtml() {
  const rows = posterTraitRows();
  if (!rows.length) return '<div class="lineup-poster-traits-empty">未激活羁绊</div>';
  const visible = rows.slice(0, MAX_POSTER_TRAITS);
  const overflow = rows.length - visible.length;
  return `${visible.map(({ trait, count, status }) => {
    const frame = status.styleIndex === "unique" ? `${UI_ROOT}/unique.svg` : `${UI_ROOT}/${status.styleIndex}.svg`;
    return `<div class="lineup-poster-trait" style="--trait-color:${TRAIT_STYLE_COLORS[status.styleIndex]}">
      <span class="lineup-poster-trait-badge"><img src="${frame}" alt="" />${trait.icon ? `<img class="lineup-poster-trait-icon" src="${escapeHtml(trait.icon)}" alt="" />` : ""}</span>
      <span class="lineup-poster-trait-count">${count}</span>
      <strong>${escapeHtml(trait.name)}</strong>
    </div>`;
  }).join("")}${overflow > 0 ? `<div class="lineup-poster-trait lineup-poster-trait-more"><b>+${overflow}</b><strong>个羁绊</strong></div>` : ""}`;
}

function posterBoardClone() {
  const board = elements.board.cloneNode(true);
  board.removeAttribute("id");
  board.classList.remove("hide-names");
  board.classList.add("lineup-poster-hex-board");
  board.querySelectorAll(".hex-cell").forEach((cell) => {
    cell.removeAttribute("draggable");
    cell.setAttribute("type", "button");
    cell.setAttribute("tabindex", "-1");
    cell.removeAttribute("role");
    cell.removeAttribute("aria-label");
    const hero = state.championById.get(cell.dataset.heroId);
    const portrait = cell.querySelector(".unit-portrait-image");
    if (hero && portrait) {
      portrait.dataset.fallbackSrc = hero.icon;
      portrait.src = hero.posterIcon || hero.icon;
    }
  });
  return board;
}

function buildPosterCapture(title, championId) {
  const hero = state.championById.get(championId) || state.championById.get(defaultPosterChampionId());
  const units = state.board.filter(Boolean);
  const totalCost = units.reduce((total, slot) => total + (state.championById.get(slot.championId)?.cost || 0), 0);
  const poster = document.createElement("section");
  poster.className = "lineup-poster-capture";
  poster.style.setProperty("--poster-width", `${POSTER_WIDTH}px`);
  poster.style.setProperty("--poster-height", `${POSTER_HEIGHT}px`);
  poster.innerHTML = `
    <div class="lineup-poster-background">
      ${hero?.splash ? `<img class="lineup-poster-background-image" src="${escapeHtml(hero.splash)}" alt="" data-fallback-src="${escapeHtml(hero.icon)}" />` : ""}
    </div>
    <div class="lineup-poster-overlay"></div>
    <header class="lineup-poster-header">
      <div class="lineup-poster-season"><span>${escapeHtml(state.season.display_name)}</span><b>${escapeHtml(state.season.game_version || "")}</b></div>
      <h1 class="${posterTitleClass(title)}">${escapeHtml(title)}</h1>
      <div class="lineup-poster-summary"><span>${units.length} 名弈子</span><i></i><span>总费用 ${totalCost}</span><i></i><span>${posterTraitRows().length} 个激活羁绊</span></div>
    </header>
    <div class="lineup-poster-board-panel"><div class="lineup-poster-board-slot"></div></div>
    <section class="lineup-poster-traits-panel">
      <div class="lineup-poster-section-title"><span>SYNERGIES</span><strong>阵容羁绊</strong></div>
      <div class="lineup-poster-traits">${posterTraitHtml()}</div>
    </section>
    <footer class="lineup-poster-footer">
      <div class="lineup-poster-footer-line"></div>
      <div class="lineup-poster-brand"><img src="/static/favicon.png" alt="" /><span><strong>金铲铲阵容库</strong><small>${POSTER_SITE_URL}</small></span></div>
    </footer>`;
  poster.querySelector(".lineup-poster-board-slot").append(posterBoardClone());
  return poster;
}

function fitPosterPreview() {
  const poster = elements.posterPreview.querySelector(".lineup-poster-capture");
  if (!poster) return;
  const scale = elements.posterPreview.clientWidth / POSTER_WIDTH;
  poster.style.transform = `scale(${scale})`;
  elements.posterPreview.style.height = `${POSTER_HEIGHT * scale}px`;
}

function renderPosterPreview() {
  const title = normalizedPosterTitle();
  elements.posterTitleCount.textContent = String(elements.posterTitle.value.length);
  elements.posterPreview.replaceChildren(buildPosterCapture(title, state.posterChampionId));
  requestAnimationFrame(fitPosterPreview);
}

function renderPosterChampionPicker() {
  const candidates = posterChampionCandidates();
  if (!candidates.some(({ hero }) => hero.id === state.posterChampionId)) {
    state.posterChampionId = defaultPosterChampionId();
  }
  elements.posterChampionPicker.innerHTML = candidates.map(({ hero }) => `
    <button class="poster-champion-option ${hero.id === state.posterChampionId ? "is-selected" : ""}" type="button" data-poster-champion-id="${escapeHtml(hero.id)}" title="${escapeHtml(hero.name)}">
      <img src="${escapeHtml(hero.icon)}" alt="" /><span>${escapeHtml(hero.name)}</span>
    </button>`).join("");
}

function openPosterDialog() {
  if (!state.board.some(Boolean)) return showToast("请先配置阵容");
  state.posterChampionId = defaultPosterChampionId();
  elements.posterTitle.value = POSTER_DEFAULT_TITLE;
  renderPosterChampionPicker();
  renderPosterPreview();
  elements.posterExportDialog.showModal();
  requestAnimationFrame(fitPosterPreview);
}

async function preparePosterImages(poster) {
  await Promise.all([...poster.querySelectorAll("img")].map(async (image) => {
    try {
      if (!image.complete) await new Promise((resolve, reject) => {
        image.addEventListener("load", resolve, { once: true });
        image.addEventListener("error", reject, { once: true });
      });
      await image.decode?.();
    } catch {
      const fallback = image.dataset.fallbackSrc;
      if (fallback && image.src !== new URL(fallback, location.href).href) {
        image.src = fallback;
        try { await image.decode?.(); } catch { image.hidden = true; }
      } else {
        image.hidden = true;
      }
    }
  }));
}

function safePosterFilename(value) {
  return String(value || POSTER_DEFAULT_TITLE).replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-").slice(0, 40);
}

function posterTitleLines(context, title, maxWidth) {
  const lines = [""];
  [...title].forEach((character) => {
    const index = lines.length - 1;
    const candidate = lines[index] + character;
    if (lines[index] && context.measureText(candidate).width > maxWidth && lines.length < 2) lines.push(character);
    else lines[index] = candidate;
  });
  return lines;
}

async function rasterizePosterTitle(poster) {
  const heading = poster.querySelector(".lineup-poster-header h1");
  if (!heading) return;
  const title = heading.textContent || POSTER_DEFAULT_TITLE;
  const fontSize = heading.classList.contains("is-very-long") ? 55 : heading.classList.contains("is-long") ? 68 : 82;
  await document.fonts?.load(`${fontSize}px "Source Han Serif SC Poster"`, title);
  const canvas = document.createElement("canvas");
  canvas.width = 1020;
  canvas.height = 150;
  const context = canvas.getContext("2d");
  context.font = `850 ${fontSize}px "Source Han Serif SC Poster", "Noto Serif SC", serif`;
  context.fillStyle = "#f6e3ad";
  context.textBaseline = "top";
  context.shadowColor = "rgba(0, 0, 0, .68)";
  context.shadowBlur = 20;
  context.shadowOffsetY = 5;
  const lineHeight = fontSize * 1.12;
  posterTitleLines(context, title, 1000).forEach((line, index) => context.fillText(line, 0, index * lineHeight, 1000));
  const image = document.createElement("img");
  image.className = "lineup-poster-title-image";
  image.src = canvas.toDataURL("image/png");
  image.alt = title;
  heading.replaceWith(image);
}

async function exportPortraitPoster() {
  if (!window.htmlToImage?.toPng) throw new Error("图片导出组件未加载");
  const title = normalizedPosterTitle();
  const poster = buildPosterCapture(title, state.posterChampionId);
  poster.classList.add("is-exporting");
  document.body.append(poster);
  elements.exportPoster.disabled = true;
  elements.confirmExportPoster.disabled = true;
  showToast("正在生成 3:4 阵容海报...");
  try {
    await document.fonts?.ready;
    await rasterizePosterTitle(poster);
    await preparePosterImages(poster);
    const dataUrl = await window.htmlToImage.toPng(poster, {
      backgroundColor: "#0b0d12",
      cacheBust: true,
      pixelRatio: 1,
      skipFonts: true,
      width: POSTER_WIDTH,
      height: POSTER_HEIGHT,
      style: { position: "static", left: "auto", top: "auto", zIndex: "auto", transform: "none" },
    });
    const link = document.createElement("a");
    link.download = `${state.season.season_id}-${safePosterFilename(title)}-poster.png`;
    link.href = dataUrl;
    link.click();
    elements.posterExportDialog.close();
    showToast("3:4 阵容海报已保存");
  } finally {
    poster.remove();
    elements.exportPoster.disabled = !state.board.some(Boolean);
    elements.confirmExportPoster.disabled = false;
  }
}

function showHeroPopover(heroId, anchor) {
  const hero = state.championById.get(heroId);
  if (!hero) return;
  const skill = hero.skill;
  const traits = hero.traitIds.map((id) => state.traitById.get(id)).filter(Boolean);
  const stats = hero.stats || {};
  elements.popover.innerHTML = `
    <div class="hero-detail-cover" style="--splash:url(&quot;${escapeHtml(hero.splash)}&quot;)">
      <h3>${escapeHtml(hero.name)}</h3>
      <div class="hero-detail-traits">${traits.map((trait) => `<span>${trait.icon ? `<img src="${escapeHtml(trait.icon)}" alt="" />` : ""}${escapeHtml(trait.name)}</span>`).join("")}</div>
      <span class="hero-detail-cost"><img src="${UI_ROOT}/gold.png" alt="" />${hero.cost}</span>
    </div>
    <div class="hero-detail-body">
      ${skill ? `<div class="skill-heading">${skill.image?.optimized_local_path || skill.image?.local_path ? `<img src="${escapeHtml(seasonAsset(skill.image.optimized_local_path || skill.image.local_path))}" alt="" />` : "<span></span>"}<strong>${escapeHtml(skill.name)}</strong><span class="mana">${stats.initial_mana ?? 0} / ${stats.max_mana ?? 0}</span></div>
      <p class="skill-description">${escapeHtml(skill.description)}</p>
      <div class="skill-values">${(skill.variables || []).map((variable) => `<div class="skill-value"><span>${escapeHtml(variable.label)}</span><span>${escapeHtml(Object.values(variable.values || {}).join(" / "))}</span></div>`).join("")}</div>` : '<p class="skill-description">暂无技能资料</p>'}
      ${hero.availability?.type === "unlock" ? `<div class="unlock-box"><img src="${UI_ROOT}/unlock.png" alt="" /><div><strong>解锁条件</strong><p>${escapeHtml(hero.availability.description || "满足赛季解锁条件")}</p></div></div>` : ""}
    </div>`;
  showPopover(anchor);
}

function showItemPopover(itemId, anchor) {
  const item = state.itemById.get(itemId);
  if (!item) return;
  const components = (item.recipe?.component_ids || []).map((id) => state.itemById.get(String(id))).filter(Boolean);
  const effects = item.effects.map((effect) => typeof effect === "string" ? effect : effect.description || effect.text || "").filter(Boolean);
  elements.popover.innerHTML = `<div class="item-detail">
    <div class="item-detail-heading"><img src="${escapeHtml(item.icon)}" alt="" /><div><h3>${escapeHtml(item.name)}</h3>${components.length ? `<div class="item-recipe">${components.map((component, index) => `${index ? "<b>+</b>" : ""}<img src="${escapeHtml(component.icon)}" alt="${escapeHtml(component.name)}" />`).join("")}</div>` : ""}</div></div>
    ${item.stats ? `<p class="item-stats">${escapeHtml(item.stats)}</p>` : ""}
    <p class="item-description">${escapeHtml([item.description, ...effects].filter(Boolean).join("\n")) || "暂无装备说明"}</p>
  </div>`;
  showPopover(anchor);
}

function showTraitPopover(traitId, anchor) {
  const trait = state.traitById.get(traitId);
  if (!trait) return;
  const count = getTraitCounts().get(traitId) || 0;
  const status = traitState(trait, count);
  const breakpoints = trait.breakpoints || [];
  elements.popover.innerHTML = `<div class="trait-detail">
    <div class="trait-detail-heading">
      ${trait.icon ? `<img src="${escapeHtml(trait.icon)}" alt="" />` : ""}
      <div><span class="trait-detail-kicker">羁绊详情</span><h3>${escapeHtml(trait.name)}</h3></div>
      <strong class="trait-detail-count">${count}</strong>
    </div>
    ${trait.description ? `<p class="trait-detail-description">${escapeHtml(trait.description)}</p>` : ""}
    <div class="trait-detail-tiers">${breakpoints.length ? breakpoints.map((point) => {
      const active = Number(point.min_units) <= count;
      return `<div class="trait-detail-tier ${active ? "is-active" : ""}">
        <strong>${escapeHtml(point.min_units)} 人</strong><span>${escapeHtml(point.effect || point.description || "")}</span>
      </div>`;
    }).join("") : `<p class="muted">独特羁绊 · ${status.active ? "已激活" : "未激活"}</p>`}</div>
  </div>`;
  showPopover(anchor);
}

function showPopover(anchor) {
  elements.popover.hidden = false;
  const rect = anchor.getBoundingClientRect();
  const popoverRect = elements.popover.getBoundingClientRect();
  let left = rect.right + 10;
  if (left + popoverRect.width > innerWidth - 10) left = rect.left - popoverRect.width - 10;
  left = Math.max(10, Math.min(left, innerWidth - popoverRect.width - 10));
  let top = rect.top;
  if (top + popoverRect.height > innerHeight - 10) top = innerHeight - popoverRect.height - 10;
  elements.popover.style.left = `${Math.max(10, left)}px`;
  elements.popover.style.top = `${Math.max(10, top)}px`;
}

function hidePopover() { elements.popover.hidden = true; }

let toastTimer;
function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  toastTimer = setTimeout(() => elements.toast.classList.remove("is-visible"), 1800);
}

elements.seasonSwitcher.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-season-id]");
  if (!button || button.dataset.seasonId === state.season?.season_id) return;
  try {
    const seasonId = button.dataset.seasonId;
    await refreshCatalog();
    await loadSeason(seasonId);
  }
  catch (error) { showToast(error.message); }
});

elements.costFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-cost]");
  if (!button) return;
  state.costFilter = button.dataset.cost;
  renderFilters();
  renderHeroes();
});

function setTraitFilterMenu(open) {
  elements.traitFilterMenu.hidden = !open;
  elements.traitFilterButton.setAttribute("aria-expanded", String(open));
  elements.traitFilterPicker.classList.toggle("is-open", open);
}

elements.traitFilterButton.addEventListener("click", () => {
  setTraitFilterMenu(elements.traitFilterMenu.hidden);
});

elements.traitFilterMenu.addEventListener("click", (event) => {
  const option = event.target.closest("[data-trait-filter]");
  if (!option) return;
  state.traitFilters.clear();
  if (option.dataset.traitFilter !== "all") state.traitFilters.add(option.dataset.traitFilter);
  setTraitFilterMenu(false);
  renderFilters();
  renderHeroes();
  elements.traitFilterButton.focus();
});

elements.traitFilterClear.addEventListener("click", () => {
  state.traitFilters.clear();
  setTraitFilterMenu(false);
  renderFilters();
  renderHeroes();
  elements.traitFilterButton.focus();
});

document.addEventListener("pointerdown", (event) => {
  if (!elements.traitFilterPicker.contains(event.target)) setTraitFilterMenu(false);
});

elements.itemTabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-item-category]");
  if (!button) return;
  state.itemCategory = button.dataset.itemCategory;
  renderFilters();
  renderItems();
});

elements.heroSearch.addEventListener("input", () => { state.heroSearch = elements.heroSearch.value; renderHeroes(); });
elements.itemSearch.addEventListener("input", () => { state.itemSearch = elements.itemSearch.value; renderItems(); });
elements.heroGroups.addEventListener("click", (event) => { const button = event.target.closest("[data-hero-id]"); if (button) addChampion(button.dataset.heroId); });
elements.itemGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-item-id]");
  if (!button) return;
  state.selectedItemId = state.selectedItemId === button.dataset.itemId ? null : button.dataset.itemId;
  renderItems();
});

elements.board.addEventListener("click", (event) => {
  const itemChip = event.target.closest(".unit-item");
  if (itemChip) return;
  const cell = event.target.closest("[data-slot-index]");
  if (!cell || !state.selectedItemId) return;
  equipItem(Number(cell.dataset.slotIndex), state.selectedItemId);
});

elements.board.addEventListener("contextmenu", (event) => {
  const itemChip = event.target.closest(".unit-item");
  if (itemChip) {
    event.preventDefault();
    hidePopover();
    mutate(() => { state.board[Number(itemChip.dataset.slotIndex)].items.splice(Number(itemChip.dataset.itemIndex), 1); });
    return;
  }
  const cell = event.target.closest(".has-unit");
  if (!cell) return;
  event.preventDefault();
  hidePopover();
  mutate(() => { state.board[Number(cell.dataset.slotIndex)] = null; });
});

document.addEventListener("dragstart", (event) => {
  const hero = event.target.closest(".hero-button");
  const item = event.target.closest(".item-button");
  const unit = event.target.closest(".hex-cell.has-unit");
  if (hero) state.dragging = { type: "hero", id: hero.dataset.heroId };
  else if (item) state.dragging = { type: "item", id: item.dataset.itemId };
  else if (unit) state.dragging = { type: "unit", index: Number(unit.dataset.slotIndex) };
  if (state.dragging) event.dataTransfer?.setData("text/plain", JSON.stringify(state.dragging));
});
document.addEventListener("dragend", () => { state.dragging = null; document.querySelectorAll(".is-drop-target").forEach((node) => node.classList.remove("is-drop-target")); });
elements.board.addEventListener("dragover", (event) => { const cell = event.target.closest(".hex-cell"); if (cell) { event.preventDefault(); cell.classList.add("is-drop-target"); } });
elements.board.addEventListener("dragleave", (event) => { event.target.closest(".hex-cell")?.classList.remove("is-drop-target"); });
elements.board.addEventListener("drop", (event) => {
  const cell = event.target.closest(".hex-cell");
  if (!cell || !state.dragging) return;
  event.preventDefault();
  cell.classList.remove("is-drop-target");
  const target = Number(cell.dataset.slotIndex);
  if (state.dragging.type === "hero") {
    if (state.board[target]) return showToast("该棋格已有弈子");
    mutate(() => { state.board[target] = { championId: state.dragging.id, items: [] }; });
  } else if (state.dragging.type === "item") equipItem(target, state.dragging.id);
  else if (state.dragging.type === "unit") moveUnit(state.dragging.index, target);
});

document.addEventListener("pointerover", (event) => {
  const hero = event.target.closest("[data-hero-id]");
  const item = event.target.closest("[data-item-id]");
  const trait = event.target.closest("[data-trait-id]");
  if (item) showItemPopover(item.dataset.itemId, item);
  else if (hero) showHeroPopover(hero.dataset.heroId, hero);
  else if (trait) showTraitPopover(trait.dataset.traitId, trait);
});
document.addEventListener("pointerout", (event) => {
  if (!event.target.closest("[data-hero-id], [data-item-id], [data-trait-id]")) return;
  const related = event.relatedTarget;
  if (related instanceof Element && related.closest("[data-hero-id], [data-item-id], [data-trait-id]") === event.target.closest("[data-hero-id], [data-item-id], [data-trait-id]")) return;
  hidePopover();
});

elements.showNames.addEventListener("change", () => {
  state.showNames = elements.showNames.checked;
  pushHistory();
  renderBoard();
  persist();
});
elements.undo.addEventListener("click", () => applyHistory(state.historyIndex - 1));
elements.redo.addEventListener("click", () => applyHistory(state.historyIndex + 1));
elements.reset.addEventListener("click", () => { if (state.board.some(Boolean) && !confirm("确认清空当前棋盘？")) return; mutate(() => { state.board = Array(28).fill(null); }); });
elements.import.addEventListener("click", () => openCodeDialog("import"));
elements.export.addEventListener("click", () => openCodeDialog("export"));
elements.confirmCode.addEventListener("click", handleCodeConfirm);
elements.share.addEventListener("click", () => shareFormation().catch(() => showToast("复制失败")));
elements.exportImage.addEventListener("click", () => elements.exportImageDialog.showModal());
elements.exportPoster.addEventListener("click", openPosterDialog);
elements.confirmExportImage.addEventListener("click", () => exportBoardImage(
  elements.exportIncludeTraits.checked,
  elements.exportTransparentBackground.checked,
).catch(() => showToast("图片生成失败")));
elements.posterTitle.addEventListener("input", renderPosterPreview);
elements.posterChampionPicker.addEventListener("click", (event) => {
  const option = event.target.closest("[data-poster-champion-id]");
  if (!option) return;
  state.posterChampionId = option.dataset.posterChampionId;
  renderPosterChampionPicker();
  renderPosterPreview();
});
elements.confirmExportPoster.addEventListener("click", () => exportPortraitPoster().catch(() => showToast("海报生成失败")));
elements.posterExportDialog.addEventListener("close", () => {
  elements.posterPreview.replaceChildren();
  elements.posterPreview.style.height = "";
});
window.addEventListener("resize", () => {
  if (elements.posterExportDialog.open) fitPosterPreview();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !event.ctrlKey && !event.metaKey && !/INPUT|TEXTAREA/.test(document.activeElement?.tagName)) { event.preventDefault(); elements.heroSearch.focus(); }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); applyHistory(state.historyIndex + (event.shiftKey ? 1 : -1)); }
  if (event.key === "Escape") { state.selectedItemId = null; setTraitFilterMenu(false); renderItems(); hidePopover(); }
});

window.lucide?.createIcons();
loadCatalog().catch((error) => {
  elements.seasonMeta.textContent = error.message;
  elements.heroGroups.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  showToast(error.message);
});
