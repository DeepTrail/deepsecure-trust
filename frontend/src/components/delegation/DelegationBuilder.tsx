"use client";

import { useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2, Send } from "lucide-react";
import {
  PermissionChecklist,
  type Permission,
} from "./PermissionChecklist";
import { TTLSelector } from "./TTLSelector";

interface Agent {
  agent_id: string;
  name: string;
}

interface PublicTemplate {
  id: string;
  agent_id: string;
  max_permissions: string[];
  blocked_permissions: string[];
  default_ttl_days: number;
}

interface DelegationBuilderProps {
  agents: Agent[];
  permissions: Permission[];
  templates?: PublicTemplate[];
  onCreated?: () => void;
  requireTemplate?: boolean;
  editMode?: boolean;
  delegationId?: string;
  initialAgentId?: string;
  initialPermissions?: string[];
}

interface DelegationResult {
  delegation_id: string;
}

const DEFAULT_TTL_DAYS = 1;

export function DelegationBuilder({
  agents,
  permissions,
  templates = [],
  onCreated,
  requireTemplate = false,
  editMode = false,
  delegationId,
  initialAgentId = "",
  initialPermissions = [],
}: DelegationBuilderProps) {
  const [selectedAgent, setSelectedAgent] = useState<string>(initialAgentId);
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>(
    initialPermissions
      .map((perm) => {
        const match = permissions.find(
          (p) => `${p.service}:${p.scope}:${p.action}` === perm,
        );
        return match?.id ?? perm;
      })
      .filter(Boolean),
  );
  const [ttlDays, setTtlDays] = useState<number>(DEFAULT_TTL_DAYS);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DelegationResult | null>(null);
  const [activeTemplate, setActiveTemplate] = useState<PublicTemplate | null>(null);

  function applyTemplate(template: PublicTemplate) {
    setActiveTemplate(template);
    setSelectedAgent(template.agent_id);
    const allowed = new Set(template.max_permissions);
    const blocked = new Set(template.blocked_permissions);
    const preSelected = permissions
      .filter((p) => allowed.has(p.id) && !blocked.has(p.id))
      .map((p) => p.id);
    setSelectedPermissions(preSelected);
    setTtlDays(template.default_ttl_days);
  }

  const handleTogglePermission = (permissionId: string) => {
    if (activeTemplate) {
      const blocked = new Set(activeTemplate.blocked_permissions);
      if (blocked.has(permissionId)) return;
      const allowed = new Set(activeTemplate.max_permissions);
      if (!selectedPermissions.includes(permissionId) && !allowed.has(permissionId)) return;
    }
    setSelectedPermissions((prev) =>
      prev.includes(permissionId)
        ? prev.filter((id) => id !== permissionId)
        : [...prev, permissionId],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgent || selectedPermissions.length === 0) return;

    setSubmitting(true);
    setError(null);

    try {
      const permissionStrings = selectedPermissions.map((id) => {
        const perm = permissions.find((p) => p.id === id);
        return perm ? `${perm.service}:${perm.scope}:${perm.action}` : id;
      });

      if (editMode && delegationId) {
        await apiClient(`delegations/${delegationId}`, {
          method: "PATCH",
          body: JSON.stringify({ permissions: permissionStrings }),
        });
        setResult({ delegation_id: delegationId });
        onCreated?.();
      } else {
        const data = await apiClient<DelegationResult>("auth/delegate", {
          method: "POST",
          body: JSON.stringify({
            agent_id: selectedAgent,
            permissions: permissionStrings,
            constraints: { expires_in_hours: ttlDays * 24 },
          }),
        });
        setResult(data);
        onCreated?.();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          editMode
            ? `Failed to update delegation (${err.status})`
            : `Failed to create delegation (${err.status})`,
        );
      } else {
        setError(
          editMode
            ? "Failed to update delegation. Please try again."
            : "Failed to create delegation. Please try again.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setSelectedAgent("");
    setSelectedPermissions([]);
    setTtlDays(DEFAULT_TTL_DAYS);
    setError(null);
    setActiveTemplate(null);
  };

  if (result) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-8">
          <CheckCircle2 className="h-12 w-12 text-green-500" />
          <h3 className="text-lg font-semibold">
            {editMode ? "Delegation Updated" : "Delegation Created"}
          </h3>
          <p className="text-sm text-muted-foreground">
            Delegation ID:{" "}
            <span className="font-mono" data-testid="delegation-id">
              {result.delegation_id}
            </span>
          </p>
          {!editMode && (
            <Button variant="outline" onClick={handleReset}>
              Create Another
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const effectivePermissions = activeTemplate
    ? (() => {
        const blocked = new Set(activeTemplate.blocked_permissions);
        return permissions.map((p) => ({
          ...p,
          locked: blocked.has(p.id) ? ("role" as const) : p.locked,
          lockReason: blocked.has(p.id) ? "Blocked by admin template" : p.lockReason,
        }));
      })()
    : permissions;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {!editMode && templates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Templates
              <Badge variant="secondary" className="ml-2 text-xs">
                {templates.length} available
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Start from an admin-approved template to pre-fill agent, permissions, and TTL.
            </p>
            <div className="grid gap-2">
              {templates.map((tmpl) => {
                const isActive = activeTemplate?.id === tmpl.id;
                return (
                  <button
                    key={tmpl.id}
                    type="button"
                    onClick={() => {
                      if (isActive) {
                        setActiveTemplate(null);
                        setSelectedAgent("");
                        setSelectedPermissions([]);
                        setTtlDays(DEFAULT_TTL_DAYS);
                      } else {
                        applyTemplate(tmpl);
                      }
                    }}
                    className={`flex items-center justify-between rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
                      isActive
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "hover:bg-muted/50"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <span className="font-medium">{tmpl.agent_id}</span>
                      <span className="ml-2 text-muted-foreground">
                        {tmpl.max_permissions.length} permissions
                        {tmpl.blocked_permissions.length > 0 &&
                          ` · ${tmpl.blocked_permissions.length} blocked`}
                        {` · TTL: ${tmpl.default_ttl_days}d`}
                      </span>
                    </div>
                    {isActive && (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                    )}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {!editMode && requireTemplate && !activeTemplate ? (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-sm text-muted-foreground">
              Select a template above to create a delegation. Contact your admin to enable free-form delegation.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Select Agent</CardTitle>
            </CardHeader>
            <CardContent>
              <select
                value={selectedAgent}
                onChange={(e) => {
                  setSelectedAgent(e.target.value);
                  if (activeTemplate && e.target.value !== activeTemplate.agent_id) {
                    setActiveTemplate(null);
                  }
                }}
                className="w-full rounded-md border px-3 py-2 text-sm"
                aria-label="Select agent"
                required
                disabled={editMode}
              >
                <option value="">Choose an agent...</option>
                {agents.map((agent) => (
                  <option key={agent.agent_id} value={agent.agent_id}>
                    {agent.name || agent.agent_id}
                  </option>
                ))}
              </select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Permissions
                {selectedPermissions.length > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {selectedPermissions.length} selected
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <PermissionChecklist
                permissions={effectivePermissions}
                selected={selectedPermissions}
                onToggle={handleTogglePermission}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Time-to-Live (TTL)</CardTitle>
            </CardHeader>
            <CardContent>
              <TTLSelector
                value={ttlDays}
                onChange={setTtlDays}
                unit="days"
                maxDays={activeTemplate?.default_ttl_days}
              />
            </CardContent>
          </Card>

          {error && (
            <div className="flex items-center gap-3">
              <p className="text-sm text-destructive flex-1">{error}</p>
              <Button type="button" variant="outline" size="sm" onClick={() => { setError(null); handleSubmit(new Event("submit") as unknown as React.FormEvent); }}>
                Retry
              </Button>
            </div>
          )}

          <Separator />

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {selectedAgent
                ? `Delegating ${selectedPermissions.length} permission(s) to ${selectedAgent}`
                : "Select an agent and permissions to create a delegation"}
            </p>
            <Button
              type="submit"
              disabled={
                submitting || !selectedAgent || selectedPermissions.length === 0
              }
            >
              <Send className="mr-2 h-4 w-4" />
              {submitting
                ? editMode
                  ? "Updating..."
                  : "Creating..."
                : editMode
                  ? "Update Delegation"
                  : "Create Delegation"}
            </Button>
          </div>
        </>
      )}
    </form>
  );
}
