"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function element() {
  return {
    children: [], style: {}, classList: { add() {}, remove() {} }, attrs: {}, offsetWidth: 150,
    setAttribute(k, v) { this.attrs[k] = v; }, getBoundingClientRect() { return { left: 0 }; }, appendChild(x) { this.children.push(x); },
    append(...xs) { this.children.push(...xs); }, replaceChildren(...xs) { this.children = xs; },
  };
}
const context = {
  document: { createElement: element, createElementNS: (_, tag) => Object.assign(element(), { tag }), createTextNode: text => ({ text }) },
  getComputedStyle: () => ({ getPropertyValue: () => "#fff" }),
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("js/charts.js", "utf8") + "\nthis.LineChart = LineChart;", context);

function renderedChart(data) {
  const chart = Object.create(context.LineChart.prototype);
  Object.assign(chart, { svg: element(), box: { clientWidth: 800 }, legend: element(), tip: element(), height: 230, fmt: String, data });
  chart.render();
  return chart;
}

for (const minutes of [360, 1440]) {
  const end = 100000, start = end - minutes * 60;
  const chart = renderedChart({ t: [end - 3600, end], tMin: start, tMax: end, series: [] });
  assert.equal(chart.x(start), chart.pad.l);
  assert.equal(chart.x(end), chart.W - chart.pad.r);
  assert.ok(chart.x(end - 3600) > chart.pad.l);
}
const auto = renderedChart({ t: [100, 200], series: [] });
assert.equal(auto.x(100), auto.pad.l);
assert.equal(auto.x(200), auto.W - auto.pad.r);
const gaps = renderedChart({ t: [20, 40, 80], tMin: 0, tMax: 100, interval: 20,
  coverage: [[18, 42], [78, 82]], series: [{ name: "Power", color: "red", values: [1, 2, 3] }] });
assert.equal(JSON.stringify(gaps.missing), JSON.stringify([[0, 18], [42, 78], [82, 100]]));
assert.equal(gaps.svg.children.find(e => e.tag === "path").attrs.d.match(/M/g).length, 2);
gaps.hover({ clientX: gaps.x(60) });
assert.match(gaps.tip.children[1].textContent, /cause is unknown/);
assert.equal(gaps.hoverI, null);
gaps.hover({ clientX: gaps.x(40) });
assert.equal(gaps.hoverI, 1);
const empty = renderedChart({ t: [], tMin: 0, tMax: 100, coverage: [], series: [] });
assert.equal(JSON.stringify(empty.missing), JSON.stringify([[0, 100]]));
empty.hover({ clientX: empty.x(50) });
assert.match(empty.tip.children[1].textContent, /cause is unknown/);
console.log("power chart time windows: ok");
