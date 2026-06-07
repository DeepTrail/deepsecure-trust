"use client";

import { Loader2, Pencil, Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { ConnectionTestResult, HealthStatus, ServiceOAuthConfig } from "@/lib/types/admin";

export interface OAuthFormState {
  clientId: string;
  clientSecret: string;
  authUrl: string;
  tokenUrl: string;
  scopes: string;
}

export interface HealthOAuthCardProps {
  mode: "view" | "edit";
  health: {
    latencyMs: number | null | undefined;
    errorCount24h: number | null | undefined;
    lastCheckedAt: string | null | undefined;
    status?: HealthStatus;
  };
  showOAuth?: boolean;
  oauthConfig?: ServiceOAuthConfig | null;
  oauthLoading?: boolean;
  oauthEditing?: boolean;
  oauthForm?: OAuthFormState;
  oauthSaving?: boolean;
  oauthError?: string | null;
  onOAuthEditStart?: () => void;
  onOAuthEditCancel?: () => void;
  onOAuthSave?: () => void;
  onOAuthFormChange?: (field: keyof OAuthFormState, value: string) => void;
  testResult?: ConnectionTestResult | null;
}

function HealthIndicator({ status }: { status: HealthStatus }) {
  const colors: Record<HealthStatus, string> = {
    up: "text-green-600",
    healthy: "text-green-600",
    down: "text-red-600",
    slow: "text-yellow-600",
    stale: "text-orange-600",
    unknown: "text-gray-400",
  };

  const labels: Record<HealthStatus, string> = {
    up: "Healthy",
    healthy: "Healthy",
    down: "Down",
    slow: "Slow",
    stale: "Stale",
    unknown: "Unknown",
  };

  return (
    <span className={cn("flex items-center gap-1.5 text-sm font-medium", colors[status])}>
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          (status === "up" || status === "healthy") && "bg-green-500",
          status === "down" && "bg-red-500",
          status === "slow" && "bg-yellow-500",
          status === "stale" && "bg-orange-500",
          status === "unknown" && "bg-gray-400"
        )}
      />
      {labels[status]}
    </span>
  );
}

function TestResultBanner({ testResult }: { testResult: ConnectionTestResult }) {
  return (
    <div
      className={cn(
        "rounded-md border p-3 text-sm",
        testResult.status === "success"
          ? "border-green-200 bg-green-50 text-green-800"
          : "border-red-200 bg-red-50 text-red-800"
      )}
    >
      <p className="font-medium">
        {testResult.status === "success" ? "Connection successful" : "Connection failed"}
      </p>
      <p className="text-xs">{testResult.message}</p>
      {testResult.latency_ms != null && (
        <p className="text-xs">Latency: {testResult.latency_ms}ms</p>
      )}
    </div>
  );
}

function OAuthViewCard({
  config,
  compact,
}: {
  config: ServiceOAuthConfig;
  compact: boolean;
}) {
  const envBanner = config.source === "env" && (
    <div className="mb-3 rounded bg-blue-50 px-2 py-1">
      <p className="text-xs text-blue-700">Managed centrally via environment configuration</p>
    </div>
  );

  if (compact) {
    return (
      <div className="rounded-md border bg-background p-3" data-testid="oauth-view-card">
        {envBanner}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Client ID</dt>
            <dd className="mt-0.5 font-mono text-xs">{config.client_id.slice(0, 12)}…</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Secret</dt>
            <dd className="mt-0.5">
              <Badge variant="secondary" className="text-xs">
                Configured
              </Badge>
            </dd>
          </div>
          {config.auth_url && (
            <div className="col-span-2">
              <dt className="text-xs text-muted-foreground">Auth URL</dt>
              <dd className="mt-0.5 font-mono text-xs break-all">{config.auth_url}</dd>
            </div>
          )}
          {config.token_url && (
            <div className="col-span-2">
              <dt className="text-xs text-muted-foreground">Token URL</dt>
              <dd className="mt-0.5 font-mono text-xs break-all">{config.token_url}</dd>
            </div>
          )}
          {config.scopes && config.scopes.length > 0 && (
            <div className="col-span-2">
              <dt className="text-xs text-muted-foreground">Scopes</dt>
              <dd className="mt-0.5 text-xs">{config.scopes.join(", ")}</dd>
            </div>
          )}
        </dl>
      </div>
    );
  }

  return (
    <dl className="space-y-1 text-sm" data-testid="oauth-view-card">
      {envBanner}
      <div className="flex justify-between">
        <dt className="text-muted-foreground">Client ID</dt>
        <dd className="font-mono text-xs">{config.client_id.slice(0, 8)}...</dd>
      </div>
      <div className="flex justify-between">
        <dt className="text-muted-foreground">Secret</dt>
        <dd>
          <Badge variant="secondary" className="text-xs">
            Configured
          </Badge>
        </dd>
      </div>
      {config.auth_url && (
        <div className="flex justify-between gap-4">
          <dt className="shrink-0 text-muted-foreground">Auth URL</dt>
          <dd className="font-mono text-xs break-all text-right">{config.auth_url}</dd>
        </div>
      )}
      {config.token_url && (
        <div className="flex justify-between gap-4">
          <dt className="shrink-0 text-muted-foreground">Token URL</dt>
          <dd className="font-mono text-xs break-all text-right">{config.token_url}</dd>
        </div>
      )}
      {config.scopes && config.scopes.length > 0 && (
        <div className="flex justify-between gap-4">
          <dt className="shrink-0 text-muted-foreground">Scopes</dt>
          <dd className="text-xs text-right">{config.scopes.join(", ")}</dd>
        </div>
      )}
    </dl>
  );
}

