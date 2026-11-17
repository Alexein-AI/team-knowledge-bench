/** Headers for a rate-limited response. `resetInSeconds` is how long until the window resets. */
export function rateLimitHeaders(
  limit: number,
  remaining: number,
  resetInSeconds: number,
  now: Date = new Date(),
): Record<string, string> {
  return {
    "X-RateLimit-Limit": String(limit),
    "X-RateLimit-Remaining": String(Math.max(0, remaining)),
    "X-RateLimit-Reset": String(resetInSeconds),
  };
}
