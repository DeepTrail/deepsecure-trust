export interface RefreshLogEntry {
  timestamp: string;
  status: "success" | "failure";
  latency_ms?: number | null;
  new_expires_in?: number;
  error?: string;
}

export interface VaultTokenItem {
  service_id: string;
  token_ref: string;
  status: "active" | "expired" | "expiring_soon";
  scopes_granted: string[] | null;
  created_at: string | null;
  expires_at: string | null;
  last_used_at: string | null;
  last_refreshed_at: string | null;
  refresh_count: number;
  refresh_log: RefreshLogEntry[];
}

export interface CredentialItem {
  credential_id: string;
  agent_id: string;
  scope: string | null;
  status: "valid" | "expired" | "revoked";
  issued_at: string | null;
  expires_at: string | null;
}

export interface SecretItem {
  name: string;
  service?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
}

export interface ServiceCredentialItem {
  id: string;
  name: string;
  service_type: string;
  has_oauth_config: boolean;
  client_id_masked?: string;
  scopes?: string[];
  auth_url?: string;
  updated_at?: string;
}

export interface EncryptionStatus {
  service_credentials: "gcp-kms" | "fernet" | "none";
  vault_tokens: "kms" | "fernet";
  secrets: "shamir_split_key";
}
