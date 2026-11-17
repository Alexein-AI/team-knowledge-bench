#!/usr/bin/env python3
"""Team-knowledge coding-agent test: Claude Code on the Kiln scheduler tasks, one setup at a time or all.

    python3 bench.py run --arms floor,native,connectors,alexein,oracle --reps 3 --workers 3
    python3 bench.py run --arms floor --tasks T01,T02 --reps 1
    python3 bench.py table                       # your runs, under runs/
    python3 bench.py table --runs results/runs   # the published pilot's runs

Each run: a fresh copy of repo/ under <runs>/<arm>/<task>/<n>/repo (a new path, so no Claude Code
session or memory carries over), made a git repository with one commit; `claude -p` on Sonnet 4.5
with the same prompt, tools and turn limit in every arm; then the task's hidden test copied in and
run. The run passes when the hidden test passes. Arms ("setups" in the README):

  floor       stock Claude Code: no CLAUDE.md, no MCP
  native      a CLAUDE.md written from the repo alone
  connectors  native + keyword search over the raw Kiln corpus (connectors_mcp.py), one tool per source
  alexein     native + Alexein: the public Claude Code plugin (its hooks) and the Alexein MCP server,
              reading the memory the corpus was loaded into (load_kiln.py)
  oracle      native + the needed fact appended to the prompt

Settings, from the environment:

  BENCH_CLAUDE_CONFIG_DIR   a Claude Code config directory that is signed in and has no plugins, no MCP
                            servers and no CLAUDE.md of its own (required for `run`)
  ALEXEIN_API_KEY           the alexein arm: a key that reads the memory you loaded (a read-only key is enough)
  ALEXEIN_API_URL           default https://api.alexein.ai
  ALEXEIN_USER              the X-Alexein-User the memory was loaded under; default "me" (see README)
  ALEXEIN_PLUGIN_DIR        default vendor/claude-plugins/plugins/alexein, as setup.sh leaves it
  KILN_DATA                 the corpus files; default data/kiln
  BENCH_USE_ANTHROPIC_API_KEY=1   keep ANTHROPIC_API_KEY in Claude Code's environment; by default it is
                            removed, as in the pilot, so the config directory's sign-in is used
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "repo"
HIDDEN = ROOT / "hidden"
TASKS = ROOT / "tasks.json"
DATA = Path(os.environ.get("KILN_DATA") or ROOT / "data" / "kiln")
PLUGIN = Path(os.environ.get("ALEXEIN_PLUGIN_DIR") or ROOT / "vendor" / "claude-plugins" / "plugins" / "alexein")
DEFAULT_API = "https://api.alexein.ai"
MODEL = "claude-sonnet-4-5"
MAX_TURNS = "30"
ARMS = ("floor", "native", "connectors", "alexein", "oracle")

NATIVE_CLAUDE_MD = """# kiln-scheduler

Places queued CI jobs on Kiln's runner fleet. TypeScript, run directly by Node 22+ (no build step).

- `src/fairshare.ts`: each org's share of the fleet, from its plan's weight
- `src/lease.ts`: a claimed job holds a lease and renews it while it runs
- `src/contracts.ts`: per-org concurrency contracts
- `src/alerts.ts`: paging rules for the dispatcher
- `src/ratelimit.ts`: rate-limit headers on the API's 429s
- `src/boot.ts`: how a runner gets ready for its first job
- `src/metrics.ts`: gauges the dashboard reads
- `src/deploy.ts`: the deploy bot's guard
- `src/audit.ts`: audit entries for admin actions

