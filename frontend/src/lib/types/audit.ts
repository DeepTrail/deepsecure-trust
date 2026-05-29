/**
 * Shared TypeScript types for audit events.
 * Mirrors the backend AuditEventResponse Pydantic model from
 * deeptrail-control/app/api/v1/endpoints/audit.py
 */

export interface AuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  agent_id: string | null;
  on_behalf_of: string;
  organization_id: string | null;
  tool: string | null;
  success: boolean | null;
  arguments: Record<string, unknown> | null;
  result_summary: string | null;
  reason: string | null;
  attempted_tool: string | null;
  required_permission: string | null;
  duration_ms: number | null;
  session_id: string | null;
  agent_session_id: string | null;
  mcp_session_id: string | null;
  delegation_id: string | null;
  extra_data: Record<string, unknown> | null;
}

export interface AuditEventsResponse {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditSummary {
  total_events: number;
  by_event_type: Record<string, number>;
  by_tool: Record<string, number>;
  by_agent: Record<string, number>;
  time_range: Record<string, string>;
}

export type AuditEventType =
  | "mcp_tool_call"
  | "permission_denied"
  | "agent_auth"
  | "delegation_created"
  | "service_connected"
  | "sso_login";

export interface ServicePermissions {
  connected: boolean;
  service_name: string;
  scopes_granted: string[];
  available_permissions: string[];
  connected_at: string | null;
}

export interface AvailablePermissionsResponse {
  services: Record<string, ServicePermissions>;
  all_permissions: string[];
  total_services: number;
  total_permissions: number;
}
