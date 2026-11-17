# Replaced runs

The first versions of T03 and T04 were run once in `floor`, `native`, `alexein` and `oracle` (round 1) and then
replaced, because `floor`, with no team knowledge, passed both:

- T03 asked for the rate-limit headers on the API's 429s. `floor` passed by following the usual convention
  (`X-RateLimit-Reset` as a Unix time, `Retry-After` in seconds), which needs no team knowledge.
- T04 asked for the lease renewal interval. `floor` passed by guessing 30 seconds.

Their hidden tests are in `hidden-round1/`. Their prompts were not kept in the records. All 8 runs passed; they
are not part of the published results. The current T03 and T04 (`tasks.json`, field `replaced`) were run three
times in every arm and are in `results/runs/`.

`python3 bench.py table --runs results/replaced` tabulates them. These runs started from the round-1 repository,
which lacked `src/admission.ts` and `RENEW_INTERVAL_MS` (`../template-round1-to-final.diff`).
