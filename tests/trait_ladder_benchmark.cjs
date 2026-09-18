// node tests/trait_ladder_benchmark.cjs <baseline-engine.cjs> <calculator-data.json>
// Inputs are local artifacts; results must match before timings are compared.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const before = require(path.resolve(process.argv[2]));
const after = require('../static/trait-ladder/engine.js');
const data = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const scenarios = [{population:8}, {population:9}, {population:10},
  {population:9,lux:'455',khazix:['344'],emblems:['341','452']}];
const median = values => values.sort((a,b)=>a-b)[Math.floor(values.length/2)];
const measurements = [];
for (const options of scenarios) {
  before.solve(data, options); after.solve(data, options);
  const times = {before:[], after:[]}, outputs = {};
  for (let i=0; i<5; i++) {
    for (const label of i%2 ? ['after','before'] : ['before','after']) {
      const start = performance.now();
      outputs[label] = (label === 'before' ? before : after).solve(data, options);
      times[label].push(performance.now()-start);
    }
    assert.deepEqual(outputs.after, outputs.before);
  }
  const old = median(times.before), current = median(times.after);
  measurements.push({options, beforeMs:Math.round(old), afterMs:Math.round(current),
    reductionPercent:Math.round((1-current/old)*100), identical:true});
}
console.log(JSON.stringify(measurements, null, 2));
