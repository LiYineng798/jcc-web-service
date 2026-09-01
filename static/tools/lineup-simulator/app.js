const DATA_ROOT = "/static/season-data";
const DATA_VERSION = document.querySelector("#simulatorRoot")?.dataset.seasonDataVersion || "0";
const UI_ROOT = "/static/tools/lineup-simulator/ui";
const STORAGE_PREFIX = "jcc-simulator-v2:";
const MAX_HISTORY = 40;
const MAX_EXPORT_TRAITS = 8;
const MAX_POSTER_TRAITS = 9;
const MAX_SELECTED_AUGMENTS = 6;
const POSTER_WIDTH = 1200;
const POSTER_HEIGHT = 1600;
const POSTER_DEFAULT_TITLE = "我的阵容";
const FORMATION_CODE_PREFIX = "JCC2-";
const FORMATION_SLOT_BYTES = 8;
const FORMATION_HEADER_BYTES = 9;
const FORMATION_CHECKSUM_BYTES = 4;
const FORMATION_TOTAL_BYTES = FORMATION_HEADER_BYTES + (28 * FORMATION_SLOT_BYTES) + FORMATION_CHECKSUM_BYTES;
const FORMATION_PAYLOAD_LENGTH = (FORMATION_TOTAL_BYTES / 3) * 4;
const FORMATION_CODE_LENGTH = FORMATION_CODE_PREFIX.length + FORMATION_PAYLOAD_LENGTH;
const FORMATION_FLAG_SHOW_NAMES = 1;
const STAT_MARKERS = {
  AD: ["ad", "ad", "物理加成", "AD"], 物理加成: ["ad", "ad", "物理加成", "AD"], 攻击力: ["ad", "ad", "物理加成", "AD"],
  AP: ["ap", "ap", "法术加成", "AP"], 法术加成: ["ap", "ap", "法术加成", "AP"], 法强: ["ap", "ap", "法术加成", "AP"],
  AS: ["attack-speed", "as", "攻击速度", "AS"], 攻击速度: ["attack-speed", "as", "攻击速度", "AS"], 攻速: ["attack-speed", "as", "攻击速度", "AS"],
  HP: ["health", "hp", "生命值", "HP"], 生命上限: ["health", "hp", "生命值", "HP"], 最大生命值: ["health", "hp", "生命值", "HP"],
  MR: ["magic-resist", "mr", "魔法抗性", "MR"], 魔法抗性: ["magic-resist", "mr", "魔法抗性", "MR"], 魔抗: ["magic-resist", "mr", "魔法抗性", "MR"],
  护甲: ["armor", "armor", "护甲", "AR"], ARMOR: ["armor", "armor", "护甲", "AR"], 攻击范围: ["range", "range", "攻击范围", "RNG"], RANGE: ["range", "range", "攻击范围", "RNG"], 射程: ["range", "range", "攻击范围", "RNG"],
  暴击率: ["crit", "crit", "暴击率", "CRIT"], 暴击几率: ["crit", "crit", "暴击率", "CRIT"], CRIT: ["crit", "crit", "暴击率", "CRIT"], 暴击伤害: ["crit-multiplier", "critmult", "暴击伤害", "CRIT"], 暴击倍率: ["crit-multiplier", "critmult", "暴击伤害", "CRIT"],
  法力值: ["mana", "mana", "法力值", "MP"], MANA: ["mana", "mana", "法力值", "MP"], MP: ["mana", "mana", "法力值", "MP"], 法力回复: ["mana-regen", "manaregen", "法力回复", "MP"], 全能吸血: ["omnivamp", "sv", "全能吸血", "吸"], OMNIVAMP: ["omnivamp", "sv", "全能吸血", "吸"],
  伤害加成: ["damage-amplification", "da", "伤害增幅", "增伤"], AMP: ["damage-amplification", "da", "伤害增幅", "增伤"], DA: ["damage-amplification", "da", "伤害增幅", "增伤"],
  伤害增幅: ["damage-amplification", "da", "伤害增幅", "增伤"], 木灵加成: ["amp", "amp", "木灵加成", "木灵"],
  DR: ["damage-reduction", "dr", "伤害减免", "减伤"], 伤害减免: ["damage-reduction", "dr", "伤害减免", "减伤"],
  技能暴击: ["skill-crit", "crit", "技能暴击", "CRIT"],
  灵魂: ["soul", "soul", "灵魂", "魂"], SOUL: ["soul", "soul", "灵魂", "魂"],
  银蛇币: ["serpent", "serpent", "银蛇币", "币"], SERPENT: ["serpent", "serpent", "银蛇币", "币"],
  太阳碎片: ["ixtal", "ixtal.svg", "太阳碎片", "碎片"], IXTAL: ["ixtal", "ixtal.svg", "太阳碎片", "碎片"],
};
const STAT_MARKER_RE = new RegExp(`\\(?【(${Object.keys(STAT_MARKERS).filter((key) => key !== "木灵加成").join("|")})】\\)?|\\(\\)`, "g");
const STAT_ICON_OVERRIDES = {
  critical_strike_damage: "critmult",
  mana_regeneration: "manaregen",
  omnivamp: "sv",
  damage_amplification: "da",
  damage_reduction: "dr",
};
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
const AUGMENT_TIER_LABELS = {
  silver: "白银",
  gold: "黄金",
  prismatic: "棱彩",
  hero: "英雄强化",
  special: "特殊强化",
};
const AUGMENT_STAGE_ORDER = ["2-1", "3-2", "4-2"];
const AUGMENT_CATEGORY_ORDER = ["economy", "combat", "equipment", "trait", "exclusive", "other"];

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
  libraryModeTabs: Array.from(document.querySelectorAll("[data-library-mode]")),
  championLibraryTab: document.querySelector("#championLibraryTab"),
  augmentLibraryTab: document.querySelector("#augmentLibraryTab"),
  championLibraryControls: document.querySelector("#championLibraryControls"),
  augmentLibraryControls: document.querySelector("#augmentLibraryControls"),
  augmentSearch: document.querySelector("#augmentSearch"),
  augmentTierFilters: document.querySelector("#augmentTierFilters"),
  augmentStageFilters: document.querySelector("#augmentStageFilters"),
  augmentCategoryFilters: document.querySelector("#augmentCategoryFilters"),
  augmentGroups: document.querySelector("#augmentGroups"),
  selectedAugmentsPanel: document.querySelector("#selectedAugmentsPanel"),
  selectedAugmentCount: document.querySelector("#selectedAugmentCount"),
  selectedAugmentList: document.querySelector("#selectedAugmentList"),
  showNames: document.querySelector("#showNamesToggle"),
  hoverDetails: document.querySelector("#hoverDetailsToggle"),
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
  exportProgress: document.querySelector("#exportProgress"),
  exportProgressTitle: document.querySelector("#exportProgressTitle"),
  exportProgressStage: document.querySelector("#exportProgressStage"),
  exportProgressBar: document.querySelector("#exportProgressBar"),
};

