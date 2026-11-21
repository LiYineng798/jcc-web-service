// Pure rule/serialization tests: no browser, network or user storage.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = process.env.PBE_DATA_ROOT || 'static/season-data/s19';
const read = name => JSON.parse(fs.readFileSync(`${root}/${name}.json`, 'utf8'))[name];
const source = fs.readFileSync('static/tools/lineup-simulator/app.js', 'utf8').split('elements.seasonSwitcher.addEventListener')[0];
const sandbox = { URLSearchParams, TextEncoder, TextDecoder, Uint8Array, DataView,
  btoa: s => Buffer.from(s, 'binary').toString('base64'), atob: s => Buffer.from(s, 'base64').toString('binary'),
  location: {search: '', origin: 'http://localhost', pathname: '/', hash: ''},
  document: {querySelector: () => ({dataset: {}}), querySelectorAll: () => []},
  localStorage: {getItem: () => null, setItem: () => {}}, window: {},
};
vm.createContext(sandbox);
vm.runInContext(source + `
renderBoard = () => {}; syncLibrarySelectionState = () => {}; renderSelectedAugments = () => {}; persist = () => {}; hidePopover = () => {};
globalThis.api = {state, normalizeTrait, expandChampionTraitChoices, normalizeBoardUnit, getTraitCounts,
totalPopulation, traitState, hydrateBoard, hydrateTraitModes, effectiveItems, boardUnitAllowance,
specialPlacementIsValid, encodePayload, decodePayload, formationPayload, pushHistory, applyHistory, posterTraitHtml, cycleUnitStars, removeUnit, unitStars, unitStarsHtml, boardSlotHtml};`, sandbox);
const a = sandbox.api, s = a.state;
s.season = {season_id:'s19', version_id:'s19__pbe'};
s.catalog = [s.season];
s.simulatorControls = true;
s.traits = read('traits').map(a.normalizeTrait);
s.traitById = new Map(s.traits.map(t => [t.id,t]));
const names = new Map(s.traits.flatMap(t => [[t.id,t],[t.name,t]]));
s.champions = read('champions').flatMap(h => a.expandChampionTraitChoices(h, names));
s.boardUnits = read('board_units').map(a.normalizeBoardUnit);
s.championById = new Map([...s.champions,...s.boardUnits].map(h => [h.id,h]));
s.traitModes = a.hydrateTraitModes(null);
const slot = (id, stars=1, items=[]) => ({championId:id,stars,items});
const count = name => a.getTraitCounts().get(names.get(name).id);
const sona = s.champions.filter(h => h.baseChampionId === '919037');
assert.equal(sona.length,5);
assert.equal(new Set(sona.map(h => h.choiceTraitId)).size,5);
const kdaSona = sona.find(h => h.choiceTraitName === 'K/DA');
const sonaHtml = a.boardSlotHtml(slot(kdaSona.id,2),0);
assert.match(sonaHtml,/<span class="unit-name">娑娜<\/span>/);
assert.doesNotMatch(sonaHtml,/unit-name is-long/);