function OAuthEditForm({
  form,
  oauthConfig,
  oauthSaving,
  oauthError,
  onSave,
  onCancel,
  onFormChange,
}: {
  form: OAuthFormState;
  oauthConfig: ServiceOAuthConfig | null | undefined;
  oauthSaving?: boolean;
  oauthError?: string | null;
  onSave?: () => void;
  onCancel?: () => void;
  onFormChange?: (field: keyof OAuthFormState, value: string) => void;
}) {
  return (
    <div className="grid gap-2 rounded-md border p-3" data-testid="oauth-edit-form">
      <div className="grid grid-cols-2 gap-2">
        <div className="grid gap-1">
          <Label className="text-xs">Client ID</Label>
          <Input
            className="h-8 text-xs"
            value={form.clientId}
            onChange={(e) => onFormChange?.("clientId", e.target.value)}
            placeholder="OAuth Client ID"
          />
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">Client Secret</Label>
          <Input
            className="h-8 text-xs"
            type="password"
            value={form.clientSecret}
            onChange={(e) => onFormChange?.("clientSecret", e.target.value)}
            placeholder={oauthConfig ? "Leave blank to keep current" : "OAuth Client Secret"}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="grid gap-1">
          <Label className="text-xs">Auth URL</Label>
          <Input
            className="h-8 text-xs"
            value={form.authUrl}
            onChange={(e) => onFormChange?.("authUrl", e.target.value)}
            placeholder="https://..."
          />
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">Token URL</Label>
          <Input
            className="h-8 text-xs"
            value={form.tokenUrl}
            onChange={(e) => onFormChange?.("tokenUrl", e.target.value)}
            placeholder="https://..."
          />
        </div>
      </div>
      <div className="grid gap-1">
        <Label className="text-xs">Scopes</Label>
        <Input
          className="h-8 text-xs"
          value={form.scopes}
          onChange={(e) => onFormChange?.("scopes", e.target.value)}
          placeholder="comma-separated"
        />
      </div>
      {oauthError && <p className="text-xs text-red-600">{oauthError}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          className="h-7 text-xs"
          onClick={onSave}
          disabled={!form.clientId || oauthSaving}
        >
          {oauthSaving ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Save className="mr-1 h-3 w-3" />
          )}
          Save Credentials
        </Button>
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export function HealthOAuthCard({
  mode,
  health,
  showOAuth = true,
  oauthConfig,
  oauthLoading,
  oauthEditing,
  oauthForm,
  oauthSaving,
  oauthError,
  onOAuthEditStart,
  onOAuthEditCancel,
  onOAuthSave,
  onOAuthFormChange,
  testResult,
}: HealthOAuthCardProps) {
  const compact = mode === "view";

  return (
    <div className="space-y-4" data-testid="health-oauth-card">
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">
          {mode === "edit" ? "Health & Monitoring" : "Health"}
        </h4>
        {compact && health.status ? (
          <div className="rounded-md border bg-background p-3">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Status</dt>
                <dd className="mt-0.5">
                  <HealthIndicator status={health.status} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Latency</dt>
                <dd className="mt-0.5 font-medium">
                  {health.latencyMs != null ? `${health.latencyMs}ms` : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Errors (24h)</dt>
                <dd className="mt-0.5 font-medium">{health.errorCount24h ?? 0}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-muted-foreground">Last checked</dt>
                <dd className="mt-0.5 font-medium">
                  {health.lastCheckedAt
                    ? new Date(health.lastCheckedAt).toLocaleString()
                    : "Never"}
                </dd>
              </div>
            </dl>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <span>
              <span className="text-muted-foreground">Latency </span>
              <span className="font-medium">
                {health.latencyMs != null ? `${health.latencyMs}ms` : "—"}
              </span>
            </span>
            <span>
              <span className="text-muted-foreground">Errors (24h) </span>
              <span className="font-medium">{health.errorCount24h ?? 0}</span>
            </span>
            <span>
              <span className="text-muted-foreground">Last checked </span>
              <span className="font-medium">
                {health.lastCheckedAt
                  ? new Date(health.lastCheckedAt).toLocaleString()
                  : "Never"}
              </span>
            </span>
          </div>
        )}
      </div>

      {testResult && <TestResultBanner testResult={testResult} />}

      {showOAuth && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold">OAuth Credentials</h4>
            {!oauthEditing && !oauthLoading && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={onOAuthEditStart}
              >
                <Pencil className="mr-1 h-3 w-3" />
                {oauthConfig ? "Edit" : "Configure"}
              </Button>
            )}
          </div>

          {oauthLoading ? (
            <p className="text-xs text-muted-foreground">Loading...</p>
          ) : oauthEditing && oauthForm ? (
            <OAuthEditForm
              form={oauthForm}
              oauthConfig={oauthConfig}
              oauthSaving={oauthSaving}
              oauthError={oauthError}
              onSave={onOAuthSave}
              onCancel={onOAuthEditCancel}
              onFormChange={onOAuthFormChange}
            />
          ) : oauthConfig ? (
            <OAuthViewCard config={oauthConfig} compact={compact} />
          ) : (
            <p className="text-xs text-muted-foreground">
              No OAuth credentials configured. Click Configure to add.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