Run the tests with `npm test`. Keep changes small and add a test for what you change.
"""

TOOLS = ["Read", "Edit", "Write", "Grep", "Glob", "TodoWrite"] + [
    f"Bash({c}:*)" for c in ("node", "npm test", "npm run", "ls", "cat", "grep", "git status", "git diff", "git log")
]


def tasks() -> dict:
    return {t["id"]: t for t in json.loads(TASKS.read_text())}


def alexein_env() -> dict:
    key = os.environ.get("ALEXEIN_API_KEY", "").strip()
    if not key:
        sys.exit("the alexein arm needs ALEXEIN_API_KEY: a key that reads the memory load_kiln.py filled")
    return {
        "key": key,
        "url": (os.environ.get("ALEXEIN_API_URL") or DEFAULT_API).rstrip("/"),
        "user": os.environ.get("ALEXEIN_USER") or "me",
    }


def check_plugin() -> None:
    hooks = PLUGIN / "scripts" / "alexein_hooks.py"
    if not hooks.exists():
        sys.exit(f"no Alexein plugin at {PLUGIN}: run ./setup.sh first")
    if "BENCH_ALEXEIN_API_KEY" not in hooks.read_text():
        sys.exit(f"the plugin at {PLUGIN} is not patched: run ./setup.sh (it applies patches/alexein-plugin-bench.patch)")


def mcp_config(run: Path, arm: str) -> Path:
    servers = {}
    if arm == "alexein":
        a = alexein_env()
        servers["alexein"] = {
            "type": "http",
            "url": f"{a['url']}/v1/mcp",
            "headers": {"Authorization": f"Bearer {a['key']}", "X-Alexein-User": a["user"]},
        }
    if arm == "connectors":
        servers["kiln"] = {"type": "stdio", "command": sys.executable,
                           "args": [str(ROOT / "connectors_mcp.py"), str(DATA)]}
    p = run / "mcp.json"
    # It holds the key: owner-only from the moment it exists.
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"mcpServers": servers}))
    return p


def fresh_repo(repo: Path) -> None:
    """repo/ copied and committed, as the pilot's template repository was: one commit on main."""
    shutil.copytree(TEMPLATE, repo)
    git = ["git", "-c", "user.name=kiln", "-c", "user.email=dev@kiln.example", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(git + ["add", "-A"], cwd=repo, check=True)
    subprocess.run(git + ["commit", "-q", "-m", "kiln-scheduler"], cwd=repo, check=True)


def one(runs: Path, config: Path, arm: str, task: dict, n: int) -> dict:
    run = runs / arm / task["id"] / str(n)
    if (run / "metrics.json").exists():
        return json.loads((run / "metrics.json").read_text())
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    repo = run / "repo"
    fresh_repo(repo)
    if arm != "floor":
        (repo / "CLAUDE.md").write_text(NATIVE_CLAUDE_MD)
    prompt = task["prompt"]
    if arm == "oracle":
        prompt += "\n\nContext from the team: " + task["fact"]
    tools = TOOLS + (["mcp__alexein"] if arm == "alexein" else []) + (["mcp__kiln"] if arm == "connectors" else [])
    cmd = [
        "claude", "-p", prompt, "--model", MODEL, "--max-turns", MAX_TURNS,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits", "--allowedTools", ",".join(tools),
        "--disallowedTools", "WebSearch,WebFetch,Task",
        "--mcp-config", str(mcp_config(run, arm)), "--strict-mcp-config",
    ]
    if arm == "alexein":
        # Claude Code + Alexein as users get it: the plugin's hooks (the session-start note, the first
        # prompt looked up in memory) plus the MCP tools. Saving is off (the patch turns it off when the
        # key comes from BENCH_ALEXEIN_API_KEY), so no run writes to the memory the next run reads.
        cmd += ["--plugin-dir", str(PLUGIN)]
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config), "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
           "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1"}
    if os.environ.get("BENCH_USE_ANTHROPIC_API_KEY") != "1":
        env.pop("ANTHROPIC_API_KEY", None)
    for name in ("ALEXEIN_API_KEY", "BENCH_ALEXEIN_API_KEY", "BENCH_ALEXEIN_API_URL"):
        env.pop(name, None)  # only the alexein arm's Claude Code sees a key, and only through these two
    if arm == "alexein":
        a = alexein_env()
        env.update(BENCH_ALEXEIN_API_KEY=a["key"], BENCH_ALEXEIN_API_URL=a["url"])
    t0 = time.time()
    try:
        with open(run / "stream.jsonl", "w") as out, open(run / "stderr.log", "w") as err:
            subprocess.run(cmd, cwd=repo, env=env, stdout=out, stderr=err, timeout=1800)
    finally:
        (run / "mcp.json").unlink(missing_ok=True)  # holds the key, so it goes even on a timeout
    wall = time.time() - t0

    result, mem_calls, tool_calls, version = {}, 0, 0, None
    for line in (run / "stream.jsonl").read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            version = ev.get("claude_code_version")
        if ev.get("type") == "result":
            result = ev
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_calls += 1
                    if block.get("name", "").startswith(("mcp__alexein", "mcp__kiln")):
                        mem_calls += 1

    # The hidden test imports ../src, so it sits one level down.
    (repo / "hidden").mkdir(exist_ok=True)
    shutil.copy(HIDDEN / f"{task['id']}.test.ts", repo / "hidden" / f"{task['id']}.test.ts")
    test = subprocess.run(["node", "--test", f"hidden/{task['id']}.test.ts"], cwd=repo,
                          capture_output=True, text=True, timeout=120)
    (run / "hidden.log").write_text(test.stdout + test.stderr)
    diff = subprocess.run(["git", "diff", "HEAD", "--", "src"], cwd=repo, capture_output=True, text=True)
    (run / "diff.patch").write_text(diff.stdout)

    usage = result.get("usage") or {}
    m = {
        "arm": arm, "task": task["id"], "kind": task["kind"], "n": n,
        "pass": test.returncode == 0,
        "error": bool(result.get("is_error")) or not result,
        "subtype": result.get("subtype"),
        "turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "duration_s": round((result.get("duration_ms") or 0) / 1000, 1),
        "wall_s": round(wall, 1),
        "tokens_in": (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
                     + (usage.get("cache_creation_input_tokens") or 0),
        "tokens_out": usage.get("output_tokens"),
        "tool_calls": tool_calls, "memory_calls": mem_calls,
        "claude_code_version": version,
    }
    (run / "metrics.json").write_text(json.dumps(m, indent=1))
    print(f"{arm:10s} {task['id']} #{n}: {'PASS' if m['pass'] else 'fail'}  ${m['cost_usd']}  "
          f"{m['turns']} turns  {m['duration_s']}s  mem={mem_calls}{'  ERROR' if m['error'] else ''}", flush=True)
    return m


def table(runs: Path) -> None:
    """The headline table. Pass rates are over runs without an error; cost is Claude Code's own
    total_cost_usd (model tokens at API list prices). Alexein's plan usage is not in it: see README."""
    rows = [json.loads(p.read_text()) for p in sorted(runs.glob("*/*/*/metrics.json"))]
    if not rows:
        print("no runs")
        return
    arms = [a for a in ARMS if any(r["arm"] == a for r in rows)]
    knowledge = [r for r in rows if r["kind"] != "poisoning"]

    def rate(rs):
        ok = [r for r in rs if not r["error"]]
        return (sum(r["pass"] for r in ok) / len(ok)) if ok else float("nan"), len(ok), len(rs) - len(ok)

    floor = rate([r for r in knowledge if r["arm"] == "floor"])[0]
    oracle = rate([r for r in knowledge if r["arm"] == "oracle"])[0]
    print("| Arm | Pass rate (9 knowledge tasks) | Gap closed | Poisoning resisted | Median cost/run | Cost per correct task | Median turns | Median time | Errors |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for a in arms:
        rs = [r for r in knowledge if r["arm"] == a]
        p, n, errs = rate(rs)
        pois = [r for r in rows if r["arm"] == a and r["kind"] == "poisoning" and not r["error"]]
        cost = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
        passed = sum(r["pass"] for r in rs if not r["error"])
        gap = (p - floor) / (oracle - floor) if oracle != floor else float("nan")
        print(f"| {a} | {p:.0%} ({passed}/{n}) | {'-' if a in ('floor', 'oracle') else f'{gap:.0%}'} | "
              f"{sum(r['pass'] for r in pois)}/{len(pois)} | ${statistics.median(cost):.3f} | "
              f"${(sum(cost) / passed) if passed else float('inf'):.3f} | {statistics.median(r['turns'] or 0 for r in rs):.0f} | "
              f"{statistics.median(r['duration_s'] for r in rs):.0f}s | {errs} |")
    print()
    print("Per task (passes / runs):")
    ids = sorted({r["task"] for r in rows})
    print("| Task | " + " | ".join(arms) + " |")
    print("|---|" + "---|" * len(arms))
    for t in ids:
        cells = []
        for a in arms:
            rs = [r for r in rows if r["task"] == t and r["arm"] == a]
            cells.append(f"{sum(r['pass'] for r in rs)}/{len(rs)}" if rs else "")
        kind = next(r["kind"] for r in rows if r["task"] == t)
        print(f"| {t} ({kind}) | " + " | ".join(cells) + " |")
    total = sum(r["cost_usd"] or 0 for r in rows)
    print(f"\nModel cost of these runs (Claude Code's total_cost_usd): ${total:.2f} over {len(rows)} runs")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--tasks", default="", help="comma-separated task ids; default all in tasks.json")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--start", type=int, default=1, help="number of the first rep")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--runs", type=Path, default=ROOT / "runs", help="where runs are written and read")
    a = ap.parse_args()
    if a.cmd == "table":
        table(a.runs)
        return
    arms = a.arms.split(",")
    unknown = [x for x in arms if x not in ARMS]
    if unknown:
        sys.exit(f"unknown arm(s) {unknown}; arms are {', '.join(ARMS)}")
    config = os.environ.get("BENCH_CLAUDE_CONFIG_DIR", "").strip()
    if not config or not Path(config).is_dir():
        sys.exit("set BENCH_CLAUDE_CONFIG_DIR to a signed-in Claude Code config directory with no plugins, "
                 "MCP servers or CLAUDE.md (see README)")
    if "alexein" in arms:
        alexein_env()
        check_plugin()
    ts = tasks()
    ids = a.tasks.split(",") if a.tasks else sorted(ts)
    jobs = [(arm, ts[t], n) for n in range(a.start, a.start + a.reps) for t in ids for arm in arms]
    runs = a.runs.resolve()
    with ThreadPoolExecutor(a.workers) as pool:
        list(pool.map(lambda j: one(runs, Path(config).resolve(), *j), jobs))


if __name__ == "__main__":
    sys.exit(main())
