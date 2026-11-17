#!/usr/bin/env python3
"""Load the Kiln corpus into one Alexein memory through the public API, POST /v2/memory/add.

    python3 load_kiln.py --dry-run 3                 # print the first 3 request bodies; no network, no key
    python3 load_kiln.py --verify                    # check data/kiln against data/kiln/SHA256SUMS
    ALEXEIN_API_KEY=tm_... python3 load_kiln.py --yes             # load; safe to stop and run again
    ALEXEIN_API_KEY=tm_... python3 load_kiln.py --check [--wait]  # how far the items have got (free)

Every record of the corpus (data/kiln/*.jsonl) and the planted email becomes one item (README,
"Loading the corpus", has the whole mapping). Items go oldest first, in batches; each item's id is
its record's id, so sending a batch again changes nothing and counts nothing. Progress is kept in a
state file after each accepted batch, and a run that stops - a network error, a 402 at the plan's
limit, Ctrl-C - picks up from the first batch not yet accepted.

Settings: ALEXEIN_API_KEY (a key that writes), ALEXEIN_API_URL (default https://api.alexein.ai),
ALEXEIN_USER (the X-Alexein-User; default "me", the one the Claude Code plugin reads). Python 3.9+,
standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "kiln"
CORPUS_FILES = ("slack.jsonl", "github.jsonl", "gmail.jsonl", "meet.jsonl", "calendar.jsonl", "sessions.jsonl")
PLANTED_FILE = "planted-email.jsonl"
SUMS = DATA / "SHA256SUMS"
DEFAULT_API = "https://api.alexein.ai"
DEFAULT_USER = "me"

MAX_ITEMS = 500  # per add, the API's bound
MAX_BODY = 900_000  # bytes per request, under the API's 1,000,000
NAME = 512  # ids, sessions, titles, author fields, each `about`
MAX_ABOUT = 20
STATUS_IDS = 500  # per status call

# What a GitHub record is, by its event type.
GITHUB_KIND = {"github.pull-request": "pull_request", "github.issue": "issue", "github.review": "review"}


# --------------------------------------------------------------------------------------------
# Reading the corpus


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_records(data: Path = DATA, planted: bool = True) -> list[dict[str, Any]]:
    """Every record, oldest first. The corpus in id order and then the planted email, sorted by time
    with a stable sort: the order the pilot loaded them in."""
    records = sorted((r for name in CORPUS_FILES for r in read_jsonl(data / name)), key=lambda r: r["id"])
    if planted:
        records += sorted(read_jsonl(data / PLANTED_FILE), key=lambda r: r["id"])
    return sorted(records, key=lambda r: r["at"])


# --------------------------------------------------------------------------------------------
# One record as one item


def _cut(value: Any, n: int = NAME) -> str:
    return str(value)[:n]


def _author(who: dict[str, Any]) -> dict[str, Any]:
    """A person as an author: one id across sources, their address (every Kiln person has one), so
    that Slack, GitHub and Google name the same people."""
    out = {"id": _cut(who.get("email") or who.get("id")), "name": _cut(who.get("name") or "")}
    if who.get("email"):
        out["email"] = _cut(who["email"])
    if who.get("handle"):
        out["handle"] = _cut(who["handle"])
    if who.get("self"):
        out["self"] = True
    return out


def _names(rec: dict[str, Any], role: str) -> list[str]:
    return [p["name"] for p in rec.get("fields", {}).get("people") or [] if p.get("role") == role]


def _work(rec: dict[str, Any]) -> tuple[str, str]:
    """The first issue or pull request a record is about: (`pull request`|`issue`, `kiln/scheduler#310`)."""
    for ref in rec.get("fields", {}).get("refs") or []:
        kind, _, ident = ref.partition(":")
        return kind.replace("_", " "), ident
    return "", ""


def _when(iso: str) -> str:
    return iso[:16].replace("T", " ")


def _text(rec: dict[str, Any]) -> tuple[str, str]:
    """(text, how): the record's own words, `as-is`; with a short lead saying what happened when the
    kind of event says something its words do not, `labelled`; or, for an event with no words (a
    review approval, a file opened, a calendar entry), a line written from its fields, `described`."""
    f = rec.get("fields") or {}
    said = (rec.get("text") or "").strip()
    title = str(rec.get("title") or "").strip()
    verb, typ = f.get("verb") or "", f.get("type") or ""
    source = rec["source"]
    who = (rec.get("author") or f.get("organizer") or {}).get("name") or ""
    work_kind, work = _work(rec)

    if source == "google/calendar":
        line = (f"Calendar event {verb}: {title}, {_when(f.get('starts_at', ''))} to {_when(f.get('ends_at', ''))} UTC"
                f" (time zone {f.get('time_zone', 'UTC')}).")
        where = (f.get("location") or "").strip()
        if where:
            line += f" Location: {where}."
        if who:
            line += f" Organiser: {who}."
        attendees = [f"{p['name']} ({p['state']})" if p.get("state") else p["name"]
                     for p in f.get("people") or [] if p.get("role") == "attendee"]
        if attendees:
            line += " Attendees: " + ", ".join(attendees) + "."
        return (line + ("\n\n" + said if said else "")), "described"

    if source == "google/meet":
        if verb == "started":
            line = f"{title} started."
            if who:
                line += f" Organiser: {who}."
            if _names(rec, "attendee"):
                line += " Attendees: " + ", ".join(_names(rec, "attendee")) + "."
            return line, "described"
        if verb == "ended":
            return f"{title} ended.", "described"
        if verb == "action_item_created":
            assignees = _names(rec, "assignee")
            lead = f"Action item{' for ' + ', '.join(assignees) if assignees else ''}: "
            return lead + said, "labelled"
        if verb == "decision_mentioned":
            return "Decision: " + said, "labelled"
        return said, "as-is"

    if source == "cursor/sessions":
        if verb == "file_opened":
            return f"Opened {title} in Cursor.", "described"
        if verb == "code_accepted":
            return f"Accepted a change to {title}: {said}", "labelled"
        if verb == "terminal_executed":
            return f"Ran in the terminal: {said}", "labelled"
        return said, "as-is"

    if source == "github/notifications":
        what = verb.replace("_", " ")
        line = f"GitHub notification ({what}) on {work_kind or 'item'} {work}: {title}."
        reviewers = _names(rec, "reviewer")
        if reviewers:
            line += " Reviewers: " + ", ".join(reviewers) + "."
        return (line + "\n\n" + said, "labelled") if said else (line, "described")

    if typ == "github.star":
        return f"{who} starred {title}.", "described"

    if source == "github/owned-repos":
        sha = str(f.get("sha") or "")[:7]
        branch = f.get("branch")
        lead = f"Commit {sha} to {f.get('repo', '')}" + (f" on {branch}" if branch else "") + ": "
        return lead + said, "labelled"

    if typ == "github.push":
        ref = str(f.get("ref") or "").replace("refs/heads/", "")
        return f"Pushed to {ref} in {f.get('repo', '')}: {said}", "labelled"

    kind = GITHUB_KIND.get(typ)
    if kind:
        noun = work_kind or ("issue" if kind == "issue" else "pull request")
        if verb == "opened":
            return f"{who} opened {noun} {work}: {title}" + ("\n\n" + said if said else ""), "labelled"
        if verb == "closed":
            line = f"{who} {'merged' if f.get('merged') else 'closed'} {noun} {work}: {title}."
            return (line + ("\n\n" + said if said else "")), ("labelled" if said else "described")
        if verb == "ready_for_review":
            line = f"{who} marked {noun} {work} ready for review: {title}."
            return (line + ("\n\n" + said if said else "")), ("labelled" if said else "described")
        if verb == "approved":
            line = f"{who} approved {noun} {work}: {title}."
            return (line + ("\n\n" + said if said else "")), ("labelled" if said else "described")
        if verb == "changes_requested":
            line = f"{who} requested changes on {noun} {work}: {title}."
            return (line + ("\n\n" + said if said else "")), ("labelled" if said else "described")

    if not said:
        # Not in this corpus: every kind of event without words is described above.
        return f"{who} {verb.replace('_', ' ')} {title}".strip() + ".", "described"
    return said, "as-is"


def item_for(rec: dict[str, Any]) -> dict[str, Any]:
    """One corpus record as one item of POST /v2/memory/add."""
    provider, feed = rec["source"].split("/", 1)
    f = rec.get("fields") or {}
    text, how = _text(rec)

    item: dict[str, Any] = {
        "id": _cut(rec["id"]),
        "kind": "note" if feed == "calendar" else "message",
        "at": rec["at"],
        "text": text,
    }

    # Who said it. A coding assistant's reply is the assistant's; a GitHub notification is GitHub's.
    if provider in ("claude", "cursor") and rec.get("role") == "assistant":
        item["author"] = {"id": provider, "name": "Claude" if provider == "claude" else "Cursor"}
        item["role"] = "assistant"
    elif feed == "notifications":
        item["author"] = {"id": "github", "name": "GitHub"}
        item["role"] = "bot"
    else:
        who = rec.get("author") or f.get("organizer")
        if who:
            item["author"] = _author(who)
        if provider in ("claude", "cursor") and rec.get("role") == "user":
            item["role"] = "user"

    session = (rec.get("conversation") or {}).get("id")
    if session:
        item["session"] = _cut(session)
    if rec.get("title"):
        item["title"] = _cut(rec["title"])

    about = []
    if f.get("repo"):
        about.append(f"repo:{f['repo']}")
    about += list(f.get("refs") or [])
    if provider == "slack" and f.get("channel"):
        about.append(f"channel:{f['channel']}")
    about = list(dict.fromkeys(_cut(a) for a in about))[:MAX_ABOUT]
    if about:
        item["about"] = about

    meta: dict[str, Any] = {
        "source": rec["source"],
        "type": f.get("type"),
        "verb": f.get("verb") or "",
        "event_id": f.get("event_id"),
        "text": how,
    }
    if f.get("url"):
        meta["url"] = f["url"]
    people = [{"role": p.get("role"), "name": p.get("name"), **({"email": p["email"]} if p.get("email") else {})}
              for p in f.get("people") or []]
    if people:
        meta["participants"] = people
    for k in ("starts_at", "ends_at", "time_zone", "edited_at", "state", "labels", "merged", "merged_at", "ref",
              "sha", "branch", "files"):
        if k in f:
            meta[k] = f[k]
    item["metadata"] = meta
    return item


def plan(data: Path = DATA, planted: bool = True) -> list[dict[str, Any]]:
    return [item_for(r) for r in read_records(data, planted)]


def batches(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    """In order, at most `size` items and MAX_BODY bytes each."""
    out: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    cur_bytes = len(b'{"items":[]}')
    for item in items:
        n = len(json.dumps(item, ensure_ascii=False).encode("utf-8")) + 1
        if cur and (len(cur) >= size or cur_bytes + n > MAX_BODY):
            out.append(cur)
            cur, cur_bytes = [], len(b'{"items":[]}')
        cur.append(item)
        cur_bytes += n
    if cur:
        out.append(cur)
    return out


def body_of(batch: list[dict[str, Any]]) -> bytes:
    return json.dumps({"items": batch}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(groups: list[list[dict[str, Any]]]) -> str:
    """Names this exact load: the same corpus, mapping and batch size give the same digest."""
    h = hashlib.sha256()
    for g in groups:
        h.update(body_of(g))
        h.update(b"\n")
    return h.hexdigest()


# --------------------------------------------------------------------------------------------
# Talking to the API


class Stop(Exception):
    """A response that retrying will not fix; the message says what to do."""


def post(api: str, path: str, key: str, user: str, body: bytes, request_id: str,
         idempotency_key: str = "", timeout: float = 60.0) -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {
        "Authorization": f"Bearer {key}",
        "X-Alexein-User": user,
        "Content-Type": "application/json",
        "User-Agent": "team-knowledge-bench-loader/1",
        "X-Request-Id": request_id,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    req = urllib.request.Request(api + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            answer = json.loads(raw) if raw else {}
        except ValueError:
            answer = {"detail": raw.decode("utf-8", "replace")[:500]}
        return e.code, answer, dict(e.headers or {})


RETRY = {429, 500, 502, 503, 504}


def send(post_fn, *, attempts: int, sleep=time.sleep, **kw) -> tuple[int, dict[str, Any], dict[str, str]]:
    """One request, retried on 429 and 5xx (after Retry-After when given) and on network errors,
    with backoff. Any other answer is returned as it is."""
    delay = 2.0
    for attempt in range(1, attempts + 1):
        try:
            status, answer, headers = post_fn(**kw)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            status, answer, headers = 0, {"detail": f"network: {e}"}, {}
        if status not in RETRY and status != 0:
            return status, answer, headers
        if attempt == attempts:
            return status, answer, headers
        wait = delay
        retry_after = {k.lower(): v for k, v in headers.items()}.get("retry-after")
        if retry_after:
            try:
                wait = max(float(retry_after), 0.5)
            except ValueError:
                pass
        print(f"  {status or 'network error'}: {str(answer.get('detail', ''))[:120]}; retrying in {wait:.0f}s "
              f"({attempt}/{attempts})", file=sys.stderr, flush=True)
        sleep(wait)
        delay = min(delay * 2, 120.0)
    raise AssertionError("unreachable")


def _state_path(base: Path, api: str, user: str) -> Path:
    host = urllib.parse.urlsplit(api).netloc.replace(":", "_") or "api"
    return base / f"{host}-{user}.json"


def _read_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, path)


def load(groups: list[list[dict[str, Any]]], *, api: str, key: str, user: str, state_path: Path,
         pace: float, attempts: int, post_fn=post, sleep=time.sleep) -> int:
    """Send every batch not yet accepted; returns 0 when all are, else an exit code."""
    plan_digest = digest(groups)
    state = _read_state(state_path)
    if state.get("plan") != plan_digest:
        if state:
            print(f"{state_path} is for a different load (another corpus, mapping or batch size); starting at batch 1")
        state = {"plan": plan_digest, "api": api, "user": user, "batches": len(groups), "done": 0}
    done = int(state.get("done", 0))
    total_items = sum(len(g) for g in groups)
    print(f"{total_items} items in {len(groups)} batches for X-Alexein-User {user!r} at {api}; "
          f"{done} batches already accepted (state: {state_path})")
    for i in range(done, len(groups)):
        g = groups[i]
        status, answer, headers = send(
            post_fn, attempts=attempts, sleep=sleep,
            api=api, path="/v2/memory/add", key=key, user=user, body=body_of(g),
            request_id=f"kiln-load-{plan_digest[:12]}-{i:05d}",
            idempotency_key=f"kiln-load-{plan_digest[:12]}-{i:05d}",
        )
        if status == 402:
            print(f"batch {i + 1}: 402, the plan's events are used: {answer.get('detail') or answer}\n"
                  f"Nothing of this batch was stored. Run again after {answer.get('resets_at', 'the reset')} "
                  "or an upgrade; it resumes here.", file=sys.stderr)
            return 2
        if status not in (200, 202):
            print(f"batch {i + 1}: {status or 'network error'}: {answer.get('detail') or answer}\n"
                  "Stopped; run again to resume here.", file=sys.stderr)
            return 1
        got = [x.get("id") for x in answer.get("items") or []]
        sent = [x["id"] for x in g]
        if got != sent:
            print(f"batch {i + 1}: the answer names other items than were sent ({len(got)} vs {len(sent)}); "
                  "stopped", file=sys.stderr)
            return 1
        left = {k.lower(): v for k, v in headers.items()}.get("x-alexein-events-remaining")
        state.update(done=i + 1, updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     events_remaining=left)
        _write_state(state_path, state)
        sent_items = sum(len(x) for x in groups[: i + 1])
        print(f"batch {i + 1}/{len(groups)}: {status}, {sent_items}/{total_items} items"
              + (f", events left this month: {left}" if left is not None else ""), flush=True)
        if pace and i + 1 < len(groups):
            sleep(pace)
    print("all batches accepted. Items are searchable within seconds; facts are learned in the background, "
          "usually within minutes. `--check --wait` says when every item is processed.")
    return 0


def check(ids: list[str], *, api: str, key: str, user: str, wait: bool, every: float,
          post_fn=post, sleep=time.sleep) -> int:
    """Tally /v2/memory/status for every id (free); with `wait`, until none is queued or stored."""
    while True:
        tally: dict[str, int] = {}
        reasons: dict[str, int] = {}
        for i in range(0, len(ids), STATUS_IDS):
            chunk = ids[i:i + STATUS_IDS]
            status, answer, _ = send(post_fn, attempts=6, sleep=sleep, api=api, path="/v2/memory/status",
                                     key=key, user=user, body=json.dumps({"items": chunk}).encode(),
                                     request_id=f"kiln-status-{i:05d}")
            if status != 200:
                print(f"status: {status or 'network error'}: {answer.get('detail') or answer}", file=sys.stderr)
                return 1
            for x in answer.get("items") or []:
                tally[x.get("status")] = tally.get(x.get("status"), 0) + 1
                if x.get("reason"):
                    reasons[x["reason"]] = reasons.get(x["reason"], 0) + 1
        print("status: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())), flush=True)
        for r, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:5]:
            print(f"  {n} x {r}")
        pending = tally.get("queued", 0) + tally.get("stored", 0)
        if tally.get("unknown"):
            print(f"{tally['unknown']} ids are unknown: not loaded yet, or loaded under another X-Alexein-User")
        if not wait or not pending:
            return 0 if not pending and not tally.get("unknown") else 3
        sleep(every)


# --------------------------------------------------------------------------------------------


def verify(root: Path = ROOT, sums: Path = SUMS) -> int:
    bad = 0
    lines = sums.read_text().splitlines()
    for line in lines:
        want, rel = line.split("  ", 1)
        p = root / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != want:
            print(f"mismatch: {rel}")
            bad += 1
    print(f"{len(lines)} files checked, {bad} mismatched")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load the Kiln corpus through POST /v2/memory/add.")
    ap.add_argument("--data", type=Path, default=DATA, help="the directory of the corpus files (default data/kiln)")
    ap.add_argument("--no-planted", action="store_true", help="leave out the planted email (T10)")
    ap.add_argument("--user", default=os.environ.get("ALEXEIN_USER") or DEFAULT_USER,
                    help="X-Alexein-User (default: $ALEXEIN_USER or 'me')")
    ap.add_argument("--api", default=(os.environ.get("ALEXEIN_API_URL") or DEFAULT_API).rstrip("/"))
    ap.add_argument("--batch", type=int, default=100, help=f"items per request, 1 to {MAX_ITEMS} (default 100)")
    ap.add_argument("--pace", type=float, default=0.5, help="seconds between requests (default 0.5)")
    ap.add_argument("--attempts", type=int, default=8, help="tries per request on 429, 5xx or network errors")
    ap.add_argument("--state", type=Path, default=ROOT / ".load-state", help="directory for the progress file")
    ap.add_argument("--dry-run", type=int, metavar="N", help="print the first N request bodies and a summary; no network")
    ap.add_argument("--yes", action="store_true", help="really load: it adds ~12,022 items, one plan event each")
    ap.add_argument("--check", action="store_true", help="report /v2/memory/status for every item (free)")
    ap.add_argument("--wait", action="store_true", help="with --check: repeat until every item is processed")
    ap.add_argument("--every", type=float, default=60.0, help="with --wait: seconds between checks")
    ap.add_argument("--verify", action="store_true", help="check the data files against data/kiln/SHA256SUMS")
    a = ap.parse_args(argv)

    if a.verify:
        return verify()
    if not 1 <= a.batch <= MAX_ITEMS:
        ap.error(f"--batch must be 1 to {MAX_ITEMS}")
    items = plan(a.data, planted=not a.no_planted)
    groups = batches(items, a.batch)

    if a.dry_run is not None:
        for i, g in enumerate(groups[: a.dry_run]):
            print(f"--- request {i + 1} of {len(groups)}: POST {a.api}/v2/memory/add  X-Alexein-User: {a.user}  "
                  f"Idempotency-Key: kiln-load-{digest(groups)[:12]}-{i:05d}  ({len(body_of(g))} bytes)")
            print(json.dumps({"items": g}, ensure_ascii=False, indent=1))
        kinds: dict[str, int] = {}
        how: dict[str, int] = {}
        for it in items:
            kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
            how[it["metadata"]["text"]] = how.get(it["metadata"]["text"], 0) + 1
        print(f"--- {len(items)} items in {len(groups)} requests; kinds {kinds}; text {how}; "
              f"largest request {max(len(body_of(g)) for g in groups)} bytes; "
              f"{items[0]['at']} .. {items[-1]['at']}; plan digest {digest(groups)}")
        return 0

    key = os.environ.get("ALEXEIN_API_KEY", "").strip()
    if not key:
        print("set ALEXEIN_API_KEY (a key that writes, for loading; a read key is enough for --check)", file=sys.stderr)
        return 1
    if a.check:
        return check([it["id"] for it in items], api=a.api, key=key, user=a.user, wait=a.wait, every=a.every)
    if not a.yes:
        print(f"This adds {len(items)} items for X-Alexein-User {a.user!r} at {a.api}: {len(items)} events of your "
              "plan's month, and facts learned from them count toward your daily budget. Run again with --yes.")
        return 1
    return load(groups, api=a.api, key=key, user=a.user, state_path=_state_path(a.state, a.api, a.user),
                pace=a.pace, attempts=a.attempts)


if __name__ == "__main__":
    sys.exit(main())
