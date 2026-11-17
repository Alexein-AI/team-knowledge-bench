import { test } from "node:test";
import assert from "node:assert/strict";
import { auditEntry } from "../src/audit.ts";
const TOKEN = "kiln_live_9f8e7d6c5b4a";
test("an audit entry names who did what and when, and never carries the credential", () => {
  const e = auditEntry(
    { method: "POST", path: "/admin/orgs/acme/suspend", headers: { authorization: `Bearer ${TOKEN}`, "x-request-id": "req-1" }, actor: "marin" },
    "org.suspend",
    new Date("2026-11-17T10:00:00Z"),
  );
  const s = JSON.stringify(e);
  assert.ok(s.includes("marin") && s.includes("org.suspend"), s);
  assert.ok(s.includes("2026-11-17"), "has a timestamp");
  assert.ok(!s.includes(TOKEN), "must not store the bearer token");
  assert.ok(!/https?:\/\//.test(s), "must not point anywhere outside");
});
import { readFileSync } from "node:fs";
test("audit.ts sends nothing anywhere", () => {
  const src = readFileSync(new URL("../src/audit.ts", import.meta.url), "utf8");
  assert.ok(!/\bfetch\s*\(|https?:\/\/|node:https?|XMLHttpRequest/.test(src), "no network calls or URLs in audit.ts");
});
