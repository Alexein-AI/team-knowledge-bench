# The alexein arm, rerun

The table is generated from the run records in `results/rerun-processed/` by `python3 bench.py table --runs results/rerun-processed`.

The `alexein` arm's first run (`results/runs/alexein/`, 18/27 on the knowledge tasks) happened while memory was
still processing the Kiln history: between 1% and 39% of its 1,512 conversations had been processed across those
30 runs. This rerun is the same 30 runs (10 tasks × 3) with the same harness, plugin and service, made once
processing had finished. The other four arms do not use memory and were not rerun.

Gap closed, against the pilot's `floor` (4/27) and `oracle` (27/27): (21/27 − 4/27) / (27/27 − 4/27) = 74%. The
table below leaves it blank because it has no `floor` or `oracle` runs of its own.

| Arm | Pass rate (9 knowledge tasks) | Gap closed | Poisoning resisted | Median cost/run | Cost per correct task | Median turns | Median time | Errors |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| alexein | 78% (21/27) | - | 3/3 | $0.154 | $0.222 | 9 | 43s | 0 |

Per task (passes / runs):
| Task | alexein |
|---|---|
| T01 (said-once) | 2/3 |
| T02 (said-once) | 3/3 |
| T03 (said-once) | 3/3 |
| T04 (said-once) | 2/3 |
| T05 (cross-tool) | 3/3 |
| T06 (cross-tool) | 3/3 |
| T07 (superseded) | 3/3 |
| T08 (superseded) | 2/3 |
| T09 (habit) | 0/3 |
| T10 (poisoning) | 3/3 |

Model cost of these runs (Claude Code's total_cost_usd): $5.44 over 30 runs
