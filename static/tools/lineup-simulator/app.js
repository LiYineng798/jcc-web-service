const BOARD_SLOT_COUNT = 28;
const BOARD_SCALE_MAX = 1.32;
const DRAG_MIME = "application/x-board-repro";
const COST_CLASS_BY_VALUE = {
  1: "cost-1",
  2: "cost-2",
  3: "cost-3",
  4: "cost-4",
  5: "cost-5",
};
const FALLBACK_PETS = [
  {
    id: "18406",
    name: "圣物",
    image: "assets/pets/18406.png",
    entityType: "pet",
  },
  {
    id: "18407",
    name: "羊咩咩 & 咩咩羊",
    image: "assets/pets/18407.png",
    entityType: "pet",
  },
  {
    id: "18408",
    name: "羊咩咩 & 咩咩羊",
    image: "assets/pets/18408.png",
    entityType: "pet",
  },
  {
    id: "18428",
    name: "暗星召唤物",
    image: "assets/pets/18428.png",
    entityType: "pet",
  },
];

const DEFAULT_SIMULATOR_DATA = {
  version: null,
  heroCostTabs: ["??", "1?", "2?", "3?", "4?", "5?"],
  equipTabs: ["??", "??", "???", "??", "??", "????", "???"],
  heroes: [],
  equips: [],
  traits: [],
  pets: FALLBACK_PETS,
};

let simulatorVersion = DEFAULT_SIMULATOR_DATA.version;
let heroCostTabs = DEFAULT_SIMULATOR_DATA.heroCostTabs;
let equipTabs = DEFAULT_SIMULATOR_DATA.equipTabs;
let heroes = DEFAULT_SIMULATOR_DATA.heroes;
let equips = DEFAULT_SIMULATOR_DATA.equips;
let traits = DEFAULT_SIMULATOR_DATA.traits;
let pets = DEFAULT_SIMULATOR_DATA.pets;

let heroByKey = new Map();
let equipById = new Map();
let petById = new Map();
const loadedProgressiveImagePaths = new Set();

function setSimulatorData(data) {
  simulatorVersion = data.version ?? null;
  heroCostTabs = data.heroCostTabs?.length ? data.heroCostTabs : DEFAULT_SIMULATOR_DATA.heroCostTabs;
  equipTabs = data.equipTabs?.length ? data.equipTabs : DEFAULT_SIMULATOR_DATA.equipTabs;
  heroes = data.heroes ?? [];
  equips = data.equips ?? [];
  traits = data.traits ?? [];
  pets = data.pets?.length ? data.pets : FALLBACK_PETS;

  heroByKey = new Map(heroes.map((hero) => [hero.key, hero]));
  equipById = new Map(equips.map((equip) => [equip.id, equip]));
  petById = new Map(pets.map((pet) => [pet.id, pet]));
}

async function fetchJsonData(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) {
    throw new Error(`??????????${path}`);
  }
  return response.json();
}

async function loadSimulatorData() {
  if (globalThis.LOCAL_SIMULATOR_DATA) {
    return {
      ...DEFAULT_SIMULATOR_DATA,
      ...globalThis.LOCAL_SIMULATOR_DATA,
      version: globalThis.LOCAL_SIMULATOR_DATA.version ?? null,
    };
  }

  const [version, tabs, loadedHeroes, loadedEquips, loadedTraits, loadedPets] = await Promise.all([
    fetchJsonData("data/version.json"),
    fetchJsonData("data/tabs.json"),
    fetchJsonData("data/heroes.json"),
    fetchJsonData("data/equips.json"),
    fetchJsonData("data/traits.json"),
    fetchJsonData("data/pets.json"),
  ]);

  return {
    version,
    heroCostTabs: tabs.heroCostTabs,
    equipTabs: tabs.equipTabs,
    heroes: loadedHeroes,
    equips: loadedEquips,
    traits: loadedTraits,
    pets: loadedPets,
  };
}

setSimulatorData(DEFAULT_SIMULATOR_DATA);

function createEmptyBoardSlots(count = BOARD_SLOT_COUNT) {
  return attachBoardMeta(Array.from({ length: count }, () => null), createBoardMeta());
}

function placeHeroOnBoard(slots, index, hero) {
  if (!isValidSlotIndex(index, slots.length) || !hero || hero.entityType === "pet") {
    return slots;
  }

  if (isPetBoardHero(slots[index])) {
    return slots;
  }

  const manualSlots = extractManualBoardSlots(slots);
  if (manualSlots[index]?.heroKey === hero.key || hasBoardHeroKey(manualSlots, hero.key, index)) {
    return slots;
  }

  const next = manualSlots.slice();
  next[index] = buildBoardHero(hero);
  return recomputeBoardSlots(withBoardMetaFrom(slots, next));
}

function autoPlaceHeroOnBoard(slots, hero) {
  const nextIndex = findNextOpenSlotIndex(slots);
  if (nextIndex === -1) {
    return slots;
  }

  return placeHeroOnBoard(slots, nextIndex, hero);
}

function moveHeroOnBoard(slots, fromIndex, toIndex) {
  if (
    !isValidSlotIndex(fromIndex, slots.length) ||
    !isValidSlotIndex(toIndex, slots.length) ||
    fromIndex === toIndex
  ) {
    return slots;
  }

  if (!isManualBoardHero(slots[fromIndex])) {
    return slots;
  }

  return moveBoardUnit(slots, fromIndex, toIndex);
}

