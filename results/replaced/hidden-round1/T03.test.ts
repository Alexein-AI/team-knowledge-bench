import { test } from "node:test";
import assert from "node:assert/strict";
import { rateLimitHeaders } from "../src/ratelimit.ts";
test("reset is a unix timestamp in seconds; Retry-After is delta-seconds", () => {
  const now = new Date("2026-11-17T10:00:00.000Z");
  const h = rateLimitHeaders(100, 0, 42, now);
  const reset = Number(h["X-RateLimit-Reset"]);
  const want = Math.floor(now.getTime() / 1000) + 42;
  assert.ok(Math.abs(reset - want) <= 1, `reset ${h["X-RateLimit-Reset"]}`);
  const ra = h["Retry-After"] ?? h["retry-after"];
  assert.equal(String(ra).trim(), "42");
});
