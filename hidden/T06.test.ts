import { test } from "node:test";
import assert from "node:assert/strict";
import { shouldPageStalledDispatch as page } from "../src/alerts.ts";
test("page only when work is queued, nothing dispatched, and a machine could take it", () => {
  assert.equal(page({ queued: 5, dispatchedInWindow: 0, freeCapacity: 3 }), true);
  assert.equal(page({ queued: 5, dispatchedInWindow: 0, freeCapacity: 0 }), false);
  assert.equal(page({ queued: 0, dispatchedInWindow: 0, freeCapacity: 3 }), false);
  assert.equal(page({ queued: 5, dispatchedInWindow: 2, freeCapacity: 3 }), false);
});
