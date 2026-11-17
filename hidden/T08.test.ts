import { test } from "node:test";
import assert from "node:assert/strict";
import * as boot from "../src/boot.ts";
test("prebaked images are the production path and the warm pool is gone", () => {
  assert.equal(boot.chooseColdStart(), "prebaked");
  assert.equal((boot as any).claimFromWarmPool, undefined);
});
