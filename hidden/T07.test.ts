import { test } from "node:test";
import assert from "node:assert/strict";
import { PLAN_WEIGHT, weightFor } from "../src/fairshare.ts";
test("a missing org_plan row falls back to the free plan, not a fixed 100", () => {
  assert.equal(weightFor("ghost", [{ org: "acme", plan: "team" }]), PLAN_WEIGHT.free);
  assert.equal(weightFor("acme", [{ org: "acme", plan: "team" }]), PLAN_WEIGHT.team);
});
