export const RENEW_INTERVAL_MS = 30_000;

export interface Lease {
  id: string;
  org: string;
  expiresAt: number;
}

/** Calls `renew` on a timer for as long as the job runs; returns a stop function. */
export function startRenewal(renew: () => void): () => void {
  const timer = setInterval(renew, RENEW_INTERVAL_MS);
  return () => clearInterval(timer);
}
