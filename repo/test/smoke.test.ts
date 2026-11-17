import { test } from "node:test";
import assert from "node:assert/strict";
import { PLAN_WEIGHT, weightFor } from "../src/fairshare.ts";
import { concurrencyFor } from "../src/contracts.ts";
import { queueDepth } from "../src/metrics.ts";

test("weights come from the plan", () => {
  assert.equal(weightFor("acme", [{ org: "acme", plan: "team" }]), PLAN_WEIGHT.team);
});

test("unknown orgs get the default concurrency", () => {
  assert.equal(concurrencyFor("someone-new"), 4);
});

test("queue depth is one gauge per org", () => {
  assert.equal(queueDepth({ a: 1, b: 2 }).length, 2);
});