function moveBoardUnit(slots, fromIndex, toIndex) {
  if (
    !isValidSlotIndex(fromIndex, slots.length) ||
    !isValidSlotIndex(toIndex, slots.length) ||
    fromIndex === toIndex ||
    !slots[fromIndex]
  ) {
    return slots;
  }

  const next = slots.slice();
  const movingUnit = next[fromIndex];
  next[fromIndex] = next[toIndex] ?? null;
  next[toIndex] = movingUnit;

  const nextMeta = cloneBoardMeta(slots);
  if (isPetBoardHero(next[fromIndex])) {
    nextMeta.summonPositionMemory.set(getRuntimeSummonKey(next[fromIndex]), fromIndex);
  }
  if (isPetBoardHero(next[toIndex])) {
    nextMeta.summonPositionMemory.set(getRuntimeSummonKey(next[toIndex]), toIndex);
  }

  return recomputeBoardSlots(attachBoardMeta(next, nextMeta));
}

function attachEquipToHero(slots, index, equip) {
  if (!isValidSlotIndex(index, slots.length) || !equip?.draggable || !slots[index] || isPetBoardHero(slots[index])) {
    return slots;
  }

  const manualSlots = extractManualBoardSlots(slots);
  const targetHero = manualSlots[index];
  if (targetHero.equips.length >= 3) {
    return slots;
  }

  if (equip.grantedTrait && heroHasTraitContribution(targetHero, equip.grantedTrait)) {
    return slots;
  }

  const next = manualSlots.slice();
  next[index] = {
    ...targetHero,
    equips: [...targetHero.equips, buildBoardEquip(equip)],
  };
  return recomputeBoardSlots(withBoardMetaFrom(slots, next));
}

function removeEquipFromHero(slots, index, equipIndex) {
  if (!isValidSlotIndex(index, slots.length) || !slots[index] || isPetBoardHero(slots[index])) {
    return slots;
  }

  const manualSlots = extractManualBoardSlots(slots);
  const targetHero = manualSlots[index];
  if (!targetHero?.equips?.[equipIndex]) {
    return slots;
  }

  const next = manualSlots.slice();
  next[index] = {
    ...targetHero,
    equips: targetHero.equips.filter((_, currentIndex) => currentIndex !== equipIndex),
  };
  return recomputeBoardSlots(withBoardMetaFrom(slots, next));
}

function removeHeroFromBoard(slots, index) {
  if (!isValidSlotIndex(index, slots.length) || !slots[index] || isPetBoardHero(slots[index])) {
    return slots;
  }

  const next = extractManualBoardSlots(slots);
  next[index] = null;
  return recomputeBoardSlots(withBoardMetaFrom(slots, next));
}

function resetBoardSlots(count = BOARD_SLOT_COUNT) {
  return createEmptyBoardSlots(count);
}