s.board = [slot('919103',2),slot('919103',3),slot('919518',2),slot(kdaSona.id,2)];
assert.equal(count('K/DA'),7, 'duplicates use highest star; Sona contributes selected band');
assert.equal(a.totalPopulation(),3, 'Sona costs zero population');
s.board.push(slot('919981'));
assert.equal(a.totalPopulation(),5,'Baron costs two population');
assert.equal(a.hydrateBoard([slot(sona[0].id),slot(sona[1].id)]).filter(Boolean).length,1);
const td = names.get('真实伤害');
s.traitModes[td.id] = 'A';
assert.match(a.traitState(td,5).active.effect,/A面/);
assert.equal(a.traitState(td,5).active.style,'gold');
s.traitModes[td.id] = 'B';
assert.match(a.traitState(td,5).active.effect,/B面/);
assert.equal(a.traitState(td,5).active.style,'gold');
assert.equal(a.traitState(names.get('心之钢'),7).active.style,'prismatic');
assert.equal(a.traitState(a.normalizeTrait({id:'zero-test',breakpoints:[{min_units:0,style:'gold'}]}),0).active,null);
assert.equal(s.traits.length,47);
assert.equal(s.traits.filter(t=>t.breakpoints.some(p=>p.style==='unique')).length,19);
for (const name of ['神秘乐器','明日新星','超级巨星']) assert.equal(names.has(name),false);
for (const name of ['幻翎boys','音乐总监','一只怪乐团']) {
  assert.equal(a.traitState(names.get(name),1).styleIndex,'unique');
  assert.equal(a.traitState(names.get(name),0).styleIndex,0);
}
assert.equal(a.traitState(names.get('电子舞曲'),2).styleIndex,3);
assert.equal(a.traitState(names.get('合奏'),5).styleIndex,3);
for (const [level,style] of [[3,1],[5,1],[7,2],[10,2],[13,3],[16,3],[23,4]]) assert.equal(a.traitState(names.get('K/DA'),level).styleIndex,style);
assert.ok(s.championById.get('919103').traitIds.includes(names.get('编舞师').id));
assert.ok(s.championById.get('919800').traitIds.includes(names.get('法师').id));

