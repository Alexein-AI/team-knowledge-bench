import { test } from "node:test";
import assert from "node:assert/strict";
import { shareOf } from "../src/fairshare.ts";
test("a small org's share stays fractional instead of flooring to zero", () => {
  const s = shareOf(1, 400, 240);
  assert.ok(s > 0.59 && s < 0.61, `got ${s}`);
  assert.ok(Math.abs(shareOf(4, 5, 240) - 192) < 1e-9);
});
