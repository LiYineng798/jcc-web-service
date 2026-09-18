const assert = require('node:assert/strict');
const fs = require('node:fs');
const engine = require('../static/trait-ladder/engine.js');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const context = opts => engine.prepare(data, {population: 9, ...opts});
let r = engine.evaluate(context({lux:'455'}), ['5459']);
assert.equal(r.rows.find(t => t.id === '455').count, 2);
assert.equal(r.active, 1); // Lux unique excluded, selected Fae activates.
assert.equal(engine.evaluate(context({}), ['5459','5459']), null);
r = engine.evaluate(context({khazix:['346','349','349']}), ['3505']);
assert.equal(r.rows.find(t=>t.id==='349').count,1);
assert.equal(r.rows.find(t=>t.id==='346').count,1);
assert.equal(r.active, 1); // Rival is a multi-level trait.
r = engine.evaluate(context({}), ['5458','1508']);
assert.equal(r.population, 3);
assert.equal(r.rows.find(t=>t.id==='454').count,3);
assert.equal(r.active,1);
assert.throws(()=>context({population:2,locked:['5458','1508']}), /人口/);
assert.throws(()=>context({lux:'455',banned:['5459']}), /禁用/);
assert.throws(()=>context({khazix:['xxx']}));
assert.equal(engine.evaluate(context({emblems:['341']}), ['1500']),null); // native guard cannot wear it
assert.equal(engine.evaluate(context({emblems:['341','341']}), ['1508']),null); // no duplicate on one carrier
r = engine.evaluate(context({emblems:['341','341']}), ['1508','1511']);
assert.equal(r.assignments.length,2);
assert.equal(r.rows.find(t=>t.id==='341').count,2);
assert.equal(engine.assignEmblems([{id:'a',traits:{}}],['a','b','c','d']),null);
r = engine.evaluate(context({lux:'459'}), ['5459','1502','3506','4508','5456']);
// Use the current release's actual lunar roster, not assumed ids.
const lunar = data.champions.filter(c=>c.traits['460']).slice(0,3).map(c=>c.id);
r = engine.evaluate(context({lux:'459'}), ['5459','1502',...lunar]);
assert(r.rows.find(t=>t.id===data.composite.id)?.active);
assert(r.rows.find(t=>t.id===data.composite.id)?.unique); // single-level excluded under reference rule
const opts = {population:7,locked:['1501'],banned:['1509'],khazix:['344'],emblems:['341'],minTank:1,minCarry:1};
const solved=engine.solve(data,opts);
assert(solved.results.length>0);
for(const result of solved.results) {
 assert.equal(result.population,7); assert(result.ids.includes('1501')); assert(!result.ids.includes('1509'));
 assert(result.ids.includes('3505')); assert(result.tanks>=1 && result.carries>=1);
 assert.equal(new Set(result.ids).size,result.ids.length);
 const checked=engine.evaluate(context(opts),result.ids); assert.equal(checked.active,result.active);
}
// Small complete candidate pool: compare search ranking to brute force.
const small={...data,champions:data.champions.slice(0,9)};
let best=0;const ctx=engine.prepare(small,{population:3});
for(let i=0;i<9;i++)for(let j=i+1;j<9;j++)for(let k=j+1;k<9;k++) best=Math.max(best,engine.evaluate(ctx,[small.champions[i].id,small.champions[j].id,small.champions[k].id]).active);
assert.equal(engine.solve(small,{population:3}).results[0].active,best);
console.log('Ladder rules, legal equipment assignments and constrained search passed');
