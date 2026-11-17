export interface DispatchStats {
  /** Jobs waiting in the queue now. */
  queued: number;
  /** Jobs dispatched in the last window. */
  dispatchedInWindow: number;
  /** Machines that could take a job now, as the scheduler's slot table sees it. */
  freeCapacity: number;
}

/** Whether to page the on-call engineer about a stalled dispatcher. */
export function shouldPageStalledDispatch(stats: DispatchStats): boolean {
  return false;
}
