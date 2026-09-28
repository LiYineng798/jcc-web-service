// Run with: node tests/simulator_position_forms.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/tools/lineup-simulator/app.js', 'utf8');
const names = ['positionFormId', 'hydrateBoard', 'mutate', 'moveUnit', 'getTraitCounts'];
const form = {front_id: '5179', back_id: '5178', front_rows: 2, legacy_ids: ['5177']};
const rakan = {id: '5179', traitIds: ['234', '237', '191'], traitContributions: [], positionForm: form};
const xayah = {id: '5178', traitIds: ['234', '237', '202'], traitContributions: [], positionForm: form};
const state = {
  champions: [rakan, xayah],
  championById: new Map([[rakan.id, rakan], [xayah.id, xayah]]),
  traitById: new Map(['234', '237', '191', '202'].map(id => [id, {id}])),
  traits: [], itemById: new Map(), board: Array(28).fill(null),
};
let history = 0;
const context = vm.createContext({
  state, equipmentError: () => '', pushHistory: () => history++,
  renderBoard: () => {}, syncLibrarySelectionState: () => {},
  renderSelectedAugments: () => {}, persist: () => {},
});
for (const name of names) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, `${name} exists`);
  const end = source.indexOf('\nfunction ', start + 1);
  vm.runInContext(source.slice(start, end), context);
}
const slot = id => ({championId: id, items: []});
const saved = Array(28).fill(null);
saved[0] = slot('5177'); // Combined r1 form should migrate to front-row Rakan.
saved[21] = slot('5179'); // Wrong form in the back should become Xayah.
state.board = context.hydrateBoard(saved);
assert.equal(state.board[0].championId, '5179');
assert.equal(state.board[21].championId, '5178');
let counts = context.getTraitCounts();
assert.equal(counts.get('191'), 1);
assert.equal(counts.get('202'), 1);
assert.equal(counts.get('234'), 2);
context.moveUnit(0, 21);
assert.equal(state.board[0].championId, '5179');
assert.equal(state.board[21].championId, '5178');
assert.equal(history, 1);
state.board[21] = null;
context.moveUnit(0, 21);
assert.equal(state.board[21].championId, '5178');
assert.equal(context.getTraitCounts().get('191'), undefined);
assert.equal(context.getTraitCounts().get('202'), 1);
context.moveUnit(21, 0);
assert.equal(state.board[0].championId, '5179');
assert.equal(context.positionFormId('5178', 13), '5179');
assert.equal(context.positionFormId('5179', 14), '5178');
console.log('PASS: official two-front/two-back position forms, saved r1 migration, and movement');
