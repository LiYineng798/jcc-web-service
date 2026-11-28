/* Population-bounded recommendations. Only legal teams enter the result list. */
const GOAL = 9;
const RESULT_LIMIT = 6;
const BEAM_WIDTH = 1400;

function solve(catalog, options, assignEmblems) {
  const { population, required, excluded, excludedCosts, excludeUnlocks, emblems } = options;
  const thresholds = catalog.traits.map(t => t.threshold);
  const indexes = new Map(catalog.traits.map((t, i) => [t.id, i]));
  const pool = catalog.heroes.map(hero => ({
    ...hero,
    indexes: hero.traits.map(id => indexes.get(id)),
    traits: Object.fromEntries(hero.traits.map(id => [id, 1])),
  }));
  const forced = pool.filter(h => required.includes(h.id));
  const choices = pool.filter(h => !required.includes(h.id) && !excluded.includes(h.id)
    && !excludedCosts.includes(h.cost) && !(excludeUnlocks && h.unlock));
  const akaliForm = id => id === 919952 || id === 919953;
  if (forced.filter(h => akaliForm(h.id)).length > 1) throw Error('两种阿卡丽形态只能选择一种。');
  if (forced.reduce((sum, h) => sum + h.slots, 0) > population) throw Error('必选弈子超出人口上限。');
  if (emblems.length > population * 3) throw Error('纹章数量超出可用装备栏。');

  function add(state, hero, next) {
    const counts = state.counts.slice();
    let progress = state.progress;
    let active = state.active;
    for (const i of hero.indexes) {
      counts[i]++;
      if (counts[i] <= thresholds[i]) progress += 1 / thresholds[i];
      if (counts[i] === thresholds[i]) active++;
    }
    return { team: [...state.team, hero], next, counts, progress, active,
      population: state.population + hero.slots, cost: state.cost + hero.cost,
      hasAkali: state.hasAkali || akaliForm(hero.id) };
  }

  const counts = new Uint8Array(thresholds.length);
  for (const id of emblems) counts[indexes.get(id)]++;
  let initial = { team: [], next: 0, population: 0, cost: 0, hasAkali: false, counts,
    progress: thresholds.reduce((n, threshold, i) => n + Math.min(1, counts[i] / threshold), 0),
    active: thresholds.filter((threshold, i) => counts[i] >= threshold).length };
  for (const hero of forced) initial = add(initial, hero, 0);

  const partial = Array.from({ length: population + 1 }, () => []);
  const matches = Array.from({ length: population + 1 }, () => []);
  const rank = (a, b) => b.active - a.active || b.progress - a.progress || a.cost - b.cost || a.next - b.next;
  function keep(state) {
    if (state.active >= GOAL && state.team.length) {
      const slots = matches[state.population];
      if (slots.length === RESULT_LIMIT && state.cost >= slots.at(-1).cost) return;
      const assignments = assignEmblems(state.team, emblems);
      if (assignments) {
        slots.push({ heroes: state.team.map(h => h.id), population: state.population, cost: state.cost,
          traits: catalog.traits.filter((t, i) => state.counts[i] >= thresholds[i]).map(t => t.id), assignments });
        slots.sort((a, b) => a.cost - b.cost);
        if (slots.length > RESULT_LIMIT) slots.pop();
        return;
      }
    }
    if (state.population === population || state.next === choices.length) return;
    const bucket = partial[state.population];
    bucket.push(state);
    if (bucket.length >= BEAM_WIDTH * 3) {
      bucket.sort(rank);
      bucket.length = BEAM_WIDTH;
    }
  }

  keep(initial);
  const results = [];
  for (let n = initial.population; n <= population; n++) {
    results.push(...matches[n].slice(0, RESULT_LIMIT - results.length));
    if (results.length === RESULT_LIMIT) break;
    for (const state of partial[n].sort(rank).slice(0, BEAM_WIDTH)) {
      for (let i = state.next; i < choices.length; i++) {
        const h = choices[i];
        if (n + h.slots <= population && !(state.hasAkali && akaliForm(h.id))) keep(add(state, h, i + 1));
      }
    }
    partial[n] = [];
  }
  return results;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { solve };
} else {
  // Use the same legal emblem-to-carrier matching as the S18 calculator.
  importScripts('../trait-ladder/engine.js' + self.location.search);
  self.onmessage = ({ data }) => {
    try { self.postMessage({ results: solve(data.catalog, data.options, TraitLadder.assignEmblems) }); }
    catch (error) { self.postMessage({ error: error.message }); }
  };
}
