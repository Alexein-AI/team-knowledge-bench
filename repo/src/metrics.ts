export interface Gauge {
  name: string;
  value: number;
}

/** Jobs queued, per org. */
export function queueDepth(queued: Record<string, number>): Gauge[] {
  return Object.entries(queued).map(([org, n]) => ({ name: `queue_depth{org="${org}"}`, value: n }));
}
