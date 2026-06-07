"use client";

import { Loader2, Pencil, Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

const ROW_GRID = "grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-6 gap-y-2 text-sm";

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

function SectionDivider({ label, first }: { label: string; first?: boolean }) {
  return (
    <div
      className={cn(
        "col-span-2",
        !first && "mt-1 border-t pt-3"
      )}
    >
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
    </div>
  );
}

function HealthRows({ health }: { health: HealthOAuthCardProps["health"] }) {
  return (
    <>
      <SectionDivider label="Health" first />
      <dt className="text-muted-foreground">Latency</dt>
      <dd className="font-medium">
        {health.latencyMs != null ? `${health.latencyMs}ms` : "—"}
      </dd>
      <dt className="text-muted-foreground">Errors (24h)</dt>
      <dd className="font-medium">{health.errorCount24h ?? 0}</dd>
      <dt className="text-muted-foreground">Last checked</dt>
      <dd className="font-medium">
        {health.lastCheckedAt ? new Date(health.lastCheckedAt).toLocaleString() : "Never"}
      </dd>
      {health.status && (
        <>
          <dt className="text-muted-foreground">Status</dt>
          <dd>
            <HealthIndicator status={health.status} />
          </dd>
        </>
      )}
    </>
  );
}

function OAuthViewRows({ config }: { config: ServiceOAuthConfig }) {
  return (
    <>
      {config.source === "env" && (
        <div className="col-span-2 rounded bg-blue-50 px-2 py-1">
          <p className="text-xs text-blue-700">
            Managed centrally via environment configuration
          </p>
        </div>
      )}
      <dt className="text-muted-foreground">Client ID</dt>
      <dd className="font-mono text-xs">{config.client_id.slice(0, 12)}…</dd>
      <dt className="text-muted-foreground">Secret</dt>
      <dd>
        <Badge variant="secondary" className="text-xs">
          Configured
        </Badge>
      </dd>
      {config.auth_url && (
        <>
          <dt className="text-muted-foreground">Auth URL</dt>
          <dd className="font-mono text-xs break-all">{config.auth_url}</dd>
        </>
      )}
      {config.token_url && (
        <>
          <dt className="text-muted-foreground">Token URL</dt>
          <dd className="font-mono text-xs break-all">{config.token_url}</dd>
        </>
      )}
      {config.scopes && config.scopes.length > 0 && (
        <>
          <dt className="text-muted-foreground">Scopes</dt>
          <dd className="text-xs">{config.scopes.join(", ")}</dd>
        </>
      )}
    </>
  );
}

function OAuthEditRows({
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
    <>
      <SectionDivider label="OAuth (editing)" />
      <dt className="text-muted-foreground">Client ID</dt>
      <dd>
        <Input
          className="h-8 text-xs"
          value={form.clientId}
          onChange={(e) => onFormChange?.("clientId", e.target.value)}
          placeholder="OAuth Client ID"
        />
      </dd>
      <dt className="text-muted-foreground">Secret</dt>
      <dd>
        <Input
          className="h-8 text-xs"
          type="password"
          value={form.clientSecret}
          onChange={(e) => onFormChange?.("clientSecret", e.target.value)}
          placeholder={oauthConfig ? "Leave blank to keep current" : "OAuth Client Secret"}
        />
      </dd>
      <dt className="text-muted-foreground">Auth URL</dt>
      <dd>
        <Input
          className="h-8 text-xs"
          value={form.authUrl}
          onChange={(e) => onFormChange?.("authUrl", e.target.value)}
          placeholder="https://..."
        />
      </dd>
      <dt className="text-muted-foreground">Token URL</dt>
      <dd>
        <Input
          className="h-8 text-xs"
          value={form.tokenUrl}
          onChange={(e) => onFormChange?.("tokenUrl", e.target.value)}
          placeholder="https://..."
        />
      </dd>
      <dt className="text-muted-foreground">Scopes</dt>
      <dd>
        <Input
          className="h-8 text-xs"
          value={form.scopes}
          onChange={(e) => onFormChange?.("scopes", e.target.value)}
          placeholder="comma-separated"
        />
      </dd>
      {oauthError && (
        <div className="col-span-2">
          <p className="text-xs text-red-600">{oauthError}</p>
        </div>
      )}
      <div className="col-span-2 flex gap-2 pt-1">
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
    </>
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
  const title = showOAuth ? "Health & OAuth" : "Health";
  const showOAuthEditButton = showOAuth && !oauthEditing && !oauthLoading;

  return (
    <div className="space-y-2" data-testid="health-oauth-card">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">{title}</h4>
        {showOAuthEditButton && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={onOAuthEditStart}
          >
            <Pencil className="mr-1 h-3 w-3" />
            {oauthConfig ? "Edit OAuth" : "Configure OAuth"}
          </Button>
        )}
      </div>

      <div
        className="rounded-md border bg-background p-3"
        data-testid="health-oauth-unified-card"
      >
        <dl className={ROW_GRID}>
          <HealthRows health={health} />

          {showOAuth && (
            <>
              {oauthLoading ? (
                <div className="col-span-2 mt-1 border-t pt-3">
                  <p className="text-xs text-muted-foreground">Loading...</p>
                </div>
              ) : oauthEditing && oauthForm ? (
                <div className="col-span-2 contents" data-testid="oauth-edit-form">
                  <OAuthEditRows
                    form={oauthForm}
                    oauthConfig={oauthConfig}
                    oauthSaving={oauthSaving}
                    oauthError={oauthError}
                    onSave={onOAuthSave}
                    onCancel={onOAuthEditCancel}
                    onFormChange={onOAuthFormChange}
                  />
                </div>
              ) : (
                <>
                  <SectionDivider label="OAuth Credentials" />
                  {oauthConfig ? (
                    <div className="col-span-2 contents" data-testid="oauth-view-card">
                      <OAuthViewRows config={oauthConfig} />
                    </div>
                  ) : (
                    <div className="col-span-2">
                      <p className="text-xs text-muted-foreground">
                        No OAuth credentials configured. Click Configure OAuth to add.
                      </p>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </dl>
      </div>

      {testResult && <TestResultBanner testResult={testResult} />}
    </div>
  );
}
