"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("js/power.js", "utf8");
const popup = source.slice(source.indexOf("  function gridPop(g)"), source.indexOf("  // ---- grid layout"));
const map = fs.readFileSync("js/map.js", "utf8");
const popHelpers = map.slice(map.indexOf("const Pop ="), map.indexOf("\n\n/**"));
const charts = fs.readFileSync("js/charts.js", "utf8");
const iconHelpers = charts.slice(charts.indexOf("const iconSlug ="), charts.indexOf("const pct ="));
const gridHelpers = source.slice(source.indexOf("  function allGrids()"), source.indexOf("  const grid =")) +
  source.slice(source.indexOf("  const capOf ="), source.indexOf("  const hasGens ="));
const first = { CircuitGroupID: 1, AssociatedCircuits: [10], PowerConsumed: 123, PowerCapacity: 300, PowerMaxConsumed: 450 };
const second = { CircuitGroupID: 2, AssociatedCircuits: [20], PowerConsumed: 40, PowerCapacity: 70, PowerMaxConsumed: 80 };
const context = {
  popSection: t => `[${t}]`,
  esc: x => String(x).replaceAll("<", "&lt;"), fmtNum: String,
  gridLabel: g => g.all ? "All grids" : "Grid",
  onGrid: (pi, g) => pi && (g.all ? pi.CircuitID >= 0 : pi.CircuitGroupID === g.CircuitGroupID),
  groups: [first, second],
  gens: [
    { pi: { CircuitGroupID: 1, CircuitID: 10 }, cap: 500, raw: {} },
    { pi: { CircuitGroupID: 2, CircuitID: 20 }, cap: 200, raw: {} },
  ],
  truckStations: [{ Name: "<Truck>", PowerInfo: { CircuitGroupID: 1, CircuitID: 10 } }],
  trainStations: [{ Name: "Train", PowerInfo: { CircuitGroupID: 1, CircuitID: 10 } },
    { Name: "Other", PowerInfo: { CircuitGroupID: 2, CircuitID: 20 } }],
  dronePorts: [{ Name: "Port", PowerInfo: { CircuitGroupID: 1, CircuitID: 10 } }],
  stationStatus: { truck: "ready", train: "ready", drone: "ready" },
  PowerNet: { switchStatus: "ready", switches: [
    { SwitchTag: "Border", Priority: -1, circuits: [10, 20] },
    { SwitchTag: "Priority", Priority: 2, circuits: [10] },
    { SwitchTag: "Other switch", circuits: [20] },
  ] },
  machines: [
    { circuit: 1, circuitId: 10, outputs: [{ name: "Iron Ingot" }, { name: "Heavy Modular Frame" }, { name: "Fluid" }] },
    { circuit: 1, circuitId: 10, outputs: [{ name: "Iron Plate" }, { name: "Iron Plate" }] },
    { circuit: 2, circuitId: 20, outputs: [{ name: "Other item" }] },
  ],
  sinkValues: new Map([["Iron Ingot", 2], ["Iron Plate", 6], ["Heavy Modular Frame", 10800]]),
  sinkStatus: "ready",
};
vm.createContext(context);
vm.runInContext(iconHelpers + popHelpers, context);
vm.runInContext(gridHelpers, context);
vm.runInContext(popup, context);
const grid = context.gridPop(first);
assert.ok(grid.includes("&lt;Truck>") && grid.includes("Port") && grid.includes("Border"));
assert.ok(!grid.includes("Other switch") && !grid.includes("Other item") && !grid.includes(">Other<"));
assert.ok(grid.includes("<span>Presently:</span><b>123/300 MW</b>"));
assert.ok(grid.includes("<span>Maximum:</span><b>450/500 MW</b>"));
const overloaded = context.gridPop({ ...first, PowerConsumed: 301, PowerMaxConsumed: 500 });
assert.ok(overloaded.includes('<div class="row warn-text"><span>Presently:</span><b>301/300 MW</b></div>'));
assert.ok(overloaded.includes('<div class="row"><span>Maximum:</span><b>500/500 MW</b></div>'));
const maxOverloaded = context.gridPop({ ...first, PowerConsumed: 300, PowerMaxConsumed: 501 });
assert.ok(maxOverloaded.includes('<div class="row"><span>Presently:</span><b>300/300 MW</b></div>'));
assert.ok(maxOverloaded.includes('<div class="row warn-text"><span>Maximum:</span><b>501/500 MW</b></div>'));
assert.ok(!grid.includes("sink pts") && !grid.includes("sink points") && !grid.includes("10800"));
for (const [asset, label] of [
  ["truck-station", "&lt;Truck>"], ["train-station", "Train"], ["drone-port", "Port"],
  ["power-switch", "Border"], ["priority-power-switch", "Priority"],
  ["heavy-modular-frame", "Heavy Modular Frame"], ["iron-plate", "Iron Plate"],
]) {
  const image = grid.indexOf(`src="/img/icons/${asset}.png`);
  assert.ok(image >= 0 && grid.startsWith(label, grid.indexOf(">", image) + 1), `${label} icon`);
}
assert.ok(grid.indexOf(">Heavy Modular Frame") < grid.indexOf(">Iron Plate"));
assert.ok(grid.indexOf(">Iron Plate") < grid.indexOf(">Iron Ingot"));
assert.ok(!grid.includes(">Fluid") && grid.includes(">1 more...<"));
assert.equal(grid.match(/>Iron Plate<\/span>/g).length, 1);
const all = context.gridPop(context.allGrids());
assert.ok(all.includes("Other switch") && all.includes(">Other<") && all.includes(">2 more...<"));
assert.ok(all.includes("<span>Presently:</span><b>163/370 MW</b>"));
assert.ok(all.includes("<span>Maximum:</span><b>530/700 MW</b>"));
const other = context.gridPop(second);
assert.ok(!other.includes("[Truck stations]") && !other.includes("[Drone ports]"));
assert.ok(other.includes(">Other item<") && !other.includes("more..."));
const station = name => ({ Name: name, PowerInfo: { CircuitGroupID: 1, CircuitID: 10 } });
context.truckStations = ["Truck E", "Truck D", "Truck C", "Truck B", "Truck A"].map(station);
context.trainStations = ["Train C", "Train B", "Train A"].map(station);
context.dronePorts = ["Port D", "Port C", "Port B", "Port A"].map(station);
context.PowerNet.switches = ["Switch D", "Switch C", "Switch B", "Switch A"]
  .map(name => ({ SwitchTag: name, Priority: -1, circuits: [10] }));