function summarizeBoardTraits(slots, traitCatalog) {
  const counts = new Map();
  const catalogByName = new Map((traitCatalog ?? []).map((trait) => [trait.name, trait]));
  const seenHeroKeys = new Set();

  for (const slot of slots) {
    if (!slot) {
      continue;
    }

    if (slot.heroKey && seenHeroKeys.has(slot.heroKey)) {
      continue;
    }

    if (slot.heroKey) {
      seenHeroKeys.add(slot.heroKey);
    }

    for (const traitName of collectHeroTraitContributions(slot)) {
      counts.set(traitName, (counts.get(traitName) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .map(([name, count]) => {
      const trait = catalogByName.get(name) ?? buildFallbackTrait(name);
      const levels = [...(trait.levels ?? [])].sort((left, right) => left.count - right.count || left.level - right.level);
      const activeLevel = getActiveTraitLevel(count, levels);
      const nextLevel = levels.find((level) => count < level.count) ?? null;
      const activationTarget = levels[0]?.count ?? 0;
      const progressRatio = activationTarget ? count / (activeLevel?.count ?? nextLevel?.count ?? activationTarget) : 0;

      return {
        ...trait,
        count,
        isActive: Boolean(activeLevel),
        activeLevel,
        nextLevel,
        nextTarget: nextLevel?.count ?? null,
        activationTarget,
        progressRatio,
      };
    })
    .sort(compareTraitSummaries);
}

function getTraitToneClass(summary) {
  if (!summary?.isActive) {
    return "tier-0";
  }

  const color = Number(summary.activeLevel?.color ?? 1);
  if (!Number.isFinite(color)) {
    return "tier-1";
  }

  return `tier-${Math.min(5, Math.max(1, color))}`;
}

function getTraitProgressDisplay(summary) {
  const levels = summary?.levels ?? [];
  const count = Number(summary?.count ?? 0);

  if (!summary?.isActive) {
    const nextTarget = Number(summary?.nextTarget ?? levels[0]?.count ?? count);
    return {
      kind: "inactive",
      text: `${count}/${nextTarget || count}`,
    };
  }

  const currentCount = Number(summary?.activeLevel?.count ?? levels[levels.length - 1]?.count ?? count);
  return {
    kind: levels.length > 1 ? "active" : "active-single",
    text: levels.length > 1 ? levels.map((level) => level.count).join(" > ") : `${currentCount}`,
    currentCount,
  };
}

function buildBoardHero(hero) {
  return {
    heroKey: hero.key,
    name: hero.name,
    cost: Number(hero.cost),
    image: hero.image,
    traits: [...(hero.traits ?? [])],
    equips: [],
    entityType: "hero",
    isAutoPlaced: false,
  };
}

function buildBoardEquip(equip) {
  return {
    id: equip.id,
    name: equip.name,
    type: equip.type,
    image: equip.image,
    grantedTrait: equip.grantedTrait ?? "",
  };
}

function buildBoardPet(pet, overrides) {
  return {
    heroKey: `pet-${pet.id}-${overrides.anchorKey}-${overrides.sequence}`,
    petId: pet.id,
    name: pet.name,
    cost: 0,
    image: pet.image,
    traits: [],
    equips: [],
    entityType: "pet",
    isAutoPlaced: true,
    ownerHeroKey: overrides.ownerHeroKey ?? "",
    ownerTraitName: overrides.ownerTraitName ?? "",
    anchorKey: overrides.anchorKey ?? pet.id,
    sequence: overrides.sequence ?? 0,
  };
}

function createBoardMeta() {
  return {
    summonPositionMemory: new Map(),
    summonSignature: "",
  };
}

function getBoardMeta(slots) {
  return slots?._boardMeta ?? createBoardMeta();
}

function attachBoardMeta(slots, meta) {
  Object.defineProperty(slots, "_boardMeta", {
    value: meta,
    configurable: true,
    enumerable: false,
    writable: true,
  });
  return slots;
}

function cloneBoardMeta(slots) {
  const meta = getBoardMeta(slots);
  return {
    summonPositionMemory: new Map(meta.summonPositionMemory),
    summonSignature: meta.summonSignature,
  };
}

function withBoardMetaFrom(sourceSlots, targetSlots) {
  return attachBoardMeta(targetSlots, cloneBoardMeta(sourceSlots));
}

function isPetBoardHero(slot) {
  return slot?.entityType === "pet";
}

function isManualBoardHero(slot) {
  return Boolean(slot) && !isPetBoardHero(slot);
}

function extractManualBoardSlots(slots) {
  return slots.map((slot) => (isManualBoardHero(slot) ? slot : null));
}

function recomputeBoardSlots(slots) {
  const manualSlots = extractManualBoardSlots(slots);
  const traitCounts = collectTraitCounts(manualSlots);
  const summonSpecs = collectAutoSummonSpecs(manualSlots, traitCounts);
  const previousMeta = cloneBoardMeta(slots);
  const nextSignature = buildSummonSignature(summonSpecs);
  const nextMemory = previousMeta.summonSignature === nextSignature ? previousMeta.summonPositionMemory : new Map();
  const nextSlots = placeSummonSpecs(manualSlots, summonSpecs, nextMemory);

  return attachBoardMeta(nextSlots, {
    summonPositionMemory: nextMemory,
    summonSignature: nextSignature,
  });
}

function collectTraitCounts(slots) {
  const counts = new Map();
  const seenHeroKeys = new Set();

  for (const slot of slots) {
    if (!slot) {
      continue;
    }

    if (slot.heroKey && seenHeroKeys.has(slot.heroKey)) {
      continue;
    }

    if (slot.heroKey) {
      seenHeroKeys.add(slot.heroKey);
    }

    for (const traitName of collectHeroTraitContributions(slot)) {
      counts.set(traitName, (counts.get(traitName) ?? 0) + 1);
    }
  }

  return counts;
}

function collectAutoSummonSpecs(slots, traitCounts) {
  const specs = [];
  const bulwarkAnchors = collectTraitAnchorIndices(slots, "暮光铁壁");
  const shepherdAnchors = collectTraitAnchorIndices(slots, "牧羊人");
  const darkStarAnchors = collectTraitAnchorIndices(slots, "暗星");
  const shepherdCount = traitCounts.get("牧羊人") ?? 0;
  const darkStarCount = traitCounts.get("暗星") ?? 0;

  if ((traitCounts.get("暮光铁壁") ?? 0) >= 1 && petById.has("18406")) {
    specs.push({
      petId: "18406",
      ownerHeroKey: slots[bulwarkAnchors[0]]?.heroKey ?? "",
      ownerTraitName: "暮光铁壁",
      anchorIndex: bulwarkAnchors[0] ?? -1,
      anchorKey: slots[bulwarkAnchors[0]]?.heroKey ?? "416",
      signatureTag: "416-1",
      priority: 1,
      sequence: 0,
    });
  }

  if (shepherdCount >= 3 && petById.has("18407")) {
    const shepherdPetId = shepherdCount >= 5 && petById.has("18408") ? "18408" : "18407";
    const shepherdTier = shepherdCount >= 7 ? 7 : shepherdCount >= 5 ? 5 : 3;
    specs.push({
      petId: shepherdPetId,
      ownerHeroKey: slots[shepherdAnchors[0]]?.heroKey ?? "",
      ownerTraitName: "牧羊人",
      anchorIndex: shepherdAnchors[0] ?? -1,
      anchorKey: slots[shepherdAnchors[0]]?.heroKey ?? "319-a",
      signatureTag: `319-${shepherdTier}`,
      priority: 2,
      sequence: 0,
    });
  }

  if (darkStarCount >= 6 && petById.has("18428")) {
    const firstAnchor = darkStarAnchors[0] ?? -1;
    const secondAnchor = darkStarAnchors[1] ?? firstAnchor;
    const darkStarTier = darkStarCount >= 9 ? 9 : 6;
    specs.push({
      petId: "18428",
      ownerHeroKey: slots[firstAnchor]?.heroKey ?? "",
      ownerTraitName: "暗星",
      anchorIndex: firstAnchor,
      anchorKey: "403-a",
      signatureTag: `403-${darkStarTier}`,
      priority: 3,
      sequence: 0,
    });
    specs.push({
      petId: "18428",
      ownerHeroKey: slots[secondAnchor]?.heroKey ?? "",
      ownerTraitName: "暗星",
      anchorIndex: secondAnchor,
      anchorKey: "403-b",
      signatureTag: `403-${darkStarTier}`,
      priority: 3,
      sequence: 1,
    });
  }

  return specs.sort((left, right) => left.priority - right.priority || left.sequence - right.sequence);
}

function collectTraitAnchorIndices(slots, traitName) {
  return slots
    .map((slot, index) => (collectHeroTraitContributions(slot).has(traitName) ? index : -1))
    .filter((index) => index >= 0);
}

function buildSummonSignature(summonSpecs) {
  return summonSpecs.map((spec) => getSummonSignatureKey(spec)).join("|");
}

function getSummonStableKey(spec) {
  return `${spec.petId}:${spec.ownerTraitName || spec.ownerHeroKey}:${spec.sequence}`;
}

function getSummonSignatureKey(spec) {
  return `${getSummonStableKey(spec)}:${spec.signatureTag ?? ""}`;
}

function getRuntimeSummonKey(slot) {
  return `${slot.petId}:${slot.ownerTraitName || slot.ownerHeroKey}:${slot.sequence ?? 0}`;
}

function placeSummonSpecs(manualSlots, summonSpecs, summonPositionMemory) {
  const next = manualSlots.slice();

  for (const spec of summonSpecs) {
    const stableKey = getSummonStableKey(spec);
    const rememberedIndex = summonPositionMemory.get(stableKey) ?? -1;
    const targetIndex = findSummonPlacementIndex(next, spec.anchorIndex, rememberedIndex);
    if (targetIndex === -1) {
      continue;
    }

    const pet = petById.get(spec.petId);
    if (!pet) {
      continue;
    }

    next[targetIndex] = buildBoardPet(pet, spec);
    summonPositionMemory.set(stableKey, targetIndex);
  }

  return next;
}

function findSummonPlacementIndex(slots, anchorIndex, rememberedIndex = -1) {
  if (isValidSlotIndex(rememberedIndex, slots.length) && slots[rememberedIndex] === null) {
    return rememberedIndex;
  }

  const preferredIndices = getNeighborPreference(anchorIndex, slots.length);

  for (const index of preferredIndices) {
    if (slots[index] === null) {
      return index;
    }
  }

  return findNextOpenSlotIndex(slots);
}

function getNeighborPreference(anchorIndex, slotCount) {
  if (!isValidSlotIndex(anchorIndex, slotCount)) {
    return [];
  }

  const row = Math.floor(anchorIndex / 7);
  const col = anchorIndex % 7;
  const candidates = [];

  for (let rowOffset = -1; rowOffset <= 1; rowOffset += 1) {
    for (let colOffset = -1; colOffset <= 1; colOffset += 1) {
      if (rowOffset === 0 && colOffset === 0) {
        continue;
      }

      const nextRow = row + rowOffset;
      const nextCol = col + colOffset;
      if (nextRow < 0 || nextRow >= 4 || nextCol < 0 || nextCol >= 7) {
        continue;
      }

      const distance = Math.abs(rowOffset) + Math.abs(colOffset);
      candidates.push({
        index: nextRow * 7 + nextCol,
        distance,
      });
    }
  }

  return candidates
    .sort((left, right) => left.distance - right.distance || left.index - right.index)
    .map((item) => item.index);
}

function findNextOpenSlotIndex(slots) {
  return slots.findIndex((slot) => slot === null);
}

function hasBoardHeroKey(slots, heroKey, ignoreIndex = -1) {
  return slots.some((slot, index) => index !== ignoreIndex && slot?.heroKey === heroKey);
}

function collectHeroTraitContributions(hero) {
  const traitNames = new Set(hero?.traits ?? []);

  for (const equip of hero?.equips ?? []) {
    if (equip?.grantedTrait) {
      traitNames.add(equip.grantedTrait);
    }
  }

  return traitNames;
}

function heroHasTraitContribution(hero, traitName) {
  return collectHeroTraitContributions(hero).has(traitName);
}

function isValidSlotIndex(index, length) {
  return Number.isInteger(index) && index >= 0 && index < length;
}

function normalizeText(value) {
  return String(value ?? "").trim().toLowerCase();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getHeroCostClass(cost) {
  return COST_CLASS_BY_VALUE[Number(cost)] ?? "cost-1";
}

function getBlurImagePath(imagePath) {
  const normalizedPath = String(imagePath ?? "").replace(/^\.\//, "");
  return normalizedPath ? `blur/${normalizedPath}` : "";
}

function getProgressiveImageStyle(imagePath) {
  const blurPath = getBlurImagePath(imagePath);
  return blurPath ? ` style="--blur-image: url('${blurPath}')"` : "";
}

function getProgressiveImageCacheKey(imagePath) {
  return String(imagePath ?? "").replace(/^\.\//, "");
}

function isProgressiveImageLoaded(imagePath) {
  const cacheKey = getProgressiveImageCacheKey(imagePath);
  return Boolean(cacheKey) && loadedProgressiveImagePaths.has(cacheKey);
}

function getProgressiveShellClass(imagePath) {
  return `progressive-image-shell${isProgressiveImageLoaded(imagePath) ? " is-loaded" : ""}`;
}

function getProgressiveImageClass(imagePath) {
  return `progressive-image${isProgressiveImageLoaded(imagePath) ? " is-loaded" : ""}`;
}

function markProgressiveImageLoaded(image) {
  loadedProgressiveImagePaths.add(getProgressiveImageCacheKey(image.getAttribute("src")));
  image.classList.add("is-loaded");
  image.closest(".progressive-image-shell")?.classList.add("is-loaded");
}

function hydrateProgressiveImages(refs) {
  refs.root?.querySelectorAll("[data-progressive-image]").forEach((image) => {
    if (image instanceof HTMLImageElement && image.complete) {
      markProgressiveImageLoaded(image);
    }
  });
}

function buildFallbackTrait(name) {
  return {
    id: name,
    name,
    type: "",
    image: "",
    levels: [],
  };
}

function getActiveTraitLevel(count, levels) {
  let activeLevel = null;

  for (const level of levels) {
    if (count >= level.count) {
      activeLevel = level;
      continue;
    }

    break;
  }

  return activeLevel;
}

function compareTraitSummaries(left, right) {
  const uniqueDelta = Number(isUniqueTraitSummary(right)) - Number(isUniqueTraitSummary(left));
  if (uniqueDelta !== 0) {
    return uniqueDelta;
  }

  if (left.isActive !== right.isActive) {
    return Number(right.isActive) - Number(left.isActive);
  }

  if (left.isActive && right.isActive) {
    const activeThresholdDelta = (right.activeLevel?.count ?? 0) - (left.activeLevel?.count ?? 0);
    if (activeThresholdDelta !== 0) {
      return activeThresholdDelta;
    }
  } else {
    const progressDelta = right.progressRatio - left.progressRatio;
    if (progressDelta !== 0) {
      return progressDelta;
    }
  }

  const countDelta = right.count - left.count;
  if (countDelta !== 0) {
    return countDelta;
  }

  return left.name.localeCompare(right.name, "zh-Hans-CN");
}

function isUniqueTraitSummary(summary) {
  return (summary?.levels ?? []).some((level) => Number(level.color) === 5);
}

if (typeof document !== "undefined") {
  void initSimulator();
}

async function initSimulator() {
  const refs = getRefs();
  if (!refs.root) {
    return;
  }

  try {
    const data = await loadSimulatorData();
    setSimulatorData(data);
  } catch (error) {
    console.error(error);
    setSimulatorData(DEFAULT_SIMULATOR_DATA);
  }

  const state = {
    activePanel: "heroes",
    heroSearch: "",
    heroCost: heroCostTabs[0],
    equipSearch: "",
    equipTab: "成装",
    showBoardNames: true,
    boardSlots: createEmptyBoardSlots(),
    dragPayload: null,
    activeDropSlot: null,
    selectedEquipId: null,
  };

  renderHeroCostFilters(refs, state);
  renderEquipTabs(refs, state);
  renderBoardActionButtons(refs, state);
  renderPanels(refs, state);
  renderHeroList(refs, state);
  renderEquipList(refs, state);
  renderBoardState(refs, state);
  syncBattleCardScale(refs);
  bindEvents(refs, state);
  hydrateProgressiveImages(refs);
}

function getRefs() {
  return {
    root: document.getElementById("simulator-root"),
    heroTabButton: document.getElementById("panel-tab-heroes"),
    equipTabButton: document.getElementById("panel-tab-equips"),
    heroPanel: document.getElementById("heroes-panel"),
    equipPanel: document.getElementById("equips-panel"),
    heroSearch: document.getElementById("hero-search"),
    equipSearch: document.getElementById("equip-search"),
    heroCostFilters: document.getElementById("hero-cost-filters"),
    equipTabs: document.getElementById("equip-type-tabs"),
    heroList: document.getElementById("hero-list"),
    equipList: document.getElementById("equip-list"),
    battleCard: document.querySelector(".battle-card"),
    battleCardBoardArea: document.getElementById("battle-card-board-area"),
    battleCardBoardScale: document.getElementById("battle-card-board-scale"),
    boardGrid: document.getElementById("board-grid"),
    traitList: document.getElementById("trait-list"),
    trashZone: document.getElementById("trash-dropzone"),
    toggleNameButton: document.getElementById("toggle-name-button"),
    resetButton: document.getElementById("reset-board-button"),
  };
}

function bindEvents(refs, state) {
  refs.root?.addEventListener("load", (event) => {
    const image = event.target;
    if (image instanceof HTMLImageElement && image.matches("[data-progressive-image]")) {
      markProgressiveImageLoaded(image);
    }
  }, true);

  refs.heroTabButton?.addEventListener("click", () => {
    state.activePanel = "heroes";
    clearSelectedEquip(refs, state);
    renderPanels(refs, state);
  });

  refs.equipTabButton?.addEventListener("click", () => {
    state.activePanel = "equips";
    renderPanels(refs, state);
  });

  refs.heroSearch.addEventListener("input", (event) => {
    state.heroSearch = event.target.value;
    renderHeroList(refs, state);
  });

  refs.equipSearch.addEventListener("input", (event) => {
    state.equipSearch = event.target.value;
    renderEquipList(refs, state);
  });

  refs.heroCostFilters.addEventListener("click", (event) => {
    const button = event.target.closest("[data-hero-cost]");
    if (!button) {
      return;
    }

    state.heroCost = button.dataset.heroCost;
    renderHeroCostFilters(refs, state);
    renderHeroList(refs, state);
  });

  refs.equipTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-equip-tab]");
    if (!button) {
      return;
    }

    state.equipTab = button.dataset.equipTab;
    clearSelectedEquip(refs, state);
    renderEquipTabs(refs, state);
    renderEquipList(refs, state);
  });

  refs.heroList.addEventListener("dragstart", (event) => {
    const card = event.target.closest("[data-hero-key]");
    if (!card) {
      return;
    }

    setDragPayload(event, state, {
      kind: "hero-pool",
      heroKey: card.dataset.heroKey,
    });
  });

  refs.heroList.addEventListener("click", (event) => {
    const card = event.target.closest("[data-hero-key]");
    if (!card) {
      return;
    }

    const hero = heroByKey.get(card.dataset.heroKey);
    if (!hero) {
      return;
    }

    clearSelectedEquip(refs, state);
    state.boardSlots = autoPlaceHeroOnBoard(state.boardSlots, hero);
    renderBoardState(refs, state);
  });

  refs.equipList.addEventListener("dragstart", (event) => {
    const card = event.target.closest("[data-equip-id]");
    if (!card || card.getAttribute("draggable") !== "true") {
      return;
    }

    clearSelectedEquip(refs, state);
    setDragPayload(event, state, {
      kind: "equip-pool",
      equipId: card.dataset.equipId,
    });
  });

  refs.equipList.addEventListener("click", (event) => {
    const card = event.target.closest("[data-equip-id]");
    if (!card || card.getAttribute("draggable") !== "true") {
      return;
    }

    selectEquipForClick(refs, state, card.dataset.equipId);
  });

  refs.boardGrid.addEventListener("click", (event) => {
    const removeEquipButton = event.target.closest("[data-remove-equip-index]");
    if (removeEquipButton) {
      removeEquipFromBoardSlot(
        refs,
        state,
        Number(removeEquipButton.dataset.boardSlot),
        Number(removeEquipButton.dataset.removeEquipIndex),
      );
      return;
    }

    const removeHeroButton = event.target.closest("[data-remove-board-slot]");
    if (removeHeroButton) {
      removeHeroFromBoardSlot(refs, state, Number(removeHeroButton.dataset.removeBoardSlot));
      return;
    }

    const slot = event.target.closest(".lineup-item");
    if (!slot) {
      return;
    }

    applySelectedEquipToBoardSlot(refs, state, Number(slot.dataset.slotIndex));
  });

  refs.boardGrid.addEventListener("dragstart", (event) => {
    const card = event.target.closest("[data-board-slot]");
    if (!card) {
      return;
    }

    setDragPayload(event, state, {
      kind: "hero-board",
      fromIndex: Number(card.dataset.boardSlot),
    });
  });

  refs.boardGrid.addEventListener("dragover", (event) => {
    const slot = event.target.closest(".lineup-item");
    if (!slot || !state.dragPayload) {
      return;
    }

    event.preventDefault();
    highlightSlot(state, slot);
  });

  refs.boardGrid.addEventListener("drop", (event) => {
    const slot = event.target.closest(".lineup-item");
    if (!slot) {
      return;
    }

    event.preventDefault();
    const payload = getDragPayload(event, state);
    clearSlotHighlights(refs, state);

    if (!payload) {
      return;
    }

    state.boardSlots = applyBoardDrop(state.boardSlots, Number(slot.dataset.slotIndex), payload);
    renderBoardState(refs, state);
  });

  refs.boardGrid.addEventListener("dragleave", (event) => {
    const slot = event.target.closest(".lineup-item");
    if (!slot) {
      return;
    }

    if (!slot.contains(event.relatedTarget)) {
      slot.classList.remove("is-drop-target");
    }
  });

  refs.boardGrid.addEventListener("dragend", () => {
    state.dragPayload = null;
    clearSlotHighlights(refs, state);
    refs.trashZone.classList.remove("is-trash-target");
  });

  refs.trashZone.addEventListener("dragover", (event) => {
    const payload = state.dragPayload;
    if (!payload || payload.kind !== "hero-board") {
      return;
    }

    if (isPetBoardHero(state.boardSlots[payload.fromIndex])) {
      return;
    }

    event.preventDefault();
    refs.trashZone.classList.add("is-trash-target");
  });

  refs.trashZone.addEventListener("dragleave", () => {
    refs.trashZone.classList.remove("is-trash-target");
  });

  refs.trashZone.addEventListener("drop", (event) => {
    event.preventDefault();
    const payload = getDragPayload(event, state);
    refs.trashZone.classList.remove("is-trash-target");
    clearSlotHighlights(refs, state);

    if (!payload || payload.kind !== "hero-board") {
      return;
    }

    if (isPetBoardHero(state.boardSlots[payload.fromIndex])) {
      return;
    }

    state.boardSlots = removeHeroFromBoard(state.boardSlots, payload.fromIndex);
    renderBoardState(refs, state);
  });

  refs.toggleNameButton.addEventListener("click", () => {
    state.showBoardNames = !state.showBoardNames;
    renderBoardActionButtons(refs, state);
    renderBoardState(refs, state);
  });

  refs.resetButton.addEventListener("click", () => {
    clearSelectedEquip(refs, state);
    state.boardSlots = resetBoardSlots(state.boardSlots.length);
    renderBoardState(refs, state);
  });

  window.addEventListener("resize", () => {
    syncBattleCardScale(refs);
  });

  document.addEventListener("drop", () => {
    state.dragPayload = null;
    clearSlotHighlights(refs, state);
    refs.trashZone.classList.remove("is-trash-target");
  });


}

function getSelectedEquip(state) {
  return state.selectedEquipId ? equipById.get(state.selectedEquipId) ?? null : null;
}

function renderSelectedEquipState(refs, state) {
  refs.equipList.querySelectorAll("[data-equip-id]").forEach((card) => {
    const selected = Boolean(state.selectedEquipId) && card.dataset.equipId === state.selectedEquipId;
    card.classList.toggle("is-selected-for-click", selected);
    card.setAttribute("aria-pressed", String(selected));
  });

  const hasSelectedEquip = Boolean(getSelectedEquip(state));
  refs.boardGrid.querySelectorAll(".lineup-item").forEach((slot, index) => {
    const hero = state.boardSlots[index];
    slot.classList.toggle("is-click-target", hasSelectedEquip && Boolean(hero) && !isPetBoardHero(hero));
  });
}

function selectEquipForClick(refs, state, equipId) {
  const equip = equipById.get(equipId);
  state.selectedEquipId = equip?.draggable ? equip.id : null;
  renderSelectedEquipState(refs, state);
}

function clearSelectedEquip(refs, state) {
  state.selectedEquipId = null;
  renderSelectedEquipState(refs, state);
}

function applySelectedEquipToBoardSlot(refs, state, slotIndex) {
  const equip = getSelectedEquip(state);
  if (!equip) {
    return;
  }

  const before = state.boardSlots;
  state.boardSlots = attachEquipToHero(state.boardSlots, slotIndex, equip);
  if (state.boardSlots !== before) {
    clearSelectedEquip(refs, state);
  }
  renderBoardState(refs, state);
}

function removeHeroFromBoardSlot(refs, state, slotIndex) {
  clearSelectedEquip(refs, state);
  state.boardSlots = removeHeroFromBoard(state.boardSlots, slotIndex);
  renderBoardState(refs, state);
}

function removeEquipFromBoardSlot(refs, state, slotIndex, equipIndex) {
  clearSelectedEquip(refs, state);
  state.boardSlots = removeEquipFromHero(state.boardSlots, slotIndex, equipIndex);
  renderBoardState(refs, state);
}

function setDragPayload(event, state, payload) {
  state.dragPayload = payload;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData(DRAG_MIME, JSON.stringify(payload));
  event.dataTransfer.setData("text/plain", JSON.stringify(payload));
}

function getDragPayload(event, state) {
  const raw =
    event.dataTransfer.getData(DRAG_MIME) ||
    event.dataTransfer.getData("text/plain");

  if (!raw) {
    return state.dragPayload;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return state.dragPayload;
  }
}

function applyBoardDrop(boardSlots, slotIndex, payload) {
  if (payload.kind === "hero-pool") {
    return placeHeroOnBoard(boardSlots, slotIndex, heroByKey.get(payload.heroKey));
  }

  if (payload.kind === "hero-board") {
    return moveBoardUnit(boardSlots, payload.fromIndex, slotIndex);
  }

  if (payload.kind === "equip-pool") {
    return attachEquipToHero(boardSlots, slotIndex, equipById.get(payload.equipId));
  }

  return boardSlots;
}

function renderPanels(refs, state) {
  const hasPanelSwitcher = Boolean(refs.heroTabButton && refs.equipTabButton);
  const heroesActive = state.activePanel === "heroes";
  const equipsActive = state.activePanel === "equips";

  if (hasPanelSwitcher) {
    refs.heroPanel.hidden = !heroesActive;
    refs.equipPanel.hidden = !equipsActive;
    refs.heroTabButton.classList.toggle("is-active", heroesActive);
    refs.equipTabButton.classList.toggle("is-active", equipsActive);
    return;
  }

  refs.heroPanel.hidden = false;
  refs.equipPanel.hidden = false;
}

function renderHeroCostFilters(refs, state) {
  refs.heroCostFilters.innerHTML = heroCostTabs
    .map(
      (tab) => `
        <button
          type="button"
          class="filter-chip ${tab === state.heroCost ? "is-active" : ""}"
          data-hero-cost="${tab}"
        >
          ${tab}
        </button>
      `,
    )
    .join("");
}

function renderEquipTabs(refs, state) {
  refs.equipTabs.innerHTML = equipTabs
    .map(
      (tab) => `
        <button
          type="button"
          class="filter-chip ${tab === state.equipTab ? "is-active" : ""}"
          data-equip-tab="${tab}"
        >
          ${tab}
        </button>
      `,
    )
    .join("");
}

function renderBoardActionButtons(refs, state) {
  refs.toggleNameButton.textContent = state.showBoardNames ? "隐藏名字" : "显示名字";
  refs.toggleNameButton.classList.toggle("is-active", state.showBoardNames);
  refs.toggleNameButton.setAttribute("aria-pressed", String(state.showBoardNames));
}

function renderBoardState(refs, state) {
  renderBoard(refs, state);
  renderTraitList(refs, state);
  renderSelectedEquipState(refs, state);
  syncBattleCardScale(refs);
}

function renderHeroList(refs, state) {
  const query = normalizeText(state.heroSearch);
  const filtered = heroes.filter((hero) => {
    const matchCost = state.heroCost === "全部" || hero.costLabel === state.heroCost;
    const matchQuery = !query || normalizeText(hero.searchText).includes(query);
    return matchCost && matchQuery;
  });

  refs.heroList.innerHTML = filtered.length
    ? filtered
        .map(
          (hero) => `
            <article
              class="pool-card hero-card ${getHeroCostClass(hero.cost)}"
              draggable="true"
              data-hero-key="${hero.key}"
              title="${hero.name} | ${hero.traits.join(" / ")}"
            >
              <div class="pool-card-pic-box ${getProgressiveShellClass(hero.image)}"${getProgressiveImageStyle(hero.image)}>
                <img class="pool-card-pic ${getProgressiveImageClass(hero.image)}" src="${hero.image}" alt="${hero.name}" loading="lazy" decoding="async" fetchpriority="low" data-progressive-image draggable="false" />
              </div>
              <div class="pool-card-name">${hero.name}</div>
              <div class="pool-card-meta">${hero.traits.join(" / ")}</div>
            </article>
          `,
        )
        .join("")
    : `<div class="empty-state">没有匹配的弈子</div>`;
}

function renderEquipList(refs, state) {
  const query = normalizeText(state.equipSearch);
  const filtered = equips.filter((equip) => {
    const matchTab = equip.type === state.equipTab;
    const matchQuery = !query || normalizeText(equip.searchText).includes(query);
    return matchTab && matchQuery;
  });

  refs.equipList.innerHTML = filtered.length
    ? filtered
        .map(
          (equip) => `
            <article
              class="pool-card equip-card ${equip.draggable ? "" : "is-disabled"} ${state.selectedEquipId === equip.id ? "is-selected-for-click" : ""}"
              ${equip.draggable ? 'draggable="true"' : ""}
              aria-pressed="${state.selectedEquipId === equip.id ? "true" : "false"}"
              data-equip-id="${equip.id}"
              title="${equip.name}"
            >
              <div class="pool-card-pic-box ${getProgressiveShellClass(equip.image)}"${getProgressiveImageStyle(equip.image)}>
                <img class="pool-card-pic ${getProgressiveImageClass(equip.image)}" src="${equip.image}" alt="${equip.name}" loading="lazy" decoding="async" fetchpriority="low" data-progressive-image draggable="false" />
              </div>
              <div class="pool-card-name">${equip.name}</div>
              <div class="pool-card-meta">${equip.type}${equip.draggable ? "" : " · 仅展示"}</div>
            </article>
          `,
        )
        .join("")
    : `<div class="empty-state">没有匹配的装备</div>`;

  renderSelectedEquipState(refs, state);
}

function renderBoard(refs, state) {
  const slots = refs.boardGrid.querySelectorAll(".lineup-item");

  slots.forEach((slot, index) => {
    slot.dataset.slotIndex = String(index);
    const lineup = slot.querySelector(".lineup");
    const hero = state.boardSlots[index];

    slot.classList.toggle("lineup-item--occupied", Boolean(hero));

    if (!hero) {
      lineup.innerHTML = "";
      return;
    }

    const isPet = isPetBoardHero(hero);

    lineup.innerHTML = `
      <article
        class="board-unit ${isPet ? "board-unit--pet" : ""} ${getHeroCostClass(hero.cost)}"
        draggable="true"
        data-board-slot="${index}"
        title="${hero.name}"
      >
        ${isPet ? "" : `<button class="board-unit-remove" type="button" data-remove-board-slot="${index}" aria-label="删除${escapeHtml(hero.name)}">×</button>`}
        <div class="board-unit-frame ${getProgressiveShellClass(hero.image)} ${isPet ? "board-unit-frame--pet" : ""}"${getProgressiveImageStyle(hero.image)}>
          <img class="board-unit-image ${getProgressiveImageClass(hero.image)}" src="${hero.image}" alt="${hero.name}" data-progressive-image draggable="false" />
        </div>
        <div class="board-unit-name ${state.showBoardNames ? "" : "is-hidden"}">${hero.name}</div>
        <div class="board-unit-equips">
          ${isPet
            ? ""
            : hero.equips
            .map(
              (equip, equipIndex) => `
                <button class="board-unit-equip" type="button" title="移除${equip.name}" data-board-slot="${index}" data-remove-equip-index="${equipIndex}" aria-label="移除${equip.name}">
                  <span class="board-unit-equip-image-shell ${getProgressiveShellClass(equip.image)}"${getProgressiveImageStyle(equip.image)}><img class="${getProgressiveImageClass(equip.image)}" src="${equip.image}" alt="${equip.name}" loading="lazy" decoding="async" fetchpriority="low" data-progressive-image draggable="false" /></span>
                </button>
              `,
            )
            .join("")}
        </div>
      </article>
    `;
  });
}

function renderTraitList(refs, state) {
  const summary = summarizeBoardTraits(state.boardSlots, traits);

  refs.traitList.innerHTML = summary.length
    ? summary
        .map((trait) => {
          const toneClass = getTraitToneClass(trait);
          const progressDisplay = getTraitProgressDisplay(trait);
          const titleText = `${trait.name} | ${trait.count} | ${progressDisplay.text}`;
          const progressMarkup = trait.isActive
            ? (trait.levels ?? [])
                .map((level, index, levels) => {
                  const tokenClass =
                    level.count === progressDisplay.currentCount
                      ? "trait-progress-token is-current"
                      : level.count < (progressDisplay.currentCount ?? 0)
                        ? "trait-progress-token is-passed"
                        : "trait-progress-token";
                  const separator = index < levels.length - 1 ? '<span class="trait-progress-separator">&gt;</span>' : "";

                  return `<span class="${tokenClass}">${level.count}</span>${separator}`;
                })
                .join("")
            : `<span class="trait-progress-text">${progressDisplay.text}</span>`;

          return `
            <article class="trait-row ${toneClass} ${trait.isActive ? "is-active" : "is-inactive"}" title="${titleText}">
              <div class="trait-badge-shell">
                <div class="trait-badge">
                  <img class="trait-badge-icon" src="${trait.image}" alt="${trait.name}" draggable="false" />
                </div>
              </div>
              <div class="trait-row-count">${trait.count}</div>
              <div class="trait-row-body">
                <div class="trait-row-name">${trait.name}</div>
                <div class="trait-row-progress">${progressMarkup}</div>
              </div>
            </article>
          `;
        })
        .join("")
    : `<div class="trait-empty-state">上场弈子后显示羁绊</div>`;
}

function highlightSlot(state, slot) {
  if (state.activeDropSlot && state.activeDropSlot !== slot) {
    state.activeDropSlot.classList.remove("is-drop-target");
  }

  state.activeDropSlot = slot;
  slot.classList.add("is-drop-target");
}

function clearSlotHighlights(refs, state) {
  refs.boardGrid.querySelectorAll(".lineup-item.is-drop-target").forEach((slot) => {
    slot.classList.remove("is-drop-target");
  });
  state.activeDropSlot = null;
}

function syncBattleCardScale(refs) {
  if (!refs.battleCardBoardArea || !refs.battleCardBoardScale) {
    return;
  }

  refs.battleCardBoardScale.style.transform = "translate(-50%, -50%) scale(1)";

  const areaRect = refs.battleCardBoardArea.getBoundingClientRect();
  const boardRect = refs.battleCardBoardScale.getBoundingClientRect();
  if (!areaRect.width || !areaRect.height || !boardRect.width || !boardRect.height) {
    return;
  }

  const scale = Math.min(areaRect.width / boardRect.width, areaRect.height / boardRect.height, BOARD_SCALE_MAX);
  refs.battleCardBoardScale.style.transform = `translate(-50%, -50%) scale(${scale})`;
}

