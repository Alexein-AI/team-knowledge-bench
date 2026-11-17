export type Plan = "free" | "team" | "business" | "enterprise";

export const PLAN_WEIGHT: Record<Plan, number> = { free: 1, team: 4, business: 16, enterprise: 64 };

export interface PlanRow {
  org: string;
  plan: Plan;
}

/** The weight an org gets, from its row in org_plan. */
export function weightFor(org: string, rows: PlanRow[]): number {
  const row = rows.find((r) => r.org === org);
  if (!row) throw new Error(`no org_plan row for ${org}`);
  return PLAN_WEIGHT[row.plan];
}

/** How many machines an org is owed right now, given every queued org's weight. */
export function shareOf(weight: number, totalWeight: number, fleet: number): number {
  if (totalWeight <= 0) return 0;
  return Math.floor((weight * fleet) / totalWeight);
}
