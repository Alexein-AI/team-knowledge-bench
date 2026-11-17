"""The "search tools" setup: plain keyword search over the raw Kiln corpus, as an MCP server on stdio.

    python3 connectors_mcp.py <data dir or .jsonl file> ...      # bench.py passes data/kiln

Our stand-in for live connectors. One tool per source, the way Slack, GitHub, Gmail and meeting
connectors each bring their own search: the score is how many of the query's words a message
contains, newest first among equals. No semantic matching, no learned ranking, no notion of what
replaced what - the raw messages, as a connector returns them.
"""
import json
import re
import sys
from pathlib import Path

SOURCES = {
    "search_slack": ("slack", "Search Slack messages in the Kiln workspace."),
    "search_github": ("github", "Search GitHub: issues, pull requests, reviews, comments and commits in the kiln org."),
    "search_gmail": ("google/gmail", "Search the engineer's Gmail."),
    "search_meetings": ("google/meet", "Search Google Meet transcripts."),
    "search_calendar": ("google/calendar", "Search Google Calendar events."),
    "search_past_sessions": ("claude|cursor", "Search past Claude Code and Cursor sessions on this machine."),
}
WORD = re.compile(r"[a-z0-9#._-]+")
STOP = set("a an the and or of to in on for is are was were be it this that with what how why when we our us i you do does did".split())
# A data directory's files, in the order they are read: the corpus, then the planted email.
FILES = ("slack.jsonl", "github.jsonl", "gmail.jsonl", "meet.jsonl", "calendar.jsonl", "sessions.jsonl",
         "planted-email.jsonl")
# The export the pilot searched held a Slack message's or an email's words twice (as the text and as
# its body), and the pilot's server matched and showed both. Kept, so results match the pilot's.
WORDS_TWICE = ("slack/", "google/gmail/")


def files(args):
    for a in args:
        a = Path(a)
        if a.is_dir():
            yield from (a / name for name in FILES if (a / name).exists())
        else:
            yield a


def load(args):
    """Every record with words, in file order: the order the pilot's server read the export in,
    which decides the order of results that score the same."""
    docs = []
    for path in files(args):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                said = r.get("text") or ""
                twice = [said] if (r["source"] + "/").startswith(WORDS_TWICE) else []
                text = " ".join(filter(None, [r.get("title"), said] + twice))
                if not text.strip():
                    continue
                docs.append({"path": r["source"] + "/", "id": (r.get("fields") or {}).get("event_id"),
                             "at": r["at"][:16], "author": (r.get("author") or {}).get("name") or "",
                             "where": r.get("place") or "", "text": " ".join(text.split()),
                             "words": set(WORD.findall(text.lower()))})
    return docs


def search(docs, prefix, query, limit=10):
    terms = [t for t in WORD.findall(query.lower()) if t not in STOP]
    pre = tuple(p + "/" for p in prefix.split("|"))
    scored = []
    for d in docs:
        if not d["path"].startswith(pre):
            continue
        s = sum(1 for t in terms if t in d["words"])
        if s:
            scored.append((s, d["at"], d))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    out = [f"[{d['at']}] {d['author']} in {d['where'] or '-'} ({d['id']}): {d['text'][:700]}" for _, _, d in scored[:limit]]
    return "\n\n".join(out) if out else "No results."


def main():
    docs = load(sys.argv[1:])
    tools = [{"name": name, "description": desc + " Plain keyword search; returns the best-matching messages.",
              "inputSchema": {"type": "object", "properties": {
                  "query": {"type": "string", "description": "Keywords to search for"},
                  "limit": {"type": "integer", "description": "Most results to return (default 10)"}},
                  "required": ["query"]}} for name, (_, desc) in SOURCES.items()]
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid, method = msg.get("id"), msg.get("method")
        if mid is None:  # a notification
            continue
        if method == "initialize":
            result = {"protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "kiln-connectors", "version": "0.1"},
                      "instructions": "Search the team's Slack, GitHub, Gmail, meetings, calendar and past coding sessions."}
        elif method == "tools/list":
            result = {"tools": tools}
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"].get("arguments") or {}
            text = search(docs, SOURCES[name][0], args.get("query", ""), int(args.get("limit") or 10)) \
                if name in SOURCES else f"unknown tool {name}"
            result = {"content": [{"type": "text", "text": text}]}
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": method}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}), flush=True)


if __name__ == "__main__":
    main()
