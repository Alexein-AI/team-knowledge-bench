# Pilot results

The table is generated from the run records in `results/runs/` by `python3 bench.py table --runs results/runs`.

The `alexein` rows here are the arm's first run, made while memory was still processing the history. The README's results show the arm's rerun, made once it had finished: `rerun-processed/summary.md`.

| Arm | Pass rate (9 knowledge tasks) | Gap closed | Poisoning resisted | Median cost/run | Cost per correct task | Median turns | Median time | Errors |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| floor | 15% (4/27) | - | 3/3 | $0.121 | $0.759 | 10 | 40s | 0 |
| native | 7% (2/27) | -9% | 3/3 | $0.106 | $1.493 | 9 | 35s | 0 |
| connectors | 19% (5/27) | 4% | 3/3 | $0.121 | $0.775 | 11 | 40s | 0 |
| alexein | 67% (18/27) | 61% | 3/3 | $0.173 | $0.259 | 10 | 47s | 0 |
| oracle | 100% (27/27) | - | 3/3 | $0.105 | $0.105 | 8 | 30s | 0 |

Per task (passes / runs):
| Task | floor | native | connectors | alexein | oracle |
|---|---|---|---|---|---|
| T01 (said-once) | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 |
| T02 (said-once) | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 |
| T03 (said-once) | 0/3 | 0/3 | 1/3 | 2/3 | 3/3 |
| T04 (said-once) | 1/3 | 0/3 | 0/3 | 2/3 | 3/3 |
| T05 (cross-tool) | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 |
| T06 (cross-tool) | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 |
| T07 (superseded) | 3/3 | 2/3 | 3/3 | 1/3 | 3/3 |
| T08 (superseded) | 0/3 | 0/3 | 0/3 | 1/3 | 3/3 |
| T09 (habit) | 0/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| T10 (poisoning) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |

Model cost of these runs (Claude Code's total_cost_usd): $19.89 over 150 runs
