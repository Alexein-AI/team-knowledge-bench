import { test } from "node:test";
import assert from "node:assert/strict";
import * as lease from "../src/lease.ts";
test("a draining runner gets 120 seconds before we give up on it", () => {
  assert.equal((lease as any).DRAIN_CEILING_MS, 120_000);
});
