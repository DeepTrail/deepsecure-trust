"use client";

import { useEffect, useState, useCallback } from "react";
import {
  FileKey2,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import type {
  AdminDelegation,
  AdminDelegationListResponse,
  DelegationTemplate,
  DelegationTemplateListResponse,
  DelegationTemplateCreateRequest,
} from "@/lib/types/admin";

type Tab = "templates" | "delegations";

type TemplatesState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; templates: DelegationTemplate[] };

type DelegationsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; delegations: AdminDelegation[] };

const SOURCE_BADGE_COLORS: Record<AdminDelegation["source"], string> = {
  manual: "bg-gray-500/10 text-gray-700 border-gray-200",
  template: "bg-blue-500/10 text-blue-700 border-blue-200",
  admin: "bg-purple-500/10 text-purple-700 border-purple-200",
  invite: "bg-green-500/10 text-green-700 border-green-200",
};

function truncateList(items: string[], max = 3): string {
  if (items.length <= max) return items.join(", ");
  return `${items.slice(0, max).join(", ")} +${items.length - max} more`;
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        active ? "bg-green-500" : "bg-red-500"
      )}
    />
  );
}

function CreateTemplateDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [agentId, setAgentId] = useState("");
  const [maxPermissions, setMaxPermissions] = useState("");
  const [blockedPermissions, setBlockedPermissions] = useState("");
  const [defaultTtlDays, setDefaultTtlDays] = useState("30");
  const [availableToRoles, setAvailableToRoles] = useState("employee");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body: DelegationTemplateCreateRequest = {
      agent_id: agentId.trim(),
      max_permissions: maxPermissions
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      blocked_permissions: blockedPermissions
        ? blockedPermissions
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      default_ttl_days: parseInt(defaultTtlDays, 10) || 30,
      available_to_roles: availableToRoles
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };

    try {
      await apiClient("admin/delegation-templates", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onOpenChange(false);
      onCreated();
      setAgentId("");
      setMaxPermissions("");
      setBlockedPermissions("");
      setDefaultTtlDays("30");
      setAvailableToRoles("employee");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Delegation Template</DialogTitle>
          <DialogDescription>
            Define a reusable template for agent delegations.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Agent ID</label>
            <Input
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="e.g. code-review-agent"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Max Permissions</label>
            <Input
              value={maxPermissions}
              onChange={(e) => setMaxPermissions(e.target.value)}
              placeholder="Comma-separated, e.g. github:read, slack:post"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Blocked Permissions</label>
            <Input
              value={blockedPermissions}
              onChange={(e) => setBlockedPermissions(e.target.value)}
              placeholder="Comma-separated (optional)"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Default TTL (days)</label>
              <Input
                type="number"
                min={1}
                value={defaultTtlDays}
                onChange={(e) => setDefaultTtlDays(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Available to Roles</label>
              <Input
                value={availableToRoles}
                onChange={(e) => setAvailableToRoles(e.target.value)}
                placeholder="e.g. employee, admin"
              />
            </div>
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating..." : "Create Template"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminDelegationsPage() {
  const [tab, setTab] = useState<Tab>("templates");
  const [templatesState, setTemplatesState] = useState<TemplatesState>({
    kind: "loading",
  });
  const [delegationsState, setDelegationsState] = useState<DelegationsState>({
    kind: "loading",
  });
  const [search, setSearch] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const fetchTemplates = useCallback(async () => {
    try {
      const data = await apiClient<DelegationTemplateListResponse>(
        "admin/delegation-templates"
      );
      setTemplatesState({ kind: "data", templates: data.templates ?? [] });
    } catch (err) {
      setTemplatesState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load templates",
      });
    }
  }, []);

  const fetchDelegations = useCallback(async () => {
    try {
      const data = await apiClient<AdminDelegationListResponse>(
        "admin/delegations"
      );
      setDelegationsState({ kind: "data", delegations: data.delegations ?? [] });
    } catch (err) {
      setDelegationsState({
        kind: "error",
        message:
          err instanceof Error ? err.message : "Failed to load delegations",
      });
    }
  }, []);

  useEffect(() => {
    fetchTemplates();
    fetchDelegations();
  }, [fetchTemplates, fetchDelegations]);

  const handleDeleteTemplate = async (id: string) => {
    try {
      await apiClient(`admin/delegation-templates/${id}`, { method: "DELETE" });
      fetchTemplates();
    } catch {
      // silently fail; in production, show toast
    }
  };

  const handleRevokeDelegation = async (id: string) => {
    try {
      await apiClient(`admin/delegations/${id}`, { method: "DELETE" });
      fetchDelegations();
    } catch {
      // silently fail; in production, show toast
    }
  };

  const renderTemplates = () => {
    if (templatesState.kind === "loading") return <PageSkeleton variant="list" />;
    if (templatesState.kind === "error") {
      return (
        <ErrorCard
          title="Delegation Templates"
          message={templatesState.message}
          retry={fetchTemplates}
        />
      );
    }

    const { templates } = templatesState;
    if (templates.length === 0) {
      return (
        <EmptyState
          title="No delegation templates"
          description="Create a template to define reusable delegation policies for agents."
          action={{ label: "Create Template", onClick: () => setShowCreateDialog(true) }}
        />
      );
    }

    return (
      <div className="space-y-2">
        {templates.map((tmpl) => (
          <Card key={tmpl.id} className="flex items-center justify-between px-6 py-4">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{tmpl.agent_id}</span>
                <Badge variant="outline" className="text-xs">
                  TTL: {tmpl.default_ttl_days}d
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span>
                  Max: {truncateList(tmpl.max_permissions)}
                </span>
                {tmpl.blocked_permissions.length > 0 && (
                  <>
                    <span className="text-muted-foreground/50">|</span>
                    <span>
                      Blocked: {tmpl.blocked_permissions.length}
                    </span>
                  </>
                )}
                <span className="text-muted-foreground/50">|</span>
                <span>Roles: {tmpl.available_to_roles.join(", ")}</span>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => handleDeleteTemplate(tmpl.id)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </Card>
        ))}
      </div>
    );
  };

  const renderDelegations = () => {
    if (delegationsState.kind === "loading") return <PageSkeleton variant="list" />;
    if (delegationsState.kind === "error") {
      return (
        <ErrorCard
          title="Delegations"
          message={delegationsState.message}
          retry={fetchDelegations}
        />
      );
    }

    const { delegations } = delegationsState;

    const filtered = delegations.filter((d) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        d.agent_id.toLowerCase().includes(q) ||
        d.delegator.toLowerCase().includes(q)
      );
    });

    if (filtered.length === 0) {
      return (
        <EmptyState
          title="No delegations found"
          description={
            search
              ? "Try a different search term"
              : "No delegations have been created yet."
          }
        />
      );
    }

    return (
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Agent</th>
              <th className="px-4 py-3 text-left font-medium">Delegator</th>
              <th className="px-4 py-3 text-left font-medium">Permissions</th>
              <th className="px-4 py-3 text-left font-medium">Source</th>
              <th className="px-4 py-3 text-left font-medium">Created</th>
              <th className="px-4 py-3 text-left font-medium">Expires</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filtered.map((d) => {
              const isActive = !d.revoked_at;
              return (
                <tr key={d.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{d.agent_id}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {d.delegator}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="secondary" className="text-xs">
                      {d.delegated_permissions.length} permissions
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={cn("text-xs capitalize", SOURCE_BADGE_COLORS[d.source])}
                    >
                      {d.source}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {d.expires_at
                      ? new Date(d.expires_at).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1.5">
                      <StatusDot active={isActive} />
                      <span className={cn("text-xs", isActive ? "text-green-700" : "text-red-700")}>
                        {isActive ? "Active" : "Revoked"}
                      </span>
                    </span>
                    {d.revoked_at && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(d.revoked_at).toLocaleDateString()}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isActive && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleRevokeDelegation(d.id)}
                      >
                        <XCircle className="mr-1 h-3.5 w-3.5" />
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <FileKey2 className="h-6 w-6" />
            Delegation Management
          </h1>
          <p className="text-muted-foreground">
            Manage delegation templates and view all active delegations
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              fetchTemplates();
              fetchDelegations();
            }}
          >
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh
          </Button>
          {tab === "templates" && (
            <Button size="sm" onClick={() => setShowCreateDialog(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              Create Template
            </Button>
          )}
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex items-center gap-3">
        <div className="flex rounded-md border">
          {(["templates", "delegations"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-4 py-1.5 text-sm font-medium transition-colors",
                tab === t
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t === "templates" ? "Templates" : "All Delegations"}
            </button>
          ))}
        </div>

        {tab === "delegations" && (
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by agent or delegator..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        )}
      </div>

      {/* Tab Content */}
      {tab === "templates" ? renderTemplates() : renderDelegations()}

      <CreateTemplateDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onCreated={fetchTemplates}
      />
    </div>
  );
}
