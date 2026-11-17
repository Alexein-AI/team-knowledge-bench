/** The deploy bot calls this before it ships to production on someone's `/ship`. */
export function canShip(now: Date): boolean {
  return true;
}
