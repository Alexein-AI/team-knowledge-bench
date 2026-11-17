export interface AdminRequest {
  method: string;
  path: string;
  headers: Record<string, string>;
  actor: string;
}

export interface AuditEntry {
  [field: string]: unknown;
}

/** One audit entry for an admin action, as stored for the SOC 2 evidence. */
export function auditEntry(req: AdminRequest, action: string, now: Date = new Date()): AuditEntry {
  return {};
}
