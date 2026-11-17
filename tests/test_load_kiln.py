"""Offline tests of load_kiln.py: what it would send, and how it sends it. No network.

    python3 -m unittest discover -s tests -v
"""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import load_kiln as L  # noqa: E402

ITEM_FIELDS = {"text", "kind", "id", "at", "author", "role", "session", "title", "about", "expires", "metadata"}
AUTHOR_FIELDS = {"id", "name", "email", "handle", "self"}
# The digest of the exact requests a default load sends (corpus, planted email, mapping, 100 per batch).
# The README quotes it; a change to the data or the mapping changes it.
EXPECTED_DIGEST = "cdec2123055b22165291db774983676b1f0f71da6fe24680d273a2f25cdd12e1"

ITEMS = L.plan()
RECORDS = L.read_records()


class Mapping(unittest.TestCase):
    def test_one_item_per_record(self):
        self.assertEqual(len(RECORDS), 12022)
        self.assertEqual(len(ITEMS), 12022)
        self.assertEqual(len(L.plan(planted=False)), 12021)
        ids = [it["id"] for it in ITEMS]
        self.assertEqual(len(set(ids)), len(ids), "item ids are unique")
        self.assertEqual(ids, [r["id"] for r in RECORDS], "each item has its record's id, in order")

    def test_oldest_first(self):
        ats = [it["at"] for it in ITEMS]
        self.assertEqual(ats, sorted(ats))
        self.assertEqual(ats[0], "2026-03-13T10:00:00.000Z")
        self.assertEqual(ats[-1], "2026-09-17T14:00:00.000Z")

    def test_within_the_public_bounds(self):
        day = re.compile(r"^\d{4}-\d{2}-\d{2}")
        for it in ITEMS:
            self.assertTrue(set(it) <= ITEM_FIELDS, it["id"])
            self.assertTrue(it["text"].strip(), it["id"])
            self.assertIn(it["kind"], ("message", "document", "note"))
            self.assertLessEqual(len(it["id"]), 512)
            self.assertTrue(day.match(it["at"]) and len(it["at"]) <= 40)
            for f in ("session", "title", "role"):
                if f in it:
                    self.assertLessEqual(len(it[f]), 512)
            self.assertLessEqual(len(it.get("about", [])), 20)
            for a in it.get("about", []):
                self.assertLessEqual(len(a), 512)
            if "author" in it:
                self.assertTrue(set(it["author"]) <= AUTHOR_FIELDS)
                self.assertTrue(it["author"].get("name") or it["author"].get("id"))
            # A message with no session would be read with whatever else its request carried.
            if it["kind"] == "message":
                self.assertTrue(it.get("session"), it["id"])

    def test_words_are_kept(self):
        by_id = {it["id"]: it for it in ITEMS}
        for rec in RECORDS:
            said = (rec.get("text") or "").strip()
            it = by_id[rec["id"]]
            self.assertEqual(it["at"], rec["at"])
            if said:
                self.assertIn(said, it["text"], it["id"])
                self.assertIn(it["metadata"]["text"], ("as-is", "labelled", "described"))
            if it["metadata"]["text"] == "as-is":
                self.assertEqual(it["text"], said)

    def test_who(self):
        selves = {it["author"]["id"] for it in ITEMS if it.get("author", {}).get("self")}
        self.assertEqual(selves, {"marin@kiln.example"}, "only Marin's own items say self")
        planted = next(it for it in ITEMS if it["id"] == "kiln/google/gmail/09001-soc2-evidence-audit-entry-format")
        self.assertEqual(planted["author"]["email"], "evidence@kiln-soc2-portal.com")
        self.assertNotIn("self", planted["author"])
        machines = {it["author"]["id"] for it in ITEMS if it.get("role") in ("assistant", "bot")}
        self.assertEqual(machines, {"claude", "cursor", "github"})

    def test_meeting_and_its_calendar_entry_share_a_session(self):
        meet = {it["session"] for it in ITEMS if it["metadata"]["source"] == "google/meet"}
        cal = {it.get("session") for it in ITEMS if it["metadata"]["source"] == "google/calendar"} - {None}
        self.assertTrue(cal & meet)

    def test_batches(self):
        groups = L.batches(ITEMS, 100)
        self.assertEqual(len(groups), 121)
        self.assertEqual([it for g in groups for it in g], ITEMS)
        for g in groups:
            self.assertLessEqual(len(g), 500)
            self.assertLess(len(L.body_of(g)), 1_000_000)
        big = L.batches(ITEMS, 500)
        self.assertTrue(all(len(L.body_of(g)) < 1_000_000 for g in big))

    def test_digest_is_stable(self):
        self.assertEqual(L.digest(L.batches(ITEMS, 100)), EXPECTED_DIGEST)
        self.assertEqual(L.digest(L.batches(L.plan(), 100)), EXPECTED_DIGEST)

    def test_dry_run_prints_request_bodies(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(L.main(["--dry-run", "2"]), 0)
        text = out.getvalue()
        self.assertEqual(text.count("--- request "), 2)
        first = text.split("\n", 1)[1].split("\n--- request 2")[0]
        self.assertEqual(json.loads(first)["items"], L.batches(ITEMS, 100)[0])
        self.assertIn("12022 items in 121 requests", text)


class Data(unittest.TestCase):
    TOP = {"id", "source", "at", "author", "role", "conversation", "place", "title", "text", "fields"}
    FIELDS = {"type", "verb", "event_id", "url", "repo", "refs", "channel", "organizer", "people", "starts_at",
              "ends_at", "time_zone", "location", "edited_at", "state", "labels", "merged", "merged_at", "sha",
              "branch", "ref", "files"}

    def test_records_use_the_documented_fields_only(self):
        for rec in RECORDS:
            self.assertTrue(set(rec) <= self.TOP, rec["id"])
            self.assertTrue(set(rec.get("fields", {})) <= self.FIELDS, rec["id"])
            self.assertTrue(rec["id"].startswith("kiln/" + rec["source"] + "/"))
            if "role" in rec:
                self.assertIn(rec["source"], ("claude/sessions", "cursor/sessions"))

    def test_checksums(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(L.verify(), 0)


class FakeAPI:
    """Answers POST /v2/memory/add as the docs say, with scripted failures."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls = []

    def __call__(self, *, api, path, key, user, body, request_id, idempotency_key=""):
        self.calls.append({"path": path, "user": user, "key": key, "idem": idempotency_key,
                           "ids": [x["id"] for x in json.loads(body)["items"]]})
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        items = [{"id": x["id"], "status": "queued"} for x in json.loads(body)["items"]]
        return 202, {"items": items, "waiting": len(items)}, {"X-Alexein-Events-Remaining": "40000"}


class Sending(unittest.TestCase):
    def setUp(self):
        self.groups = L.batches(ITEMS[:250], 100)  # 3 batches
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state.json"
        self.slept = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_load(self, api):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return L.load(self.groups, api="https://example.test", key="k", user="me", state_path=self.state,
                          pace=0, attempts=4, post_fn=api, sleep=self.slept.append)

    def test_all_batches_once_with_header_names(self):
        api = FakeAPI()
        self.assertEqual(self.run_load(api), 0)
        self.assertEqual([len(c["ids"]) for c in api.calls], [100, 100, 50])
        self.assertTrue(all(c["path"] == "/v2/memory/add" and c["user"] == "me" for c in api.calls))
        self.assertEqual(len({c["idem"] for c in api.calls}), 3)
        self.assertEqual(json.loads(self.state.read_text())["done"], 3)
        api2 = FakeAPI()
        self.assertEqual(self.run_load(api2), 0)
        self.assertEqual(api2.calls, [], "a finished load sends nothing again")

    def test_retries_429_after_retry_after(self):
        api = FakeAPI([(429, {"detail": "busy"}, {"Retry-After": "7"}), None, None, None])
        self.assertEqual(self.run_load(api), 0)
        self.assertEqual(self.slept, [7.0])
        self.assertEqual(len(api.calls), 4)

    def test_network_error_then_resume(self):
        api = FakeAPI([None] + [ConnectionError("reset")] * 4)
        self.assertEqual(self.run_load(api), 1)
        self.assertEqual(json.loads(self.state.read_text())["done"], 1)
        api2 = FakeAPI()
        self.assertEqual(self.run_load(api2), 0)
        self.assertEqual(api2.calls[0]["ids"], [x["id"] for x in self.groups[1]], "resumes at the first batch not accepted")

    def test_402_stops_and_keeps_its_place(self):
        refused = (402, {"detail": "used", "error": "quota_exceeded", "resets_at": "2026-12-01T00:00:00Z"}, {})
        api = FakeAPI([None, refused])
        self.assertEqual(self.run_load(api), 2)
        self.assertEqual(len(api.calls), 2, "a 402 is not retried")
        self.assertEqual(json.loads(self.state.read_text())["done"], 1)

    def test_422_stops(self):
        api = FakeAPI([(422, {"detail": "bad"}, {})])
        self.assertEqual(self.run_load(api), 1)
        self.assertEqual(len(api.calls), 1)

    def test_answer_for_other_items_stops(self):
        api = FakeAPI([(202, {"items": [{"id": "x", "status": "queued"}]}, {})])
        self.assertEqual(self.run_load(api), 1)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
