/** Per-org concurrency contracts: the most builds an org may run at once. */
export const CONTRACTS: Record<string, number> = {
  "kiln-internal": 4,
};

export const DEFAULT_CONCURRENCY = 4;

export function concurrencyFor(org: string): number {
  return CONTRACTS[org] ?? DEFAULT_CONCURRENCY;
}
