# kiln-scheduler

Places queued CI jobs on Kiln's runner fleet.

- `src/fairshare.ts` - each org's share of the fleet, from its plan's weight
- `src/lease.ts` - a claimed job holds a lease and renews it while it runs
- `src/admission.ts` - whether a new enqueue is accepted
- `src/contracts.ts` - per-org concurrency contracts
- `src/alerts.ts` - paging rules for the dispatcher
- `src/ratelimit.ts` - rate-limit headers on the API's 429s
- `src/boot.ts` - how a runner gets ready for its first job
- `src/metrics.ts` - gauges the dashboard reads
- `src/deploy.ts` - the deploy bot's guard
- `src/audit.ts` - audit entries for admin actions

`npm test` runs the tests. Node 22+ runs the TypeScript directly.
