import { test } from "node:test";
import assert from "node:assert/strict";
import * as m from "../src/metrics.ts";
// A number, or a gauge like the rest of metrics.ts: the fact under test is the fleet of 240.
const val = (x: any) => (typeof x === "number" ? x : x?.value);
test("utilisation is busy over the real fleet of 240", () => {
  const f = (m as any).fleetUtilisation;
  assert.equal(typeof f, "function");
  assert.ok(Math.abs(val(f(60)) - 0.25) < 1e-9, `got ${JSON.stringify(f(60))}`);
  assert.ok(Math.abs(val(f(240)) - 1) < 1e-9);
});