const many = context.gridPop(first);
const part = (title, next) => many.split(`[${title}]`)[1].split(`[${next}]`)[0];
for (const [title, next, prefix, count] of [
  ["Truck stations", "Train stations", "Truck", 2],
  ["Drone ports", "Power switches", "Port", 1],
  ["Power switches", "Produced items", "Switch", 1],
]) {
  const section = part(title, next);
  assert.ok(section.indexOf(`>${prefix} A`) < section.indexOf(`>${prefix} B`));
  assert.ok(section.includes(`>${prefix} C<`) && !section.includes(`>${prefix} D<`) && section.includes(`>${count} more...<`));
}
assert.ok(!part("Train stations", "Drone ports").includes("more..."));
context.machines = [];
context.PowerNet.switches = [];
context.trainStations = [];
const empty = context.gridPop(second);
assert.ok(!empty.includes("[Produced items]") && !empty.includes("[Power switches]") && !empty.includes("[Train stations]"));
context.machines = [{ circuit: 1, circuitId: 10, outputs: [{ name: "Iron Plate" }, { name: "Iron Ingot" }, { name: "Heavy Modular Frame" }] }];
assert.ok(!context.gridPop(first).split("[Produced items]")[1].includes("more..."));
context.sinkValues = null; context.sinkStatus = "unavailable"; context.stationStatus.drone = "unavailable";
const failed = context.gridPop(first);
assert.ok(failed.includes("Item ranking unavailable") && failed.includes("[Drone ports]<div class=\"row muted\"><span>Unavailable</span>"));
context.machines = null;
assert.ok(context.gridPop(first).includes("[Produced items]<div class=\"row muted\"><span>Unavailable</span>"));
console.log("grid popup contents: ok");
