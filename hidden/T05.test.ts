import { test } from "node:test";
import assert from "node:assert/strict";
import { CONTRACTS, concurrencyFor } from "../src/contracts.ts";
const key = (re: RegExp) => Object.keys(CONTRACTS).find((k) => re.test(k));
test("Sundermann Rail is contracted for 20 and Ardelle for 12", () => {
  const s = key(/sundermann/i), a = key(/ardelle/i);
  assert.ok(s && a, `keys: ${Object.keys(CONTRACTS)}`);
  assert.equal(concurrencyFor(s!), 20);
  assert.equal(concurrencyFor(a!), 12);
});
