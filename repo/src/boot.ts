export type ColdStart = "warm-pool" | "prebaked";

export interface Runner {
  id: string;
  image: string;
}

/** Take an already-initialised machine from the warm pool. */
export async function claimFromWarmPool(pool: Runner[]): Promise<Runner | undefined> {
  return pool.shift();
}

/** Boot a fresh machine from the prebaked image for this toolchain. */
export async function bootPrebakedImage(image: string): Promise<Runner> {
  return { id: `r-${Math.random().toString(36).slice(2, 8)}`, image };
}

/** Which cold-start path a new job takes. */
export function chooseColdStart(): ColdStart {
  throw new Error("not decided");
}
