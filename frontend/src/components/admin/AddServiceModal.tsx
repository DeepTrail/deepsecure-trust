"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AvailableToPicker } from "@/components/admin/AvailableToPicker";
import type {
  BackendType,
  McpAuthMethod,
  McpTransport,
  DataClassification,
} from "@/lib/types/admin";

interface AddServiceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function AddServiceModal({ open, onOpenChange, onCreated }: AddServiceModalProps) {
  const [backendType, setBackendType] = useState<BackendType>("rest");
  const [serviceId, setServiceId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [transport, setTransport] = useState<McpTransport>("streamable-http");
  const [authMethod, setAuthMethod] = useState<McpAuthMethod>("none");
  const [authHeader, setAuthHeader] = useState("Authorization");
  const [authValue, setAuthValue] = useState("");
  const [dataClassification, setDataClassification] = useState<DataClassification>("internal");
  const [availableToEveryone, setAvailableToEveryone] = useState(true);
  const [availableToGroups, setAvailableToGroups] = useState<string[]>([]);
  const [availableToUsers, setAvailableToUsers] = useState<string[]>([]);
  const [oauthOpen, setOauthOpen] = useState(false);
  const [oauthClientId, setOauthClientId] = useState("");
  const [oauthClientSecret, setOauthClientSecret] = useState("");
  const [oauthAuthUrl, setOauthAuthUrl] = useState("");
  const [oauthTokenUrl, setOauthTokenUrl] = useState("");
  const [oauthScopes, setOauthScopes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMcp = backendType === "mcp";

  function detectAndPrefillOAuth(url: string) {
    if (isMcp || !url) return;
    const lc = url.toLowerCase();
    if (lc.includes("notion.com") || lc.includes("notion.so")) {
      if (!oauthAuthUrl) setOauthAuthUrl("https://api.notion.com/v1/oauth/authorize");
      if (!oauthTokenUrl) setOauthTokenUrl("https://api.notion.com/v1/oauth/token");
    } else if (lc.includes("slack.com")) {
      if (!oauthAuthUrl) setOauthAuthUrl("https://slack.com/oauth/v2/authorize");
      if (!oauthTokenUrl) setOauthTokenUrl("https://slack.com/api/oauth.v2.access");
      if (!oauthScopes) setOauthScopes("channels:read,chat:write,users:read");
    } else if (lc.includes("github.com") || lc.includes("api.github.com")) {
      if (!oauthAuthUrl) setOauthAuthUrl("https://github.com/login/oauth/authorize");
      if (!oauthTokenUrl) setOauthTokenUrl("https://github.com/login/oauth/access_token");
      if (!oauthScopes) setOauthScopes("repo,read:org,read:user");
    }
  }

  function resetForm() {
    setServiceId("");
    setDisplayName("");
    setDescription("");
    setEndpointUrl("");
    setTransport("streamable-http");
    setAuthMethod("none");
    setAuthHeader("Authorization");
    setAuthValue("");
    setDataClassification("internal");
    setAvailableToEveryone(true);
    setAvailableToGroups([]);
    setAvailableToUsers([]);
    setOauthOpen(false);
    setOauthClientId("");
    setOauthClientSecret("");
    setOauthAuthUrl("");
    setOauthTokenUrl("");
    setOauthScopes("");
    setError(null);
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        service_id: serviceId,
        display_name: displayName,
        description: description || undefined,
        backend_type: backendType,
        endpoint_url: endpointUrl,
        data_classification: dataClassification,
        available_to_roles: availableToEveryone ? ["all"] : [],
        available_to_groups: availableToEveryone ? [] : (availableToGroups.length ? availableToGroups : undefined),
        available_to_users: availableToEveryone ? [] : (availableToUsers.length ? availableToUsers : undefined),
      };
      if (isMcp) {
        body.transport = transport;
        body.mcp_auth_method = authMethod;
        if (authMethod !== "none") {
          body.mcp_auth_header = authHeader;
          body.mcp_auth_value = authValue;
        }
      }
      await apiClient("admin/services", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!isMcp && oauthClientId && oauthClientSecret) {
        const oauthBody: Record<string, unknown> = {
          client_id: oauthClientId,
          client_secret: oauthClientSecret,
        };
        if (oauthAuthUrl) oauthBody.auth_url = oauthAuthUrl;
        if (oauthTokenUrl) oauthBody.token_url = oauthTokenUrl;
        if (oauthScopes) oauthBody.scopes = oauthScopes.split(",").map((s) => s.trim()).filter(Boolean);
        await apiClient(
          `admin/services/${encodeURIComponent(serviceId)}/oauth`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(oauthBody),
          }
        );
      }

      resetForm();
      onOpenChange(false);
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.body as Record<string, string> | undefined;
        setError(body?.detail ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create service");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = serviceId && displayName && endpointUrl && !submitting;

  return (
    <Dialog
      open={open}
      onOpenChange={(v: boolean) => {
        if (!v) resetForm();
        onOpenChange(v);
      }}
    >
      <DialogContent className="max-w-lg flex flex-col max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Add Service</DialogTitle>
          <DialogDescription>
            Register a new backend service or MCP server in the catalog.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2 overflow-y-auto pr-1">
          {/* Backend Type Selector */}
          <div className="grid gap-2">
            <Label>Backend Type</Label>
            <div className="flex rounded-md border">
              {(["rest", "mcp"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setBackendType(t)}
                  className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
                    backendType === t
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t === "rest" ? "REST + OAuth" : "MCP Server"}
                </button>
              ))}
            </div>
          </div>

          {/* Common Fields */}
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="service-id">Service ID</Label>
              <Input
                id="service-id"
                placeholder="e.g. jira-mcp"
                value={serviceId}
                onChange={(e) => setServiceId(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="display-name">Display Name</Label>
              <Input
                id="display-name"
                placeholder="e.g. Jira"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="endpoint">Endpoint URL</Label>
            <Input
              id="endpoint"
              placeholder={isMcp ? "https://jira.example.com/mcp" : "https://api.jira.com/v3"}
              value={endpointUrl}
              onChange={(e) => {
                setEndpointUrl(e.target.value);
                detectAndPrefillOAuth(e.target.value);
              }}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              placeholder="Brief description of this service"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label>Data Classification</Label>
            <Select
              value={dataClassification}
              onValueChange={(v) => setDataClassification(v as DataClassification)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="internal">Internal</SelectItem>
                <SelectItem value="confidential">Confidential</SelectItem>
                <SelectItem value="restricted">Restricted</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Available To */}
          <div className="grid gap-1.5">
            <Label>Available To</Label>
            <AvailableToPicker
              everyone={availableToEveryone}
              onEveryoneChange={setAvailableToEveryone}
              selectedGroups={availableToGroups}
              selectedUsers={availableToUsers}
              onGroupsChange={setAvailableToGroups}
              onUsersChange={setAvailableToUsers}
            />
            <p className="text-xs text-muted-foreground">
              Select which groups or users can see and connect to this service
            </p>
          </div>

          {/* REST OAuth Credentials — collapsible */}
          {!isMcp && (
            <div className="rounded-md border">
              <button
                type="button"
                onClick={() => setOauthOpen(!oauthOpen)}
                className="flex w-full items-center gap-2 p-3 text-left hover:bg-muted/30 transition-colors"
              >
                {oauthOpen ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="text-sm font-semibold">OAuth Credentials</span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {oauthClientId ? "Configured" : "Optional — configure now or later"}
                </span>
              </button>
              {oauthOpen && (
                <div className="grid gap-3 border-t px-3 pb-3 pt-2">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-1.5">
                      <Label htmlFor="oauth-client-id">Client ID</Label>
                      <Input
                        id="oauth-client-id"
                        placeholder="OAuth Client ID"
                        value={oauthClientId}
                        onChange={(e) => setOauthClientId(e.target.value)}
                      />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="oauth-client-secret">Client Secret</Label>
                      <Input
                        id="oauth-client-secret"
                        type="password"
                        placeholder="OAuth Client Secret"
                        value={oauthClientSecret}
                        onChange={(e) => setOauthClientSecret(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-1.5">
                      <Label htmlFor="oauth-auth-url">Authorization URL</Label>
                      <Input
                        id="oauth-auth-url"
                        placeholder="https://provider.com/oauth/authorize"
                        value={oauthAuthUrl}
                        onChange={(e) => setOauthAuthUrl(e.target.value)}
                      />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="oauth-token-url">Token URL</Label>
                      <Input
                        id="oauth-token-url"
                        placeholder="https://provider.com/oauth/token"
                        value={oauthTokenUrl}
                        onChange={(e) => setOauthTokenUrl(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="oauth-scopes">Scopes (comma-separated)</Label>
                    <Input
                      id="oauth-scopes"
                      placeholder="e.g. repo, read:org, read:user"
                      value={oauthScopes}
                      onChange={(e) => setOauthScopes(e.target.value)}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* MCP-specific fields */}
          {isMcp && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <Label>Transport</Label>
                  <Select
                    value={transport}
                    onValueChange={(v) => setTransport(v as McpTransport)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="streamable-http">Streamable HTTP</SelectItem>
                      <SelectItem value="sse">SSE</SelectItem>
                      <SelectItem value="rest">REST</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label>Auth Method</Label>
                  <Select
                    value={authMethod}
                    onValueChange={(v) => setAuthMethod(v as McpAuthMethod)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="api-key">API Key</SelectItem>
                      <SelectItem value="bearer-token">Bearer Token</SelectItem>
                      <SelectItem value="oauth">OAuth</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {authMethod === "none" && endpointUrl && (
                <p className="text-xs text-amber-600 -mt-1">
                  Most MCP servers require authentication. Consider selecting an auth method above.
                </p>
              )}

              {authMethod !== "none" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="auth-header">Auth Header</Label>
                    <Input
                      id="auth-header"
                      value={authHeader}
                      onChange={(e) => setAuthHeader(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="auth-value">Auth Value</Label>
                    <Input
                      id="auth-value"
                      type="password"
                      placeholder="API key or token"
                      value={authValue}
                      onChange={(e) => setAuthValue(e.target.value)}
                    />
                  </div>
                </div>
              )}
            </>
          )}

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            Add Service
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