const state = {
  catalog: [],
  defaultSeasonId: "",
  season: null,
  champions: [],
  boardUnits: [],
  traits: [],
  items: [],
  augments: [],
  championById: new Map(),
  traitById: new Map(),
  itemById: new Map(),
  augmentById: new Map(),
  board: Array(28).fill(null),
  selectedItemId: null,
  selectedAugmentIds: [],
  libraryMode: "champions",
  itemCategory: "normal",
  heroSearch: "",
  itemSearch: "",
  augmentSearch: "",
  augmentTier: "all",
  augmentStage: "all",
  augmentCategory: "all",
  costFilter: "all",
  traitFilters: new Set(),
  showNames: true,
  hoverDetails: true,
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

function traitChoiceNames(raw, traitByName = null) {
  const traitText = (raw.trait_ids || [])
    .map((traitId) => traitByName?.get(String(traitId)))
    .map((trait) => trait?.description || "")
    .filter(Boolean);
  const text = [...(raw.skills || []).map((skill) => skill?.description || ""), ...traitText].join(" ");
  const names = [];
  for (const match of text.matchAll(/从([^。]{0,120})中选择/g)) {
    const choices = [...match[1].matchAll(/【([^】]+)】/g)].map((item) => item[1].trim()).filter(Boolean);
    if (choices.length >= 2) names.push(...choices);
  }
  return [...new Set(names)];
}

function expandChampionTraitChoices(raw, traitByName) {
  const base = normalizeChampion(raw, traitByName);
  const choices = traitChoiceNames(raw, traitByName)
    .map((name) => traitByName.get(name))
    .filter(Boolean);
  if (choices.length < 2) return [base];
  return choices.map((trait, index) => ({
    ...base,
    id: index === 0 ? base.id : `${base.id}~choice-${trait.id}`,
    name: `${base.name} · ${trait.name}`,
    aliases: [...base.aliases, base.name],
    traitIds: [...new Set([...base.traitIds, trait.id])],
    choiceTraitId: trait.id,
    choiceTraitName: trait.name,
  }));
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function simulatorChampionRules(raw, traitsByName) {
  const traitDescriptions = (raw.trait_ids || [])
    .map((traitId) => traitsByName.get(String(traitId))?.description || "")
    .filter(Boolean);
  const championName = escapeRegExp(raw.name);
  const slotPattern = new RegExp(`【${championName}】\\s*占用\\s*(\\d+)\\s*个(?:弈子|队伍)栏位`);
  const slotMatch = traitDescriptions.map((description) => description.match(slotPattern)).find(Boolean);
  const traitContributions = [];
  traitDescriptions.forEach((description) => {
    for (const match of description.matchAll(/提供\s*[+＋]\s*(\d+)\s*【([^】]+)】(?:特质|羁绊|职业)/g)) {
      const trait = traitsByName.get(match[2]);
      if (trait) traitContributions.push({ traitId: trait.id, count: Number(match[1]) });
    }
  });
  return {
    unitSlots: Math.max(1, Number(slotMatch?.[1]) || 1),
    traitContributions,
  };
}

function normalizeChampion(raw, traitsByName) {
  const simulatorRules = simulatorChampionRules(raw, traitsByName);
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
    attackRange: Number(raw.stats_by_star?.["1"]?.attack_range || 0),
    unitSlots: simulatorRules.unitSlots,
    traitContributions: simulatorRules.traitContributions,
    tftCode: String(raw.tft_code || raw.tftCode || ""),
    isBoardUnit: false,
    canEquip: true,
  };
}

function parseCompositeActivation(text) {
  const match = String(text || "").match(/登场\s*(\d+)\s*个【([^】]+)】和\s*(\d+)\s*个【([^】]+)】弈子以激活/);
  if (!match) return [];
  return [{
    source: [{ name: match[2], min: Number(match[1]) }, { name: match[4], min: Number(match[3]) }],
  }];
}

function fallbackRichTextTokens(text) {
  const value = String(text || "");
  const tokens = [];
  let cursor = 0;
  for (const match of value.matchAll(STAT_MARKER_RE)) {
    const woodSpiritPlaceholder = !match[1]
      && value.includes("木灵加成")
      && match.index > 0
      && /[0-9%]/.test(value[match.index - 1]);
    if (!match[1] && !woodSpiritPlaceholder) continue;
    const markerStart = woodSpiritPlaceholder ? match.index + 1 : match.index;
    const markerEnd = woodSpiritPlaceholder ? markerStart : match.index + match[0].length;
    if (markerStart > cursor) tokens.push({ type: "text", value: value.slice(cursor, markerStart) });
    const sourceLabel = woodSpiritPlaceholder ? "木灵加成" : match[1];
    const [kind, icon, label, fallback] = STAT_MARKERS[sourceLabel];
    tokens.push({ type: "stat", kind, icon, label, fallback, source_label: sourceLabel });
    cursor = markerEnd;
  }
  if (cursor < value.length) tokens.push({ type: "text", value: value.slice(cursor) });
  return tokens;
}

function richTextHtml(text, importedTokens = null) {
  const tokens = Array.isArray(importedTokens) && importedTokens.some((token) => token.type === "stat")
    ? importedTokens
    : fallbackRichTextTokens(text);
  if (!tokens.some((token) => token.type === "stat")) return escapeHtml(text);
  return tokens.map((token) => {
    if (token.type === "text") return escapeHtml(token.value);
    const label = token.label || token.source_label || token.stat || "属性加成";
    const kind = token.kind || String(token.stat || "stat").replaceAll("_", "-");
    const iconName = STAT_ICON_OVERRIDES[token.stat] || token.icon;
    const iconFilename = iconName && (/\.[a-z0-9]+$/i.test(iconName) ? iconName : `${iconName}.png`);
    const content = iconFilename
      ? `<img src="/static/season-stats/${encodeURIComponent(iconFilename)}" alt="" aria-hidden="true" />`
      : `<span aria-hidden="true">${escapeHtml(token.fallback || token.source_label || label)}</span>`;
    return `<span class="scale-chip scale-chip-${escapeHtml(kind)}" role="img" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${content}</span>`;
  }).join("");
}

function normalizeBoardUnit(raw) {
  const contributionTraitIds = (raw.contribution_trait_ids || []).map(String);
  const relatedTraitIds = (raw.trait_ids || []).map(String);
  return {
    id: String(raw.id),
    name: raw.name || "未知棋盘对象",
    aliases: raw.aliases || [],
    cost: 0,
    traitIds: contributionTraitIds,
    boardUnitTraitIds: [...new Set([...relatedTraitIds, ...contributionTraitIds])],
    availability: { type: "trait_object", description: null, rules: raw.placement_rules || [] },
    placementRules: raw.placement_rules || [],
    icon: seasonAsset(raw.image?.optimized_local_path || raw.image?.local_path),
    posterIcon: seasonAsset(raw.image?.local_path || raw.image?.optimized_local_path),
    splash: seasonAsset(raw.image?.local_path || raw.image?.optimized_local_path),
    skill: raw.skill || null,
    stats: raw.stats || {},
    isBoardUnit: true,
    canEquip: raw.can_equip === true,
  };
}

function normalizeTrait(raw) {
  const activationRules = parseCompositeActivation(raw.description).filter((rule) => (
    rule.source.every((source) => source.name !== raw.name)
  ));
  if (!activationRules.length && raw.name === "日月双蚀") {
    activationRules.push({
      source: [{ name: "日蚀骑士", min: 3 }, { name: "月蚀骑士", min: 3 }],
    });
  }
  return {
    id: String(raw.id),
    name: raw.name || "未知羁绊",
    category: raw.category || "other",
    description: raw.description || "",
    descriptionTokens: raw.description_tokens || null,
    breakpoints: [...(raw.breakpoints || [])].sort((a, b) => Number(a.min_units) - Number(b.min_units)),
    icon: seasonAsset(raw.image?.optimized_local_path || raw.image?.local_path),
    tags: raw.tags || [],
    activationRules,
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
    descriptionTokens: raw.description_tokens || null,
    stats: raw.stats?.raw || "",
    effects: raw.effects || [],
    unique: Boolean(raw.unique),
    recipe: raw.recipe || { type: "none", component_ids: [] },
    grantedTraitId: rawGrantedTraitId == null || rawGrantedTraitId === "" ? null : String(rawGrantedTraitId),
    icon: seasonAsset(raw.image?.optimized_local_path || raw.image?.local_path),
  };
}

function normalizeAugment(raw) {
  return {
    id: String(raw.id),
    name: raw.name || "未知强化符文",
    description: raw.description || "",
    descriptionTokens: raw.description_tokens || null,
    tier: raw.tier || "other",
    tierLabel: raw.tier_label || AUGMENT_TIER_LABELS[raw.tier] || "强化符文",
    tierOrder: Number(raw.tier_order) || 99,
    augmentType: raw.augment_type || "standard",
    category: raw.category || "other",
    categoryLabel: raw.category_label || "其他",
    appearanceStages: raw.appearance_stages || [],
    stageDataStatus: raw.extensions?.appearance_stage_evidence?.status || "unavailable",
    icon: seasonAsset(raw.image?.optimized_local_path || raw.image?.local_path),
    posterIcon: seasonAsset(raw.image?.local_path || raw.image?.optimized_local_path),
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
  const persistedId = localStorage.getItem(`${STORAGE_PREFIX}season`);
  const initial = state.catalog.find((season) => season.season_id === hashPayload?.season)
    || state.catalog.find((season) => season.season_id === persistedId)
    || state.catalog.find((season) => season.season_id === state.defaultSeasonId)
    || state.catalog.find((season) => season.status === "active")
    || state.catalog[0];
  if (!initial) throw new Error("资料库中没有可用赛季");
  await loadSeason(initial.season_id, hashPayload);
}

async function refreshCatalog() {
  const catalog = await fetchJson(`/api/season-catalog?surface=simulator&v=${encodeURIComponent(DATA_VERSION)}`);
  state.catalog = [...(catalog.seasons || [])].sort((a, b) => Number(a.order || 999) - Number(b.order || 999));
  state.defaultSeasonId = catalog.default_season_id || '';
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
  state.libraryMode = "champions";
  state.augmentSearch = "";
  state.augmentTier = "all";
  state.augmentStage = "all";
  state.augmentCategory = "all";
  elements.heroSearch.value = "";
  elements.itemSearch.value = "";
  elements.augmentSearch.value = "";
  setLoading(true);
  try {
    const stamp = encodeURIComponent(`${season.version_id}-${DATA_VERSION}`);
    const augmentRequest = Number(season.counts?.augments || 0) > 0
      ? fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/augments.json?v=${stamp}`)
      : Promise.resolve({ augments: [] });
    const [championData, traitData, itemData, boardUnitData, augmentData] = await Promise.all([
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/champions.json?v=${stamp}`),
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/traits.json?v=${stamp}`),
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/items.json?v=${stamp}`),
      fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/board_units.json?v=${stamp}`),
      augmentRequest,
    ]);
    state.traits = (traitData.traits || []).map(normalizeTrait)
      .sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name, "zh-CN"));
    const traitByName = new Map(state.traits.flatMap((trait) => [[trait.name, trait], [String(trait.id), trait]]));
    state.champions = (championData.champions || [])
      .filter((raw) => raw.extensions?.simulator_visible !== false)
      .flatMap((raw) => expandChampionTraitChoices(raw, traitByName))
      .sort((a, b) => a.cost - b.cost || a.name.localeCompare(b.name, "zh-CN"));
    state.boardUnits = (boardUnitData.board_units || []).map(normalizeBoardUnit).sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    state.items = (itemData.items || []).map(normalizeItem);
    state.augments = (augmentData.augments || []).map(normalizeAugment)
      .sort((a, b) => a.tierOrder - b.tierOrder || a.category.localeCompare(b.category) || a.name.localeCompare(b.name, "zh-CN"));
    const availableCategories = availableItemCategories();
    if (!availableCategories.some((category) => category.id === state.itemCategory)) {
      state.itemCategory = availableCategories[0]?.id || "normal";
    }
    state.championById = new Map([...state.champions, ...state.boardUnits].map((item) => [item.id, item]));
    state.traitById = new Map(state.traits.map((item) => [item.id, item]));
    state.itemById = new Map(state.items.map((item) => [item.id, item]));
    state.augmentById = new Map(state.augments.map((item) => [item.id, item]));
    state.tftCodeMap = {};
    try {
      const codebook = await fetchJson(`${DATA_ROOT}/${encodeURIComponent(seasonId)}/tft-codebook.json?v=${stamp}`);
      state.tftCodeMap = codebook.codes || {};
    } catch { /* A season can be used before a TFT codebook is available. */ }
    let payload = readStoredFormation(seasonId);
    if (importedPayload?.season === seasonId) {
      payload = importedPayload.format === "JCC2" ? decodePayload(importedPayload.code) : importedPayload;
    }
    state.board = hydrateBoard(payload?.board);
    state.selectedAugmentIds = hydrateAugmentIds(payload?.augmentIds);
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

function hydrateAugmentIds(rawIds) {
  if (!Array.isArray(rawIds)) return [];
  return [...new Set(rawIds.map(String).filter((id) => state.augmentById.has(id)))].slice(0, MAX_SELECTED_AUGMENTS);
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
  renderAugments();
  renderSelectedAugments();
  renderLibraryMode();
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
    const boardUnitText = state.boardUnits.length ? ` · ${state.boardUnits.length} 个棋盘对象` : "";
    elements.seasonMeta.textContent = `${state.season.display_name} · ${state.season.game_version} · ${state.champions.length} 名弈子${boardUnitText}`;
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
  const championGroups = costs.map((cost) => {
    if (state.costFilter !== "all" && Number(state.costFilter) !== cost) return "";
    const heroes = state.champions.filter((hero) => hero.cost === cost && (!query || normalizeText([hero.name, ...hero.aliases].join(" ")).includes(query)));
    if (!heroes.length) return "";
    return `<section class="hero-cost-group" aria-label="${cost}费弈子">
      <div class="cost-heading" style="--cost-color:${costColor(cost)}"><span class="cost-dot"></span><span><strong>${cost}</strong>费用</span></div>
      <div class="hero-grid">${heroes.map(heroButtonHtml).join("")}</div>
    </section>`;
  }).join("");
  const boardUnits = state.costFilter === "all"
    ? state.boardUnits.filter((unit) => !query || normalizeText([unit.name, ...unit.aliases].join(" ")).includes(query))
    : [];
  const specialGroup = boardUnits.length ? `<section class="hero-cost-group special-group" aria-label="特殊棋盘对象">
    <div class="cost-heading"><span class="cost-dot"></span><span><strong>特殊</strong>单位</span></div>
    <div class="hero-grid">${boardUnits.map(heroButtonHtml).join("")}</div>
  </section>` : "";
  const groups = `${championGroups}${specialGroup}`;
  elements.heroGroups.innerHTML = groups || '<div class="empty-state">没有符合条件的弈子</div>';
}

function heroButtonHtml(hero) {
  const filterTraitIds = hero.isBoardUnit ? hero.boardUnitTraitIds : hero.traitIds;
  const traitMismatch = state.traitFilters.size > 0 && ![...state.traitFilters].every((id) => filterTraitIds.includes(id));
  const unlocked = hero.availability?.type === "unlock";
  const allowance = hero.isBoardUnit ? boardUnitAllowance(hero) : null;
  const placed = hero.isBoardUnit ? countPlacedUnit(hero.id) : 0;
  const locked = hero.isBoardUnit && placed >= allowance;
  const requirement = hero.isBoardUnit ? boardUnitRequirementText(hero) : "";
  const title = traitMismatch ? "不属于当前筛选羁绊" : locked ? requirement : "";
  return `<button class="hero-button ${hero.isBoardUnit ? "is-special" : ""} ${traitMismatch ? "is-dimmed" : ""} ${locked ? "is-locked" : ""}" type="button" draggable="${!locked}" data-hero-id="${escapeHtml(hero.id)}" data-locked="${locked}" style="--hero-color:${hero.isBoardUnit ? "#4fc6b1" : costColor(hero.cost)}" aria-label="上阵 ${escapeHtml(hero.name)}" aria-disabled="${locked}"${title ? ` title="${escapeHtml(title)}"` : ""}>
    <img src="${escapeHtml(hero.icon)}" alt="" loading="lazy" decoding="async" />
    <span>${escapeHtml(hero.name)}</span>
    ${unlocked ? `<img class="hero-unlock" src="${UI_ROOT}/unlock.png" alt="解锁弈子" />` : ""}
    ${hero.isBoardUnit ? `<b class="hero-special-mark">${allowance ? `${placed}/${allowance}` : "锁"}</b>` : ""}
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

function syncLibrarySelectionState() {
  elements.itemGrid.querySelectorAll("[data-item-id]").forEach((button) => {
    const selected = button.dataset.itemId === state.selectedItemId;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  elements.augmentGroups.querySelectorAll("[data-augment-id]").forEach((button) => {
    const selected = state.selectedAugmentIds.includes(button.dataset.augmentId);
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
    const augment = state.augmentById.get(button.dataset.augmentId);
    if (augment) button.setAttribute("aria-label", `${selected ? "移除" : "选择"} ${augment.name}`);
  });
  elements.heroGroups.querySelectorAll("[data-hero-id]").forEach((button) => {
    const hero = state.championById.get(button.dataset.heroId);
    if (!hero?.isBoardUnit) return;
    const allowance = boardUnitAllowance(hero);
    const placed = countPlacedUnit(hero.id);
    const locked = placed >= allowance;
    button.classList.toggle("is-locked", locked);
    button.dataset.locked = String(locked);
    button.draggable = !locked;
    button.setAttribute("aria-disabled", String(locked));
    button.title = locked ? boardUnitRequirementText(hero) : "";
    const mark = button.querySelector(".hero-special-mark");
    if (mark) mark.textContent = allowance ? `${placed}/${allowance}` : "锁";
  });
  updateSelectedItemStatus();
}

function renderLibraryMode() {
  if (!state.augments.length) state.libraryMode = "champions";
  elements.augmentLibraryTab.hidden = state.augments.length === 0;
  elements.libraryModeTabs.forEach((button) => {
    const active = button.dataset.libraryMode === state.libraryMode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  const showingChampions = state.libraryMode === "champions";
  elements.championLibraryControls.hidden = !showingChampions;
  elements.augmentLibraryControls.hidden = showingChampions;
  elements.heroGroups.hidden = !showingChampions;
  elements.augmentGroups.hidden = showingChampions;
}

function augmentFilterOptions() {
  const tiers = [...new Map(state.augments.map((augment) => [augment.tier, augment])).values()]
    .sort((a, b) => a.tierOrder - b.tierOrder)
    .map((augment) => ({ id: augment.tier, label: AUGMENT_TIER_LABELS[augment.tier] || augment.tierLabel }));
  const availableStages = new Set(state.augments.flatMap((augment) => augment.appearanceStages));
  const stages = AUGMENT_STAGE_ORDER.filter((stage) => availableStages.has(stage));
  const categoryLabels = new Map(state.augments.map((augment) => [augment.category, augment.categoryLabel]));
  const categoryIds = [
    ...AUGMENT_CATEGORY_ORDER.filter((id) => categoryLabels.has(id)),
    ...[...categoryLabels.keys()].filter((id) => !AUGMENT_CATEGORY_ORDER.includes(id)),
  ];
  const categories = categoryIds.map((id) => ({ id, label: categoryLabels.get(id) }));
  return {
    tiers,
    stages: stages.map((stage) => ({ id: stage, label: stage })),
    categories,
  };
}

function augmentFilterHtml(options, key) {
  return options.map((option) => {
    const active = state[key] === option.id;
    return `<button class="${active ? "is-active" : ""}" type="button" data-augment-filter-key="${key}" data-augment-filter-value="${escapeHtml(option.id)}" aria-pressed="${active}" title="${active ? "再次点击清除此筛选" : `筛选：${escapeHtml(option.label)}`}">${escapeHtml(option.label)}</button>`;
  }).join("");
}

function filteredAugments() {
  const query = normalizeText(state.augmentSearch);
  return state.augments.filter((augment) => {
    if (state.augmentTier !== "all" && augment.tier !== state.augmentTier) return false;
    if (state.augmentStage !== "all" && !augment.appearanceStages.includes(state.augmentStage)) return false;
    if (state.augmentCategory !== "all" && augment.category !== state.augmentCategory) return false;
    return !query || normalizeText([augment.name, augment.description, augment.categoryLabel, augment.tierLabel].join(" ")).includes(query);
  });
}

function renderAugments() {
  const options = augmentFilterOptions();
  elements.augmentTierFilters.innerHTML = augmentFilterHtml(options.tiers, "augmentTier");
  elements.augmentStageFilters.innerHTML = augmentFilterHtml(options.stages, "augmentStage");
  elements.augmentCategoryFilters.innerHTML = augmentFilterHtml(options.categories, "augmentCategory");
  const augments = filteredAugments();
  elements.augmentGroups.innerHTML = augments.length ? augments.map((augment) => {
    const selected = state.selectedAugmentIds.includes(augment.id);
    return `<button class="augment-library-card augment-tier-${escapeHtml(augment.tier)} ${selected ? "is-selected" : ""}" type="button" data-augment-id="${escapeHtml(augment.id)}" aria-pressed="${selected}" aria-label="${selected ? "移除" : "选择"} ${escapeHtml(augment.name)}">
      <img src="${escapeHtml(augment.icon)}" alt="" loading="lazy" decoding="async" />
      <span><small>${escapeHtml(AUGMENT_TIER_LABELS[augment.tier] || augment.tierLabel)}</small><strong>${escapeHtml(augment.name)}</strong><em>${escapeHtml(augment.categoryLabel)}</em></span>
    </button>`;
  }).join("") : '<div class="empty-state">没有符合条件的强化符文</div>';
}

function renderSelectedAugments() {
  const augments = state.selectedAugmentIds.map((id) => state.augmentById.get(id)).filter(Boolean);
  elements.selectedAugmentsPanel.hidden = augments.length === 0;
  elements.selectedAugmentCount.textContent = `${augments.length} / ${MAX_SELECTED_AUGMENTS}`;
  elements.selectedAugmentList.innerHTML = augments.map((augment) => `
    <article class="selected-augment-chip augment-tier-${escapeHtml(augment.tier)}" data-augment-id="${escapeHtml(augment.id)}">
      <img src="${escapeHtml(augment.icon)}" alt="" />
      <span><small>${escapeHtml(AUGMENT_TIER_LABELS[augment.tier] || augment.tierLabel)}</small><strong>${escapeHtml(augment.name)}</strong></span>
      <button type="button" data-remove-augment-id="${escapeHtml(augment.id)}" title="移除 ${escapeHtml(augment.name)}" aria-label="移除 ${escapeHtml(augment.name)}"><i data-lucide="x"></i></button>
    </article>`).join("");
  window.lucide?.createIcons();
}

function toggleAugment(augmentId) {
  if (!state.augmentById.has(augmentId)) return;
  const selected = state.selectedAugmentIds.includes(augmentId);
  if (!selected && state.selectedAugmentIds.length >= MAX_SELECTED_AUGMENTS) {
    showToast(`最多选择 ${MAX_SELECTED_AUGMENTS} 个强化符文`);
    return;
  }
  mutate(() => {
    state.selectedAugmentIds = selected
      ? state.selectedAugmentIds.filter((id) => id !== augmentId)
      : [...state.selectedAugmentIds, augmentId];
  });
}

function renderBoard() {
  elements.board.classList.toggle("hide-names", !state.showNames);
  elements.board.innerHTML = state.board.map((slot, index) => boardSlotHtml(slot, index)).join("");
  const units = state.board.filter(Boolean);
  const population = totalPopulation();
  elements.unitCount.textContent = String(population);
  elements.totalCost.textContent = String(units.reduce((total, slot) => total + (state.championById.get(slot.championId)?.cost || 0), 0));
  const invalidSpecials = state.board.filter((slot, index) => slot && !specialPlacementIsValid(slot.championId, index)).length;
  elements.boardStatus.textContent = population > state.board.length
    ? `阵容超出 ${population - state.board.length} 人口，请调整后再使用`
    : invalidSpecials
    ? `${invalidSpecials} 个特殊单位未满足解锁条件`
    : units.length ? `${population} 人口 · ${units.length} 个单位已上阵` : "阵容未配置";
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
  const validSpecial = !hero.isBoardUnit || specialPlacementIsValid(hero.id, index);
  const longNameClass = [...hero.name].length > 7 ? " is-long" : "";
  return `<button class="hex-cell has-unit ${items ? "has-items" : ""} ${hero.isBoardUnit ? "is-special" : ""} ${validSpecial ? "" : "is-invalid-special"}" type="button" role="gridcell" draggable="true" data-slot-index="${index}" data-hero-id="${escapeHtml(hero.id)}" aria-label="${escapeHtml(hero.name)}">
    <span class="hex-floor"></span>
    <span class="unit-portrait" style="--unit-color:${costColor(hero.cost)}"><img class="unit-portrait-image" src="${escapeHtml(hero.icon)}" alt="" /></span>
    <span class="unit-items">${items}</span>
    <span class="unit-name${longNameClass}">${escapeHtml(hero.name)}</span>
    ${hero.availability?.type === "unlock" ? `<span class="unlock-mark" title="解锁弈子"><img src="${UI_ROOT}/unlock.png" alt="" /></span>` : ""}
  </button>`;
}

function getTraitCounts() {
  const contributors = new Map();
  const addContributor = (traitId, unitId, count = 1) => {
    if (!state.traitById.has(traitId)) return;
    if (!contributors.has(traitId)) contributors.set(traitId, new Map());
    const traitContributors = contributors.get(traitId);
    traitContributors.set(unitId, Math.max(traitContributors.get(unitId) || 0, count));
  };
  const countContributors = (traitContributors) => [...traitContributors.values()]
    .reduce((total, count) => total + count, 0);
  state.board.filter(Boolean).forEach((slot) => {
    const hero = state.championById.get(slot.championId);
    hero?.traitIds.forEach((traitId) => addContributor(traitId, hero.id));
    hero?.traitContributions.forEach(({ traitId, count }) => addContributor(traitId, hero.id, count));
    slot.items.forEach((itemId) => {
      const traitId = state.itemById.get(itemId)?.grantedTraitId;
      if (traitId) addContributor(traitId, hero.id);
    });
  });

  // Composite traits declare their source thresholds in the imported trait
  // text. This covers S18 日月双蚀 without coupling the simulator to IDs.
  const traitsByName = new Map(state.traits.map((trait) => [trait.name, trait]));
  state.traits.forEach((trait) => {
    (trait.activationRules || []).forEach((rule) => {
      const sourceContributors = rule.source.map((source) => ({
        contributors: contributors.get(traitsByName.get(source.name)?.id) || new Map(),
        min: source.min,
      }));
      if (sourceContributors.some((source) => countContributors(source.contributors) < source.min)) return;
      const composite = contributors.get(trait.id) || new Map();
      sourceContributors.forEach((source) => source.contributors.forEach((count, heroId) => {
        composite.set(heroId, Math.max(composite.get(heroId) || 0, count));
      }));
      contributors.set(trait.id, composite);
    });
  });

  return new Map([...contributors].map(([traitId, traitContributors]) => [traitId, countContributors(traitContributors)]));
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

function totalPopulation(board = state.board) {
  return board.filter(Boolean).reduce((total, slot) => (
    total + (state.championById.get(slot.championId)?.unitSlots || 1)
  ), 0);
}

function placementStart(hero) {
  const range = Number(hero?.attackRange || hero?.stats?.attack_range || 0);
  if (range <= 2) return 0;
  if (range === 3) return 7;
  if (range >= 4) return 21;
  return 0;
}

function automaticSlot(hero) {
  const start = placementStart(hero);
  for (let index = start; index < state.board.length; index += 1) if (!state.board[index]) return index;
  if (start) for (let index = 0; index < start; index += 1) if (!state.board[index]) return index;
  return -1;
}

function countPlacedUnit(unitId, beforeIndex = state.board.length) {
  return state.board.slice(0, beforeIndex).filter((slot) => slot?.championId === unitId).length;
}

function boardUnitAllowance(unit) {
  if (!unit?.isBoardUnit) return Infinity;
  const traitCounts = getTraitCounts();
  return unit.placementRules.reduce((maximum, rule) => {
    const count = rule.champion_id
      ? countPlacedUnit(String(rule.champion_id))
      : traitCounts.get(String(rule.trait_id)) || 0;
    return count >= Number(rule.min_units || 1) ? Math.max(maximum, Number(rule.max_count || 1)) : maximum;
  }, 0);
}

function boardUnitRequirementText(unit) {
  const first = [...(unit.placementRules || [])].sort((a, b) => Number(a.min_units) - Number(b.min_units))[0];
  const trait = first ? state.traitById.get(String(first.trait_id)) : null;
  const champion = first ? state.championById.get(String(first.champion_id)) : null;
  if (trait) return `需要 ${first.min_units} ${trait.name}`;
  if (champion) return `需要先上阵 ${champion.name}`;
  return "当前阵容未解锁该棋盘对象";
}

function specialPlacementIsValid(unitId, index) {
  const unit = state.championById.get(unitId);
  if (!unit?.isBoardUnit) return true;
  return countPlacedUnit(unitId, index + 1) <= boardUnitAllowance(unit);
}

function addChampion(championId, requestedIndex = null) {
  const hero = state.championById.get(championId);
  if (!hero) return;
  if (totalPopulation() + hero.unitSlots > state.board.length) {
    return showToast("阵容人口已满");
  }
  if (hero.isBoardUnit && countPlacedUnit(hero.id) >= boardUnitAllowance(hero)) {
    return showToast(boardUnitRequirementText(hero));
  }
  const index = requestedIndex ?? automaticSlot(hero);
  if (index < 0) return showToast("棋盘已满");
  mutate(() => { state.board[index] = { championId, items: [] }; });
}

function equipItem(slotIndex, itemId) {
  const slot = state.board[slotIndex];
  if (!slot) return showToast("请先在该位置上阵弈子");
  if (state.championById.get(slot.championId)?.canEquip === false) return showToast("棋盘对象不能携带装备");
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
  syncLibrarySelectionState();
  renderSelectedAugments();
  persist();
}

function snapshot() {
  return JSON.stringify({ board: state.board, augmentIds: state.selectedAugmentIds, showNames: state.showNames });
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
  state.selectedAugmentIds = hydrateAugmentIds(value.augmentIds);
  state.showNames = value.showNames !== false;
  elements.showNames.checked = state.showNames;
  renderBoard();
  syncLibrarySelectionState();
  renderSelectedAugments();
  persist();
}

function formationPayload() {
  return { version: 2, season: state.season.season_id, showNames: state.showNames, board: state.board, augmentIds: state.selectedAugmentIds };
}

function persist() {
  if (!state.season) return;
  localStorage.setItem(`${STORAGE_PREFIX}${state.season.season_id}`, JSON.stringify(formationPayload()));
}

function readStoredFormation(seasonId) {
  try { return JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}${seasonId}`) || "null"); }
  catch { return null; }
}

function fnv1a32(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  let hash = 0x811c9dc5;
  bytes.forEach((byte) => {
    hash ^= byte;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  });
  return hash >>> 0;
}

function formationCodebook() {
  const units = [...state.champions, ...state.boardUnits].sort((a, b) => String(a.id).localeCompare(String(b.id), undefined, { numeric: true }));
  const items = [...state.items].sort((a, b) => String(a.id).localeCompare(String(b.id), undefined, { numeric: true }));
  const unitIds = units.map((unit) => unit.id);
  const itemIds = items.map((item) => item.id);
  return {
    units,
    items,
    unitIndexes: new Map(unitIds.map((id, index) => [id, index + 1])),
    itemIndexes: new Map(itemIds.map((id, index) => [id, index + 1])),
    hash: fnv1a32(`JCC2|${state.season.season_id}|U:${unitIds.join(",")}|I:${itemIds.join(",")}`),
  };
}

function bytesToBase64Url(bytes) {
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function base64UrlToBytes(value) {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function normalizeFormationCode(value) {
  const text = String(value || "").trim();
  const hashMatch = text.match(/#lineup=([^&#\s]+)/);
  return hashMatch ? hashMatch[1] : text;
}

function encodePayload(payload = formationPayload()) {
  const codebook = formationCodebook();
  const bytes = new Uint8Array(FORMATION_TOTAL_BYTES);
  const view = new DataView(bytes.buffer);
  view.setUint8(0, payload.showNames === false ? 0 : FORMATION_FLAG_SHOW_NAMES);
  view.setUint32(1, fnv1a32(payload.season));
  view.setUint32(5, codebook.hash);
  (payload.board || []).slice(0, 28).forEach((slot, slotIndex) => {
    const offset = FORMATION_HEADER_BYTES + (slotIndex * FORMATION_SLOT_BYTES);
    if (!slot) return;
    const unitIndex = codebook.unitIndexes.get(String(slot.championId));
    if (!unitIndex) throw new Error("阵容包含当前赛季不支持的弈子");
    view.setUint16(offset, unitIndex);
    (slot.items || []).slice(0, 3).forEach((itemId, itemIndex) => {
      const itemCode = codebook.itemIndexes.get(String(itemId));
      if (!itemCode) throw new Error("阵容包含当前赛季不支持的装备");
      view.setUint16(offset + 2 + (itemIndex * 2), itemCode);
    });
  });
  view.setUint32(FORMATION_TOTAL_BYTES - FORMATION_CHECKSUM_BYTES, fnv1a32(bytes.slice(0, -FORMATION_CHECKSUM_BYTES)));
  const code = `${FORMATION_CODE_PREFIX}${bytesToBase64Url(bytes)}`;
  if (code.length !== FORMATION_CODE_LENGTH) throw new Error("阵容码生成长度异常");
  return code;
}

function inspectFixedFormation(code) {
  if (!code.startsWith(FORMATION_CODE_PREFIX) || code.length !== FORMATION_CODE_LENGTH) throw new Error("阵容码长度无效");
  const bytes = base64UrlToBytes(code.slice(FORMATION_CODE_PREFIX.length));
  if (bytes.length !== FORMATION_TOTAL_BYTES) throw new Error("阵容码数据无效");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const expectedChecksum = view.getUint32(FORMATION_TOTAL_BYTES - FORMATION_CHECKSUM_BYTES);
  const actualChecksum = fnv1a32(bytes.slice(0, -FORMATION_CHECKSUM_BYTES));
  if (expectedChecksum !== actualChecksum) throw new Error("阵容码校验失败");
  const seasonHash = view.getUint32(1);
  const season = state.catalog.find((candidate) => fnv1a32(candidate.season_id) === seasonHash)?.season_id || null;
  if (!season) throw new Error("阵容码赛季不受支持");
  return { format: "JCC2", code, season, bytes };
}

function decodeFixedFormation(code) {
  const inspected = inspectFixedFormation(code);
  if (inspected.season !== state.season?.season_id) throw new Error("请先切换到阵容码对应赛季");
  const view = new DataView(inspected.bytes.buffer, inspected.bytes.byteOffset, inspected.bytes.byteLength);
  const codebook = formationCodebook();
  if (view.getUint32(5) !== codebook.hash) throw new Error("阵容码与当前赛季资料版本不兼容");
  const board = Array(28).fill(null);
  for (let slotIndex = 0; slotIndex < 28; slotIndex += 1) {
    const offset = FORMATION_HEADER_BYTES + (slotIndex * FORMATION_SLOT_BYTES);
    const unitCode = view.getUint16(offset);
    const itemCodes = [view.getUint16(offset + 2), view.getUint16(offset + 4), view.getUint16(offset + 6)];
    if (!unitCode) {
      if (itemCodes.some(Boolean)) throw new Error("空棋格包含装备数据");
      continue;
    }
    const unit = codebook.units[unitCode - 1];
    if (!unit) throw new Error("阵容码包含未知弈子");
    const items = itemCodes.filter(Boolean).map((itemCode) => {
      const item = codebook.items[itemCode - 1];
      if (!item) throw new Error("阵容码包含未知装备");
      return item.id;
    });
    if (unit.canEquip === false && items.length) throw new Error("棋盘对象不能携带装备");
    board[slotIndex] = { championId: unit.id, items };
  }
  return {
    version: 2,
    season: inspected.season,
    showNames: Boolean(view.getUint8(0) & FORMATION_FLAG_SHOW_NAMES),
    board,
  };
}

function decodeLegacyPayload(code) {
  const bytes = base64UrlToBytes(code);
  return JSON.parse(new TextDecoder().decode(bytes));
}

function inspectFormationCode(value) {
  const code = normalizeFormationCode(value);
  if (code.startsWith(FORMATION_CODE_PREFIX)) return inspectFixedFormation(code);
  const payload = decodeLegacyPayload(code);
  if (!payload?.season || !Array.isArray(payload.board)) throw new Error("旧版阵容码无效");
  return payload;
}

function decodePayload(value) {
  const code = normalizeFormationCode(value);
  return code.startsWith(FORMATION_CODE_PREFIX) ? decodeFixedFormation(code) : decodeLegacyPayload(code);
}

function isTftTeamCode(value) {
  return /^(?:01|02)[0-9a-fA-F]+TFTSet[0-9A-Za-z._]+$/.test(String(value || "").trim());
}

function decodeTftTeamCode(value) {
  const match = String(value || "").trim().match(/^(01|02)([0-9a-fA-F]+)TFTSet/);
  if (!match) throw new Error("云顶阵容码格式无效");
  const width = match[1] === "01" ? 2 : 3;
  const board = Array(28).fill(null);
  const originalBoard = state.board;
  state.board = board;
  try {
    for (let offset = 0; offset + width <= match[2].length && offset / width < 10; offset += width) {
      const token = match[2].slice(offset, offset + width).toLowerCase();
      if (/^0+$/.test(token)) continue;
      const championId = state.tftCodeMap?.[token];
      const hero = state.championById.get(String(championId));
      if (!hero) continue;
      const index = automaticSlot(hero);
      if (index < 0) break;
      board[index] = { championId: String(championId), items: [] };
    }
  } finally {
    state.board = originalBoard;
  }
  if (!board.some(Boolean)) throw new Error("云顶阵容码未匹配到当前赛季弈子");
  return { version: 2, season: state.season.season_id, showNames: true, board, augmentIds: [] };
}

function readHashPayload() {
  const match = location.hash.match(/^#lineup=(.+)$/);
  if (!match) return null;
  try { return inspectFormationCode(match[1]); }
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
    const rawCode = normalizeFormationCode(elements.code.value);
    if (isTftTeamCode(rawCode)) {
      const seasonMatch = rawCode.match(/TFTSet([0-9]+(?:\.[0-9]+)?)/i);
      const targetSeason = seasonMatch ? ({ "16.5": "s16_5", "16": "s16_5", "17": "s17", "18": "s18" }[seasonMatch[1]] || state.season.season_id) : state.season.season_id;
      if (targetSeason !== state.season.season_id && state.catalog.some((item) => item.season_id === targetSeason)) await loadSeason(targetSeason);
      const payload = decodeTftTeamCode(rawCode);
      state.board = payload.board;
      state.selectedAugmentIds = [];
      pushHistory();
      renderAll();
      elements.dialog.close();
      return showToast("云顶阵容码已导入并自动排位");
    }
    const inspected = inspectFormationCode(elements.code.value);
    if (inspected.season !== state.season.season_id) await loadSeason(inspected.season, inspected);
    else {
      const payload = inspected.format === "JCC2" ? decodePayload(inspected.code) : inspected;
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

function waitForPaint() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function beginExportProgress(title) {
  elements.exportProgressTitle.textContent = title;
  elements.exportProgressStage.textContent = "正在整理棋盘";
  elements.exportProgressBar.style.width = "10%";
  elements.exportProgress.hidden = false;
  elements.exportProgress.setAttribute("aria-hidden", "false");
  document.body.classList.add("export-running");
  return performance.now();
}

async function updateExportProgress(stage, percent) {
  elements.exportProgressStage.textContent = stage;
  elements.exportProgressBar.style.width = `${Math.max(10, Math.min(100, percent))}%`;
  await waitForPaint();
}

async function finishExportProgress(startedAt) {
  const remaining = Math.max(0, 1100 - (performance.now() - startedAt));
  if (remaining) await delay(remaining);
  elements.exportProgress.hidden = true;
  elements.exportProgress.setAttribute("aria-hidden", "true");
  document.body.classList.remove("export-running");
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
  elements.exportImageDialog.close();
  elements.exportImage.disabled = true;
  elements.confirmExportImage.disabled = true;
  const startedAt = beginExportProgress("图片正在导出");
  let capture = null;
  try {
    await updateExportProgress("正在整理棋盘与羁绊", 22);
    capture = buildImageCapture(includeTraits, transparentBackground);
    await updateExportProgress("正在加载字体与图像", 42);
    await document.fonts?.ready;
    await updateExportProgress("正在绘制高清阵容图", 68);
    const dataUrl = await window.htmlToImage.toPng(capture, {
      backgroundColor: transparentBackground ? "transparent" : "#0d101a",
      cacheBust: true,
      pixelRatio: 2,
      style: { position: "static", left: "auto", top: "auto", zIndex: "auto" },
    });
    await updateExportProgress("正在准备下载", 92);
    const link = document.createElement("a");
    link.download = `${state.season.season_id}-lineup.png`;
    link.href = dataUrl;
    link.click();
    await updateExportProgress("导出完成", 100);
    showToast("阵容图已保存");
  } finally {
    capture?.remove();
    elements.exportImage.disabled = false;
    elements.confirmExportImage.disabled = false;
    await finishExportProgress(startedAt);
  }
}

function posterChampionCandidates() {
  const seen = new Set();
  return state.board.flatMap((slot, index) => {
    if (!slot || seen.has(slot.championId)) return [];
    const hero = state.championById.get(slot.championId);
    if (!hero || hero.isBoardUnit) return [];
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

function posterAugmentHtml() {
  const augments = state.selectedAugmentIds
    .map((id) => state.augmentById.get(id))
    .filter(Boolean)
    .slice(0, MAX_SELECTED_AUGMENTS);
  if (!augments.length) return '<div class="lineup-poster-augments-empty">未选择强化符文</div>';
  return augments.map((augment) => `
    <div class="lineup-poster-augment augment-tier-${escapeHtml(augment.tier)}">
      <img src="${escapeHtml(augment.posterIcon || augment.icon)}" alt="" data-fallback-src="${escapeHtml(augment.icon)}" />
      <span><small>${escapeHtml(AUGMENT_TIER_LABELS[augment.tier] || augment.tierLabel)}</small><strong>${escapeHtml(augment.name)}</strong></span>
    </div>`).join("");
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
  const selectedAugmentCount = state.selectedAugmentIds.filter((id) => state.augmentById.has(id)).length;
  const poster = document.createElement("section");
  poster.className = "lineup-poster-capture";
  poster.style.setProperty("--poster-width", `${POSTER_WIDTH}px`);
  poster.style.setProperty("--poster-height", `${POSTER_HEIGHT}px`);
  poster.innerHTML = `
    <div class="lineup-poster-background">
      ${hero?.splash ? `
        <img class="lineup-poster-background-fill" src="${escapeHtml(hero.splash)}" alt="" data-fallback-src="${escapeHtml(hero.icon)}" />
        <img class="lineup-poster-background-art" src="${escapeHtml(hero.splash)}" alt="" data-fallback-src="${escapeHtml(hero.icon)}" />` : ""}
    </div>
    <div class="lineup-poster-overlay"></div>
    <header class="lineup-poster-header">
      <div class="lineup-poster-season"><span>${escapeHtml(state.season.display_name)}</span><b>${escapeHtml(state.season.game_version || "")}</b></div>
      <h1 class="${posterTitleClass(title)}">${escapeHtml(title)}</h1>
      <div class="lineup-poster-summary"><span>${units.length} 个单位</span><i></i><span>${posterTraitRows().length} 个激活羁绊</span><i></i><span>${selectedAugmentCount} 个强化符文</span></div>
    </header>
    <div class="lineup-poster-board-panel"><div class="lineup-poster-board-slot"></div></div>
    <section class="lineup-poster-insights">
      <section class="lineup-poster-traits-panel">
        <div class="lineup-poster-section-title"><span>SYNERGIES</span><strong>阵容羁绊</strong></div>
        <div class="lineup-poster-traits">${posterTraitHtml()}</div>
      </section>
      <section class="lineup-poster-augments-panel">
        <div class="lineup-poster-section-title"><span>AUGMENTS</span><strong>强化符文推荐</strong></div>
        <div class="lineup-poster-augments">${posterAugmentHtml()}</div>
      </section>
    </section>
    <footer class="lineup-poster-footer">
      <div class="lineup-poster-footer-line"></div>
      <div class="lineup-poster-brand"><img src="${UI_ROOT}/poster-brand.png" alt="" /><span><strong>金铲铲阵容库</strong></span></div>
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
  const fontSize = heading.classList.contains("is-very-long") ? 50 : heading.classList.contains("is-long") ? 61 : 72;
  await document.fonts?.load(`${fontSize}px "Source Han Serif SC Poster"`, title);
  const canvas = document.createElement("canvas");
  canvas.width = 1040;
  canvas.height = 122;
  const context = canvas.getContext("2d");
  context.font = `850 ${fontSize}px "Source Han Serif SC Poster", "Noto Serif SC", serif`;
  context.fillStyle = "#f6e3ad";
  context.textBaseline = "top";
  context.shadowColor = "rgba(0, 0, 0, .68)";
  context.shadowBlur = 20;
  context.shadowOffsetY = 5;
  const lineHeight = fontSize * 1.12;
  posterTitleLines(context, title, 1020).forEach((line, index) => context.fillText(line, 0, index * lineHeight, 1020));
  const image = document.createElement("img");
  image.className = "lineup-poster-title-image";
  image.src = canvas.toDataURL("image/png");
  image.alt = title;
  heading.replaceWith(image);
}

async function exportPortraitPoster() {
  if (!window.htmlToImage?.toPng) throw new Error("图片导出组件未加载");
  elements.posterExportDialog.close();
  const startedAt = beginExportProgress("海报正在导出");
  let poster = null;
  elements.exportPoster.disabled = true;
  elements.confirmExportPoster.disabled = true;
  try {
    const title = normalizedPosterTitle();
    poster = buildPosterCapture(title, state.posterChampionId);
    poster.classList.add("is-exporting");
    document.body.append(poster);
    await updateExportProgress("正在排版阵容海报", 20);
    await document.fonts?.ready;
    await updateExportProgress("正在绘制标题与背景", 42);
    await rasterizePosterTitle(poster);
    await preparePosterImages(poster);
    await updateExportProgress("正在合成高清海报", 68);
    const dataUrl = await window.htmlToImage.toPng(poster, {
      backgroundColor: "#0b0d12",
      cacheBust: true,
      pixelRatio: 1,
      skipFonts: true,
      width: POSTER_WIDTH,
      height: POSTER_HEIGHT,
      style: { position: "static", left: "auto", top: "auto", zIndex: "auto", transform: "none" },
    });
    await updateExportProgress("正在准备下载", 92);
    const link = document.createElement("a");
    link.download = `${state.season.season_id}-${safePosterFilename(title)}-poster.png`;
    link.href = dataUrl;
    link.click();
    await updateExportProgress("导出完成", 100);
    showToast("3:4 阵容海报已保存");
  } finally {
    poster?.remove();
    elements.exportPoster.disabled = !state.board.some(Boolean);
    elements.confirmExportPoster.disabled = false;
    await finishExportProgress(startedAt);
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
      <p class="skill-description">${richTextHtml(skill.description, skill.description_tokens)}</p>
      <div class="skill-values">${(skill.variables || []).map((variable) => `<div class="skill-value"><span>${escapeHtml(variable.label)}</span><span>${escapeHtml(Object.values(variable.values || {}).join(" / "))}</span></div>`).join("")}</div>` : '<p class="skill-description">暂无技能资料</p>'}
      ${hero.availability?.type === "unlock" ? `<div class="unlock-box"><img src="${UI_ROOT}/unlock.png" alt="" /><div><strong>解锁条件</strong><p>${escapeHtml(hero.availability.description || "满足赛季解锁条件")}</p></div></div>` : ""}
    </div>`;
  showPopover(anchor);
}

function showItemPopover(itemId, anchor) {
  const item = state.itemById.get(itemId);
  if (!item) return;
  const components = (item.recipe?.component_ids || []).map((id) => state.itemById.get(String(id))).filter(Boolean);
  const effects = item.effects.map((effect) => {
    if (typeof effect === "string") return richTextHtml(effect);
    const text = effect.description || effect.text || "";
    return text ? richTextHtml(text, effect.description_tokens || effect.text_tokens) : "";
  }).filter(Boolean);
  elements.popover.innerHTML = `<div class="item-detail">
    <div class="item-detail-heading"><img src="${escapeHtml(item.icon)}" alt="" /><div><h3>${escapeHtml(item.name)}</h3>${components.length ? `<div class="item-recipe">${components.map((component, index) => `${index ? "<b>+</b>" : ""}<img src="${escapeHtml(component.icon)}" alt="${escapeHtml(component.name)}" />`).join("")}</div>` : ""}</div></div>
    ${item.stats ? `<p class="item-stats">${escapeHtml(item.stats)}</p>` : ""}
    <p class="item-description">${[richTextHtml(item.description, item.descriptionTokens), ...effects].filter(Boolean).join("<br>") || "暂无装备说明"}</p>
  </div>`;
  showPopover(anchor);
}

function showAugmentPopover(augmentId, anchor) {
  const augment = state.augmentById.get(augmentId);
  if (!augment) return;
  elements.popover.innerHTML = `<div class="augment-detail augment-tier-${escapeHtml(augment.tier)}">
    <div class="augment-detail-heading"><img src="${escapeHtml(augment.icon)}" alt="" /><div><span>${escapeHtml(AUGMENT_TIER_LABELS[augment.tier] || augment.tierLabel)}</span><h3>${escapeHtml(augment.name)}</h3></div><b>${escapeHtml(augment.categoryLabel)}</b></div>
    <p>${richTextHtml(augment.description, augment.descriptionTokens)}</p>
    ${augment.appearanceStages.length
      ? `<div class="augment-detail-stages">${augment.appearanceStages.map((stage) => `<span>${escapeHtml(stage)}</span>`).join("")}</div>`
      : (augment.stageDataStatus === "unavailable" ? '<div class="augment-detail-stages is-unavailable">暂无可信出现时机数据</div>' : "")}
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
    ${trait.description ? `<p class="trait-detail-description">${richTextHtml(trait.description, trait.descriptionTokens)}</p>` : ""}
    <div class="trait-detail-tiers">${breakpoints.length ? breakpoints.map((point) => {
      const active = Number(point.min_units) <= count;
      return `<div class="trait-detail-tier ${active ? "is-active" : ""}">
        <strong>${escapeHtml(point.min_units)} 人</strong><span>${richTextHtml(point.effect || point.description || "", point.effect_tokens || point.description_tokens)}</span>
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
    if (location.hash.startsWith("#lineup=")) {
      history.replaceState(null, "", `${location.pathname}${location.search}`);
    }
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

elements.libraryModeTabs.forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.libraryMode === "augments" && !state.augments.length) return;
  state.libraryMode = button.dataset.libraryMode;
  renderLibraryMode();
}));

elements.augmentLibraryControls.addEventListener("click", (event) => {
  const button = event.target.closest("[data-augment-filter-key]");
  if (!button) return;
  const key = button.dataset.augmentFilterKey;
  const value = button.dataset.augmentFilterValue;
  state[key] = state[key] === value ? "all" : value;
  renderAugments();
});

elements.heroSearch.addEventListener("input", () => { state.heroSearch = elements.heroSearch.value; renderHeroes(); });
elements.itemSearch.addEventListener("input", () => { state.itemSearch = elements.itemSearch.value; renderItems(); });
elements.augmentSearch.addEventListener("input", () => { state.augmentSearch = elements.augmentSearch.value; renderAugments(); });
elements.heroGroups.addEventListener("click", (event) => {
  const button = event.target.closest("[data-hero-id]");
  if (button) addChampion(button.dataset.heroId);
});
elements.itemGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-item-id]");
  if (!button) return;
  state.selectedItemId = state.selectedItemId === button.dataset.itemId ? null : button.dataset.itemId;
  syncLibrarySelectionState();
});
elements.augmentGroups.addEventListener("click", (event) => {
  const button = event.target.closest("[data-augment-id]");
  if (button) toggleAugment(button.dataset.augmentId);
});
elements.selectedAugmentList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-augment-id]");
  if (button) toggleAugment(button.dataset.removeAugmentId);
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
  if (hero && hero.dataset.locked !== "true") state.dragging = { type: "hero", id: hero.dataset.heroId };
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
    addChampion(state.dragging.id, target);
  } else if (state.dragging.type === "item") equipItem(target, state.dragging.id);
  else if (state.dragging.type === "unit") moveUnit(state.dragging.index, target);
});

