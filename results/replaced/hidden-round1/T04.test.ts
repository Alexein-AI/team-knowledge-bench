import { test } from "node:test";
import assert from "node:assert/strict";
import * as lease from "../src/lease.ts";
test("leases renew every 30 seconds", () => {
  assert.equal((lease as any).RENEW_INTERVAL_MS, 30_000);
});
