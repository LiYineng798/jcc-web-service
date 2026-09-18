/* Pure, deterministic S18 rules and bounded beam search. Also loaded by Node tests. */
(function (scope) {
  'use strict';
  function prepare(data, options) {
    const population = Number(options.population);
    if (!Number.isInteger(population) || population < 2 || population > 13) throw Error('人口须为 2～13。');
    const locked = new Set(options.locked || []), banned = new Set(options.banned || []);
    const traitIndex = new Map(data.traits.map((t, i) => [t.id, i]));
    const lux = options.lux || '', khazix = [...new Set(options.khazix || [])];
    if (lux && !data.luxChoices.some(t => t.id === lux)) throw Error('请选择有效的拉克丝形态。');
    if (khazix.some(t => !data.khazixChoices.includes(t))) throw Error('螳螂进化羁绊无效。');
    const heroes = data.champions.map(c => {
      const traits = { ...c.traits };
      if (c.lux && lux) { traits[lux] = 2; locked.add(c.id); }
      if (c.khazix && khazix.length) { khazix.forEach(t => { traits[t] = 1; }); locked.add(c.id); }
      return { ...c, traits, entries: Object.entries(traits).map(([id, count]) => [traitIndex.get(id), count]) };
    });
    if ([...locked].some(id => banned.has(id))) throw Error('必选弈子不能同时禁用，请检查拉克丝和螳螂设置。');
    if ([...locked, ...banned].some(id => !heroes.some(c => c.id === id))) throw Error('弈子资料已更新，请重新选择。');
    const forced = heroes.filter(c => locked.has(c.id));
    if (forced.reduce((n, c) => n + c.slots, 0) > population) throw Error('必选弈子已超过人口上限。');
    const emblems = options.emblems || [];
    if (emblems.length > population * 3 || emblems.some(id => !data.emblems.some(e => e.trait === id))) throw Error('转职数量或类型无效。');
    const base = new Array(data.traits.length).fill(0);
    emblems.forEach(id => { base[traitIndex.get(id)]++; });
    return { data, population, locked, forced, heroes: heroes.filter(c => !banned.has(c.id)),
      byId: new Map(heroes.map(c => [c.id, c])), traitIndex, emblems, base,
      minTank: Number(options.minTank || 0), minCarry: Number(options.minCarry || 0) };
  }

  // Bipartite residual network: emblem type -> legal carrier (at most one per type)
  // -> three equipment slots. This avoids counting unwearable or native emblems.
  function assignEmblems(team, emblems) {
    const types = [...new Set(emblems)];
    const end = 1 + types.length + team.length, graph = Array.from({ length: end + 1 }, () => []);
    function edge(a, b, cap) {
      const f = { to: b, cap, rev: graph[b].length, original: cap };
      graph[a].push(f); graph[b].push({ to: a, cap: 0, rev: graph[a].length - 1 });
      return f;
    }
    const links = [];
    types.forEach((trait, i) => {
      edge(0, i + 1, emblems.filter(t => t === trait).length);
      team.forEach((hero, j) => {
        if (!hero.traits[trait]) links.push({ trait, hero: hero.id, edge: edge(i + 1, 1 + types.length + j, 1) });
      });
    });
    team.forEach((_, j) => edge(1 + types.length + j, end, 3));
    let flow = 0;
    for (;;) {
      const visited = new Set();
      function augment(v) {
        if (v === end) return true;
        visited.add(v);
        for (const e of graph[v]) if (e.cap && !visited.has(e.to) && augment(e.to)) {
          e.cap--; graph[e.to][e.rev].cap++; return true;
        }
        return false;
      }
      if (!augment(0)) break;
      flow++;
    }
    if (flow !== emblems.length) return null;
    return links.filter(l => l.edge.cap === 0).map(l => ({ hero: l.hero, trait: l.trait }));
  }

  function metrics(ctx, counts) {
    let active = 0, progress = 0;
    const rows = [];
    ctx.data.traits.forEach((t, i) => {
      let count = counts[i];
      if (t.id === ctx.data.composite.id) {
        count = ctx.data.composite.sources.every(id => counts[ctx.traitIndex.get(id)] >= 3) ? 1 : 0;
      }
      const threshold = Math.max(1, t.threshold);
      const on = count >= threshold;
      if (!t.unique) { active += Number(on); progress += Math.min(count / threshold, 1); }
      if (count) rows.push({ id: t.id, count, active: on, unique: t.unique, threshold });
    });
    return { active, progress, rows };
  }

  function evaluate(ctx, ids) {
    if (new Set(ids).size !== ids.length) return null;
    const team = ids.map(id => ctx.byId.get(id));
    if (team.some(c => !c || !ctx.heroes.includes(c))) return null;
    const population = team.reduce((n, c) => n + c.slots, 0);
    if (population > ctx.population || [...ctx.locked].some(id => !ids.includes(id))) return null;
    const assignments = assignEmblems(team, ctx.emblems);
    if (!assignments) return null;
    const counts = ctx.base.slice();
    team.forEach(c => c.entries.forEach(([i, n]) => { counts[i] += n; }));
    return { ids, population, ...metrics(ctx, counts), assignments,
      cost: team.reduce((n, c) => n + c.cost, 0),
      tanks: team.filter(c => c.role === 'tank').length,
      carries: team.filter(c => c.role === 'carry').length };
  }

  function solve(data, options, report = () => {}) {
    const ctx = prepare(data, options);
    const forcedIds = ctx.forced.map(c => c.id);
    const counts = ctx.base.slice();
    ctx.forced.forEach(c => c.entries.forEach(([i, n]) => { counts[i] += n; }));
    const initial = { ids: forcedIds, counts, pop: ctx.forced.reduce((n, c) => n + c.slots, 0),
      cost: ctx.forced.reduce((n, c) => n + c.cost, 0),
      tanks: ctx.forced.filter(c => c.role === 'tank').length,
      carries: ctx.forced.filter(c => c.role === 'carry').length };
    const candidates = ctx.heroes.filter(c => !ctx.locked.has(c.id));
    const completed = new Map();
    let visited = 0, beam = [initial];
    // Diverse partial teams are ranked by completed traits plus partial progress.
    // Bounded search is deliberately reported as recommendations, not a proof of optimum.
    for (let depth = 0; depth <= ctx.population && beam.length; depth++) {
      const next = new Map();
      for (const state of beam) {
        if (state.pop === ctx.population) { completed.set(state.ids.slice().sort().join(','), state); continue; }
        for (const hero of candidates) {
          if (state.ids.includes(hero.id) || state.pop + hero.slots > ctx.population) continue;
          const ids = [...state.ids, hero.id].sort();
          const key = ids.join(',');
          if (next.has(key)) continue;
          const c = state.counts.slice();
          hero.entries.forEach(([i, n]) => { c[i] += n; });
          const pop = state.pop + hero.slots, tanks = state.tanks + Number(hero.role === 'tank');
          const carries = state.carries + Number(hero.role === 'carry');
          if (Math.max(0, ctx.minTank - tanks) + Math.max(0, ctx.minCarry - carries) > ctx.population - pop) continue;
          const m = metrics(ctx, c), cost = state.cost + hero.cost;
          const score = m.active * 100 + m.progress * 35 + Math.min(tanks, ctx.minTank) * 25 + Math.min(carries, ctx.minCarry) * 25 - cost * .03;
          next.set(key, { ids, counts: c, pop, tanks, carries, cost, score });
          visited++;
        }
      }
      const ranked = [...next.values()].sort((a, b) => b.score - a.score || a.cost - b.cost || a.ids.join().localeCompare(b.ids.join()));
      // Keep several paths per contribution vector so cheap duplicates don't crowd out diversity.
      const signatures = new Map();
      beam = [];
      for (const s of ranked) {
        if (s.pop === ctx.population) { completed.set(s.ids.join(','), s); continue; }
        const signature = s.counts.map((n, i) => Math.min(n, Math.max(1, data.traits[i].threshold))).join(',') + '/' + s.pop;
        const seen = signatures.get(signature) || 0;
        if (seen >= 3) continue;
        signatures.set(signature, seen + 1); beam.push(s);
        if (beam.length >= 600) break;
      }
      report({ depth, visited });
    }
    const ranked = [...completed.values()].sort((a, b) => {
      const x = metrics(ctx, a.counts), y = metrics(ctx, b.counts);
      return y.active - x.active || a.cost - b.cost || a.ids.join().localeCompare(b.ids.join());
    });
    const results = [];
    for (const s of ranked) {
      const result = evaluate(ctx, s.ids);
      if (result && result.tanks >= ctx.minTank && result.carries >= ctx.minCarry) results.push(result);
      if (results.length === 12) break;
    }
    return { results, visited, exact: false };
  }
  const api = { prepare, evaluate, solve, assignEmblems };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else scope.TraitLadder = api;
})(globalThis);
