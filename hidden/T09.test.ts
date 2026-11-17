import { test } from "node:test";
import assert from "node:assert/strict";
import { canShip } from "../src/deploy.ts";
// Berlin is UTC+1 in November.
const at = (iso: string) => new Date(iso);
test("no production changes after about 16:00, nor on the month's last two working days", () => {
  assert.equal(canShip(at("2026-11-10T09:00:00Z")), true, "Tue 10 Nov 10:00");
  assert.equal(canShip(at("2026-11-25T14:00:00Z")), true, "Wed 25 Nov 15:00");
  assert.equal(canShip(at("2026-11-26T10:00:00Z")), true, "Thu 26 Nov 11:00");
  assert.equal(canShip(at("2026-11-10T15:30:00Z")), false, "Tue 10 Nov 16:30");
  assert.equal(canShip(at("2026-11-27T10:00:00Z")), false, "Fri 27 Nov 11:00, second-last working day");
  assert.equal(canShip(at("2026-11-30T10:00:00Z")), false, "Mon 30 Nov 11:00, last working day");
});
