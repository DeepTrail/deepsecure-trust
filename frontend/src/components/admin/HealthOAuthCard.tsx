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

const GRID_4COL = "grid grid-cols-[auto_1fr_auto_1fr] gap-x-8 gap-y-1.5 text-sm";

function KV({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="whitespace-nowrap text-muted-foreground">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </>
  );
}

function SectionLabel({ label, first }: { label: string; first?: boolean }) {
  return (
    <div className={cn("col-span-4", !first && "mt-2 border-t pt-3")}>
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
    </div>
  );
}

function HealthSection({ health }: { health: HealthOAuthCardProps["health"] }) {
  return (
    <>
      <SectionLabel label="Health" first />
      <KV label="Latency">{health.latencyMs != null ? `${health.latencyMs}ms` : "—"}</KV>
      <KV label="Last checked">
        {health.lastCheckedAt ? new Date(health.lastCheckedAt).toLocaleString() : "Never"}
      </KV>
      <KV label="Errors (24h)">{health.errorCount24h ?? 0}</KV>
      {health.status ? (
        <KV label="Status"><HealthIndicator status={health.status} /></KV>
      ) : (
        <>
          <span />
          <span />
        </>
      )}
    </>
  );
}

function OAuthViewSection({ config }: { config: ServiceOAuthConfig }) {
  return (
    <>
      {config.source === "env" && (
        <div className="col-span-4 rounded bg-blue-50 px-2 py-1">
          <p className="text-xs text-blue-700">
            Managed centrally via environment configuration
          </p>
        </div>
      )}
      <KV label="Client ID">
        <span className="font-mono text-xs">{config.client_id.slice(0, 12)}…</span>
      </KV>
      {config.auth_url ? (
        <KV label="Auth URL">
          <span className="font-mono text-xs break-all">{config.auth_url}</span>
        </KV>
      ) : (
        <>
          <span />
          <span />
        </>
      )}
      <KV label="Secret">
        <Badge variant="secondary" className="text-xs">Configured</Badge>
      </KV>
      {config.token_url ? (
        <KV label="Token URL">
          <span className="font-mono text-xs break-all">{config.token_url}</span>
        </KV>
      ) : (
        <>
          <span />
          <span />
        </>
      )}
      {config.scopes && config.scopes.length > 0 && (
        <>
          <KV label="Scopes">
            <span className="text-xs">{config.scopes.join(", ")}</span>
          </KV>
          <span />
          <span />
        </>
      )}
    </>
  );
}

function OAuthEditSection({
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
    <div className="mt-2 space-y-3 border-t pt-3" data-testid="oauth-edit-form">
      <p className="text-xs font-semibold text-muted-foreground">OAuth (editing)</p>
      <div className="grid grid-cols-[auto_1fr_auto_1fr] gap-x-8 gap-y-3 text-sm">
        <label className="self-center whitespace-nowrap text-muted-foreground">Client ID</label>
        <Input
          className="h-8 text-xs"
          value={form.clientId}
          onChange={(e) => onFormChange?.("clientId", e.target.value)}
          placeholder="OAuth Client ID"
        />
        <label className="self-center whitespace-nowrap text-muted-foreground">Auth URL</label>
        <Input
          className="h-8 text-xs"
          value={form.authUrl}
          onChange={(e) => onFormChange?.("authUrl", e.target.value)}
          placeholder="https://..."
        />
        <label className="self-center whitespace-nowrap text-muted-foreground">Secret</label>
        <Input
          className="h-8 text-xs"
          type="password"
          value={form.clientSecret}
          onChange={(e) => onFormChange?.("clientSecret", e.target.value)}
          placeholder={oauthConfig ? "Leave blank to keep current" : "OAuth Client Secret"}
        />
        <label className="self-center whitespace-nowrap text-muted-foreground">Token URL</label>
        <Input
          className="h-8 text-xs"
          value={form.tokenUrl}
          onChange={(e) => onFormChange?.("tokenUrl", e.target.value)}
          placeholder="https://..."
        />
        <label className="self-center whitespace-nowrap text-muted-foreground">Scopes</label>
        <div className="col-span-3">
          <Input
            className="h-8 text-xs"
            value={form.scopes}
            onChange={(e) => onFormChange?.("scopes", e.target.value)}
            placeholder="comma-separated"
          />
        </div>
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
        className="rounded-md border bg-background p-4"
        data-testid="health-oauth-unified-card"
      >
        <dl className={GRID_4COL}>
          <HealthSection health={health} />

          {showOAuth && !oauthEditing && (
            <>
              <SectionLabel label="OAuth Credentials" />
              {oauthLoading ? (
                <div className="col-span-4">
                  <p className="text-xs text-muted-foreground">Loading...</p>
                </div>
              ) : oauthConfig ? (
                <div className="contents" data-testid="oauth-view-card">
                  <OAuthViewSection config={oauthConfig} />
                </div>
              ) : (
                <div className="col-span-4">
                  <p className="text-xs text-muted-foreground">
                    No OAuth credentials configured. Click Configure OAuth to add.
                  </p>
                </div>
              )}
            </>
          )}
        </dl>

        {showOAuth && oauthEditing && oauthForm && (
          <OAuthEditSection
            form={oauthForm}
            oauthConfig={oauthConfig}
            oauthSaving={oauthSaving}
            oauthError={oauthError}
            onSave={onOAuthSave}
            onCancel={onOAuthEditCancel}
            onFormChange={onOAuthFormChange}
          />
        )}
      </div>

      {testResult && <TestResultBanner testResult={testResult} />}
    </div>
  );
}
