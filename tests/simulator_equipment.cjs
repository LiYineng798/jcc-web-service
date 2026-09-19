// Run with: node tests/simulator_equipment.cjs (no browser dependencies).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/tools/lineup-simulator/app.js', 'utf8');
const functions = ['equipmentError', 'equipItem', 'hydrateBoard', 'getTraitCounts'];
const state = {
  championById: new Map([
    ['native', {id:'native', traitIds:['a'], traitContributions:[]}],
    ['other', {id:'other', traitIds:['b'], traitContributions:[]}],
    ['third', {id:'third', traitIds:[], traitContributions:[]}],
    ['object', {id:'object', traitIds:['a'], canEquip:false}],
  ]),
  itemById: new Map([
    ['a', {category:'emblem', grantedTraitId:'a'}],
    ['a-alias', {category:'emblem', grantedTraitId:'a'}],
    ['b', {category:'emblem', grantedTraitId:'b'}],
    ['c', {category:'emblem', grantedTraitId:'c'}],
    ['unmapped', {category:'emblem', grantedTraitId:null}],
    ['sword', {category:'completed', grantedTraitId:null}],
  ]),
  traits: ['a','b','c'].map(id=>({id,name:id})),
  traitById: new Map(['a','b','c'].map(id=>[id,{id}])),
  board: [],
};
let mutations = 0;
const messages = [];
const context = vm.createContext({state, showToast:msg=>messages.push(msg), mutate:fn=>{fn();mutations++;}});
for (const name of functions) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0);
  const end = source.indexOf('\nfunction ', start + 1);
  vm.runInContext(source.slice(start, end), context);
}
const items = slot => Array.from(slot.items);
state.board = [{championId:'native',items:[]}, {championId:'other',items:[]}, {championId:'third',items:[]}];
context.equipItem(0,'a');
assert.deepEqual(items(state.board[0]),[]);
assert.match(messages.at(-1),/已拥有此羁绊/);
assert.equal(mutations,0);
context.equipItem(1,'a');
assert.equal(context.getTraitCounts().get('a'),2, 'legal emblem contributes one trait count');
context.equipItem(1,'a');
context.equipItem(1,'a-alias');
assert.deepEqual(items(state.board[1]),['a']);
assert.match(messages.at(-1),/只能佩戴一个/);
assert.equal(mutations,1, 'rejection must not change history');
context.equipItem(1,'c');
assert.deepEqual(items(state.board[1]),['a','c'], 'different emblems may coexist');
context.equipItem(2,'a');
assert.equal(context.getTraitCounts().get('a'),3, 'different champions may wear the same emblem');
context.equipItem(2,'sword');
context.equipItem(2,'sword');
assert.deepEqual(items(state.board[2]),['a','sword','sword'], 'ordinary items retain existing stacking');
context.equipItem(2,'c');
assert.equal(state.board[2].items.length,3);
const hydrated = context.hydrateBoard([
  {championId:'native',items:['a','sword','b','b','c']},
  {championId:'other',items:['a','a-alias','b','sword']},
  {championId:'object',items:['c']},
  {championId:'third',items:['unmapped','unmapped','missing']},
  {championId:'third',items:'malformed'},
]);
assert.deepEqual(items(hydrated[0]),['sword','b','c']);
assert.deepEqual(items(hydrated[1]),['a','sword']);
assert.deepEqual(items(hydrated[2]),[]);
assert.deepEqual(items(hydrated[3]),['unmapped']);
assert.deepEqual(items(hydrated[4]),[]);
state.board = hydrated;
assert.doesNotThrow(()=>context.getTraitCounts(), 'special board objects have no traitContributions');
console.log('PASS: emblem contribution, native conflict, duplicate/alias rejection, distinct emblems, item limit, ordinary stacking and restored/imported boards');
