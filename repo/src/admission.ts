export interface OrgLoad {
  /** Jobs this org has waiting in the queue. */
  queued: number;
  /** Jobs this org has running now. */
  running: number;
  /** Machines this org is owed right now (fairshare.shareOf). */
  share: number;
}

/** The per-org queue-depth fuse: whether to refuse a new enqueue from this org. */
export function refuseEnqueue(load: OrgLoad): boolean {
  return false;
}
