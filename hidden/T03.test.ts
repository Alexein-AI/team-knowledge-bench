import { test } from "node:test";
import assert from "node:assert/strict";
import { refuseEnqueue } from "../src/admission.ts";
test("refuse past five times the org's share queued, counting queued jobs only", () => {
  assert.equal(refuseEnqueue({ queued: 51, running: 0, share: 10 }), true, "51 queued against a share of 10");
  assert.equal(refuseEnqueue({ queued: 49, running: 0, share: 10 }), false, "49 queued against a share of 10");
  assert.equal(refuseEnqueue({ queued: 45, running: 30, share: 10 }), false, "running work does not count");
  assert.equal(refuseEnqueue({ queued: 21, running: 0, share: 4 }), true, "21 queued against a share of 4");
});
