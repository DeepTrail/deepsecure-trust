/**
 * Admin-specific TypeScript types for IT Admin pages.
 * Mirrors the backend admin endpoint Pydantic models from
 * deeptrail-control/app/api/v1/endpoints/admin_*.py
 */

// ---------------------------------------------------------------------------
// Service Registry
// ---------------------------------------------------------------------------

export type BackendType = "rest" | "mcp";
export type ServiceStatus = "active" | "sandbox" | "review" | "disabled";
export type HealthStatus = "up" | "down" | "slow" | "unknown";
export type McpAuthMethod = "none" | "api-key" | "bearer-token" | "oauth";
export type McpTransport = "rest" | "streamable-http" | "sse";
export type DataClassification = "internal" | "confidential" | "restricted";

export interface ServiceRegistryEntry {
  id: string;
  service_id: string;
  display_name: string;
  description: string | null;
  backend_type: BackendType;
  endpoint_url: string;
  transport: McpTransport;
  mcp_auth_method: McpAuthMethod;
  mcp_auth_header: string | null;
  mcp_protocol_version: string;
  discovered_tools: DiscoveredTool[] | null;
  tools_last_discovered_at: string | null;
  permission_map: Record<string, string> | null;
  data_classification: DataClassification;
  status: ServiceStatus;
  available_to_roles: string[];
  requires_approval: boolean;
  health_status: HealthStatus;
  health_last_checked_at: string | null;
  health_latency_ms: number | null;
  health_error_count_24h: number;
  created_at: string;
  updated_at: string;
}

export interface DiscoveredTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface ServiceCreateRequest {
  service_id: string;
  display_name: string;
  description?: string;
  backend_type: BackendType;
  endpoint_url: string;
  transport?: McpTransport;
  mcp_auth_method?: McpAuthMethod;
  mcp_auth_header?: string;
  mcp_auth_value?: string;
  mcp_protocol_version?: string;
  data_classification?: DataClassification;
  status?: ServiceStatus;
  available_to_roles?: string[];
  requires_approval?: boolean;
}

export interface ServiceUpdateRequest {
  display_name?: string;
  description?: string;
  endpoint_url?: string;
  status?: ServiceStatus;
  data_classification?: DataClassification;
  available_to_roles?: string[];
  requires_approval?: boolean;
}

export interface ServiceListResponse {
  services: ServiceRegistryEntry[];
  total: number;
}

// ---------------------------------------------------------------------------
// OAuth Config
// ---------------------------------------------------------------------------

export interface ServiceOAuthConfig {
  service_id: string;
  client_id: string;
  has_client_secret: boolean;
  auth_url: string | null;
  token_url: string | null;
  scopes: string[];
  created_at: string;
  updated_at: string;
}

export interface OAuthConfigSetRequest {
  client_id: string;
  client_secret: string;
  auth_url?: string;
  token_url?: string;
  scopes?: string[];
}

// ---------------------------------------------------------------------------
// Connection Test & Tool Discovery
// ---------------------------------------------------------------------------

export interface ConnectionTestResult {
  status: "success" | "error";
  message: string;
  latency_ms: number | null;
  server_info?: Record<string, unknown>;
}

export interface ToolDiscoveryResult {
  tools: DiscoveredTool[];
  permission_map: Record<string, string>;
  discovered_at: string;
}

// ---------------------------------------------------------------------------
// Agent Fleet
// ---------------------------------------------------------------------------

export interface AdminAgent {
  agent_id: string;
  name: string;
  status: "active" | "suspended" | "inactive";
  public_key: string | null;
  created_at: string;
  last_active_at: string | null;
  delegation_count: number;
  delegating_users: string[];
  active_sessions: number;
}

export interface AdminAgentListResponse {
  agents: AdminAgent[];
  total: number;
}

export interface AgentSuspendRequest {
  reason: string;
}

// ---------------------------------------------------------------------------
// Delegation Management
// ---------------------------------------------------------------------------

export interface AdminDelegation {
  id: string;
  agent_id: string;
  delegator: string;
  delegated_permissions: string[];
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  source: "manual" | "template" | "invite" | "admin";
  template_id: string | null;
}

export interface AdminDelegationListResponse {
  delegations: AdminDelegation[];
  total: number;
}

export interface AdminDelegationCreateRequest {
  agent_id: string;
  user_id: string;
  permissions: string[];
  template_id?: string;
}

// ---------------------------------------------------------------------------
// Delegation Templates
// ---------------------------------------------------------------------------

export interface DelegationTemplate {
  id: string;
  agent_id: string;
  max_permissions: string[];
  blocked_permissions: string[];
  default_ttl_days: number;
  available_to_roles: string[];
  max_actions_per_day: number | null;
  working_hours_start: string | null;
  working_hours_end: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DelegationTemplateCreateRequest {
  agent_id: string;
  max_permissions: string[];
  blocked_permissions?: string[];
  default_ttl_days?: number;
  available_to_roles?: string[];
  max_actions_per_day?: number | null;
  working_hours_start?: string | null;
  working_hours_end?: string | null;
}

export interface DelegationTemplateUpdateRequest {
  max_permissions?: string[];
  blocked_permissions?: string[];
  default_ttl_days?: number;
  available_to_roles?: string[];
  max_actions_per_day?: number | null;
  working_hours_start?: string | null;
  working_hours_end?: string | null;
}

export interface DelegationTemplateListResponse {
  templates: DelegationTemplate[];
  total: number;
}

// ---------------------------------------------------------------------------
// Health & Emergency
// ---------------------------------------------------------------------------

export interface HealthAggregation {
  total_services: number;
  services_up: number;
  services_down: number;
  services_slow: number;
  services_unknown: number;
  total_requests_24h: number;
  success_rate_24h: number;
  avg_latency_ms: number;
  backends: BackendHealthEntry[];
}

export interface BackendHealthEntry {
  service_id: string;
  display_name: string;
  backend_type: BackendType;
  health_status: HealthStatus;
  latency_ms: number | null;
  error_count_24h: number;
  last_checked_at: string | null;
}

export interface EmergencyActionRequest {
  reason: string;
}

export interface EmergencyActionResponse {
  action: string;
  agents_affected: number;
  delegations_revoked: number;
  reason: string;
  executed_by: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// User / Role Management
// ---------------------------------------------------------------------------

export type UserRole = "employee" | "admin" | "security";

export interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  role: UserRole;
  created_at: string;
}

export interface SetUserRoleRequest {
  role: UserRole;
}
