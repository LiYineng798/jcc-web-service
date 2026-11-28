const assert = require('node:assert/strict');
const { solve } = require('../static/smeech/worker');
const { assignEmblems } = require('../static/trait-ladder/engine');
const catalog = require('../static/smeech/catalog.json');
const byId = new Map(catalog.heroes.map(h => [h.id, h]));
const run = overrides => solve(catalog, { population: 9, required: [], excluded: [], emblems: [],
  excludedCosts: [4, 5, 7], excludeUnlocks: false, ...overrides }, assignEmblems);

assert.equal(byId.has(919958), false);
assert.equal(catalog.traits.filter(t => t.emblem).length, 22);
assert.equal(byId.get(919981).slots, 2);
assert.equal(catalog.traits.find(t => t.name === 'K/DA').threshold, 2);
assert.equal(catalog.traits.find(t => t.name === '电子舞曲').threshold, 2);
assert.deepEqual(byId.get(919037).traits, ['job_11']);
const baseline = run({});
assert.ok(baseline.length > 0);
for (const [i, result] of baseline.entries()) {
  const heroes = result.heroes.map(id => byId.get(id));
  assert.ok(heroes.every(h => h.cost < 4));
  assert.equal(heroes.length, new Set(result.heroes).size);
  const active = catalog.traits.filter(t => heroes.filter(h => h.traits.includes(t.id)).length >= t.threshold);
  assert.ok(active.length >= 9);
  assert.deepEqual(result.traits, active.map(t => t.id));
  assert.ok(i === 0 || result.population > baseline[i - 1].population || result.cost >= baseline[i - 1].cost);
}
const emblem = catalog.traits.find(t => t.emblem).id;
const custom = run({ required: [919800], excluded: [919115], emblems: [emblem, emblem], excludeUnlocks: true });
assert.ok(custom.length);
for (const team of custom) {
  assert.ok(team.heroes.includes(919800) && !team.heroes.includes(919115));
  assert.equal(team.assignments.length, 2);
  assert.equal(new Set(team.assignments.map(a => a.hero)).size, 2);
  for (const { hero, trait } of team.assignments) assert.ok(!byId.get(hero).traits.includes(trait));
}
assert.deepEqual(run({ population: 4 }), []);
assert.throws(() => run({ population: 4, required: baseline[0].heroes }), /人口/);
assert.throws(() => run({ required: [919952, 919953] }), /形态/);
console.log('S19 unlock rules and filtered recommendations passed.');