s.board = [slot('919103',3),slot('919245'),slot('919235'),slot('919085')];
assert.doesNotMatch(a.posterTraitHtml(),/[AB]面/);
assert.match(a.posterTraitHtml(),/<strong>真实伤害<\/strong>/);
assert.doesNotMatch(a.posterTraitHtml(),/★/);
assert.match(a.posterTraitHtml(),/lineup-poster-trait-count">3<\/span>/);
s.board = [slot('919497',1,['sword']),slot('rakan-clone'),slot('rakan-clone')];
assert.equal(a.boardUnitAllowance(s.boardUnits[0]),2);
assert.equal(count('幻翎boys'),1);
assert.match(a.posterTraitHtml(),/unique\.svg/);
assert.match(a.posterTraitHtml(),/<strong>幻翎boys<\/strong>/);
assert.equal(a.totalPopulation(),1,'clones have unverified population, only known lower bound');
assert.equal(s.boardUnits[0].populationUnverified,true);
assert.deepEqual(a.effectiveItems(s.board[1]),['sword']);
s.board[0].items = ['armor'];
assert.deepEqual(a.effectiveItems(s.board[1]),['armor']);
s.board.push(slot('rakan-clone'));
assert.equal(a.specialPlacementIsValid('rakan-clone',3),false);
s.board[0]=null;
assert.equal(a.boardUnitAllowance(s.boardUnits[0]),0);
assert.equal(a.effectiveItems(s.board[1]).length,0);
s.board=[slot('919497',1,['sword']),slot('919497',2,['armor']),slot('rakan-clone')];
assert.deepEqual(a.effectiveItems(s.board[2]),['armor'],'highest-star body supplies cloned items');
s.board[1].stars=1;s.board[0].items.push('bow');
assert.deepEqual(a.effectiveItems(s.board[2]),['sword','bow'],'equipment count breaks equal-star ties');

s.board=[slot('919103',3),slot(kdaSona.id,2)];
s.history=[];s.historyIndex=-1;
a.pushHistory();
s.board[0].stars=1;s.traitModes[td.id]='A';a.pushHistory();
a.applyHistory(0);
assert.equal(s.board[0].stars,3);assert.equal(s.traitModes[td.id],'B');
const roundtrip=a.decodePayload(a.encodePayload());
assert.equal(roundtrip.board[0].stars,3);assert.equal(roundtrip.traitModes[td.id],'B');
assert.equal(roundtrip.board[1].championId,kdaSona.id);
// Direct editing cycles 1 → 2 → 3 → 4 → 1 and survives history/import.
s.board=[slot('919103')];s.history=[];s.historyIndex=-1;a.pushHistory();
for (const expected of [2,3,4,1]) { a.cycleUnitStars(0); assert.equal(s.board[0].stars,expected); }
a.applyHistory(3);assert.equal(s.board[0].stars,4);
assert.equal(a.hydrateBoard(a.decodePayload(a.encodePayload()).board)[0].stars,4);
assert.equal(a.hydrateBoard([slot('919103',99)])[0].stars,4);
assert.equal(a.hydrateBoard([{championId:'919103',items:[],star:3}])[0].stars,3); // Stored deck payload
assert.equal(a.unitStars({stars:Infinity}),1);
assert.match(a.unitStarsHtml(s.board[0],0),/4星/);
assert.equal((a.unitStarsHtml(s.board[0],0).match(/<path /g)||[]).length,4);
s.board=[slot('rakan-clone')];a.cycleUnitStars(0);assert.equal(s.board[0].stars,1);
s.board=[slot('919103',4)];a.removeUnit(0);assert.equal(s.board[0],null);a.applyHistory(s.historyIndex-1);assert.equal(s.board[0].stars,4);
// Other seasons preserve stars through JSON, retaining JCC2 for one-star boards.
s.simulatorControls=false;s.traitModes={};
assert.equal(a.hydrateBoard(a.decodePayload(a.encodePayload()).board)[0].stars,4);
s.board[0].stars=1;
const ordinary=a.encodePayload();assert.equal(ordinary.length,321);assert.match(ordinary,/^JCC2-/);
assert.equal(a.decodePayload(ordinary).board[0].championId,'919103');
console.log('PBE counting, choices, sides, clones, history and share roundtrips passed');

// Exercise the production DOM event handlers with narrow event/element doubles.
const listeners = new Map();
const classes = new Set();
const rail = {
  classList: {
    add: (...names) => names.forEach(n => classes.add(n)),
    remove: (...names) => names.forEach(n => classes.delete(n)),
    toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
  },
  contains: () => false,
  addEventListener: (name, fn) => listeners.set(`rail:${name}`, fn),
};
sandbox.document.querySelector = selector => selector === '.trait-rail' ? rail : null;
sandbox.document.querySelectorAll = () => [rail];
sandbox.document.addEventListener = (name, fn) => listeners.set(`document:${name}`, fn);
sandbox.bindBoard = board => { board.addEventListener = (name, fn) => listeners.set(`board:${name}`,fn); board.querySelector = () => null; };
vm.runInContext('bindBoard(elements.board)', sandbox);
const fullSource = fs.readFileSync('static/tools/lineup-simulator/app.js','utf8');
vm.runInContext(fullSource.slice(fullSource.indexOf('elements.board.addEventListener("click"'), fullSource.indexOf('document.addEventListener("pointerover"')), sandbox);
const cell = {dataset:{slotIndex:'0'},classList:rail.classList};
const target = {closest: selector => ['.has-unit','.hex-cell.has-unit','.hex-cell','[data-slot-index]'].includes(selector) ? cell : null, matches: selector => selector === '.hex-cell.has-unit'};
const event = {target, preventDefault(){this.prevented=true;},dataTransfer:{setData(){}}};
s.board=[slot('919103',4)];s.history=[];s.historyIndex=-1;a.pushHistory();
listeners.get('board:contextmenu')(event);assert.equal(s.board[0].stars,1);assert.equal(event.prevented,true);
listeners.get('document:dragstart')(event);assert.equal(classes.has('is-unit-dragging'),true);
listeners.get('rail:dragover')(event);assert.equal(classes.has('is-delete-target'),true);
listeners.get('rail:drop')(event);assert.equal(s.board[0],null);assert.equal(s.dragging,null);assert.equal(classes.size,0);
a.applyHistory(s.historyIndex-1);assert.equal(s.board[0].championId,'919103');
s.dragging={type:'item',id:'sword'};listeners.get('rail:drop')(event);assert.ok(s.board[0],'equipment drag must not delete units');
listeners.get('document:dragend')();assert.equal(s.dragging,null);
const removeTarget={closest: selector => selector === '[data-remove-unit]' ? {dataset:{removeUnit:'0'}} : null};
listeners.get('board:click')({...event,target:removeTarget});assert.equal(s.board[0],null);
console.log('Right-click cycling, hover removal, drag deletion and cancellation passed');