document.addEventListener("pointerover", (event) => {
  if (!state.hoverDetails) return;
  if (event.pointerType === "touch" || window.matchMedia("(hover: none)").matches) return;
  const hero = event.target.closest("[data-hero-id]");
  const item = event.target.closest("[data-item-id]");
  const trait = event.target.closest("[data-trait-id]");
  const augment = event.target.closest("[data-augment-id]");
  if (item) showItemPopover(item.dataset.itemId, item);
  else if (hero) showHeroPopover(hero.dataset.heroId, hero);
  else if (augment) showAugmentPopover(augment.dataset.augmentId, augment);
  else if (trait) showTraitPopover(trait.dataset.traitId, trait);
});
document.addEventListener("pointerout", (event) => {
  if (!event.target.closest("[data-hero-id], [data-item-id], [data-trait-id], [data-augment-id]")) return;
  const related = event.relatedTarget;
  if (related instanceof Element && related.closest("[data-hero-id], [data-item-id], [data-trait-id], [data-augment-id]") === event.target.closest("[data-hero-id], [data-item-id], [data-trait-id], [data-augment-id]")) return;
  hidePopover();
});

elements.showNames.addEventListener("change", () => {
  state.showNames = elements.showNames.checked;
  pushHistory();
  renderBoard();
  persist();
});
elements.hoverDetails.addEventListener("change", () => {
  state.hoverDetails = elements.hoverDetails.checked;
  if (!state.hoverDetails) hidePopover();
  localStorage.setItem(`${STORAGE_PREFIX}hover-details`, elements.hoverDetails.checked ? "on" : "off");
});
elements.undo.addEventListener("click", () => applyHistory(state.historyIndex - 1));
elements.redo.addEventListener("click", () => applyHistory(state.historyIndex + 1));
elements.reset.addEventListener("click", () => {
  if ((state.board.some(Boolean) || state.selectedAugmentIds.length) && !confirm("确认清空当前阵容？")) return;
  mutate(() => { state.board = Array(28).fill(null); state.selectedAugmentIds = []; });
});
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
  if (event.key === "Escape") { state.selectedItemId = null; setTraitFilterMenu(false); syncLibrarySelectionState(); hidePopover(); }
});

state.hoverDetails = localStorage.getItem(`${STORAGE_PREFIX}hover-details`) !== "off";
elements.hoverDetails.checked = state.hoverDetails;
window.lucide?.createIcons();
loadCatalog().catch((error) => {
  elements.seasonMeta.textContent = error.message;
  elements.heroGroups.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  showToast(error.message);
});
