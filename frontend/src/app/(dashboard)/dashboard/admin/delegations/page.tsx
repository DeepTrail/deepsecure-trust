"use client";

import { useEffect, useState, useCallback } from "react";
import {
  FileKey2,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  XCircle,
  Pencil,
  Mail,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
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
import { AgentSelector } from "@/components/delegation/AgentSelector";
import { PermissionPicker } from "@/components/delegation/PermissionPicker";
import { TTLSelector } from "@/components/delegation/TTLSelector";
import { AvailableToPicker } from "@/components/admin/AvailableToPicker";
import { EditDelegationSheet } from "@/components/admin/EditDelegationSheet";
import type {
  AdminDelegation,
  AdminDelegationListResponse,
  DelegationTemplate,
  DelegationTemplateListResponse,
  DelegationTemplateCreateRequest,
  DelegationTemplateUpdateRequest,
  ProvisionMode,
} from "@/lib/types/admin";

interface Agent {
  agent_id: string;
  name: string;
}

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

function groupPermissionsByService(perms: string[]): Record<string, string[]> {
  const grouped: Record<string, string[]> = {};
  for (const p of perms) {
    const colonIdx = p.indexOf(":");
    const svc = colonIdx > 0 ? p.slice(0, colonIdx) : "other";
    const rest = colonIdx > 0 ? p.slice(colonIdx + 1) : p;
    if (!grouped[svc]) grouped[svc] = [];
    grouped[svc].push(rest);
  }
  return grouped;
}

function formatExpiryInfo(createdAt: string, expiresAt: string | null): { ttlLabel: string; isExpired: boolean } {
  if (!expiresAt) return { ttlLabel: "—", isExpired: false };
  const created = new Date(createdAt).getTime();
  const expires = new Date(expiresAt).getTime();
  const now = Date.now();
  const ttlMs = expires - created;
  const ttlDays = Math.round(ttlMs / 86400000);
  const ttlLabel = ttlDays >= 1 ? `${ttlDays}d` : `${Math.round(ttlMs / 3600000)}h`;
  return { ttlLabel, isExpired: now > expires };
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
  const [maxPermissions, setMaxPermissions] = useState<string[]>([]);
  const [blockedPermissions, setBlockedPermissions] = useState<string[]>([]);
  const [defaultTtlDays, setDefaultTtlDays] = useState(30);
  const [availableToEveryone, setAvailableToEveryone] = useState(true);
  const [availableToGroups, setAvailableToGroups] = useState<string[]>([]);
  const [availableToUsers, setAvailableToUsers] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body: DelegationTemplateCreateRequest = {
      agent_id: agentId.trim(),
      max_permissions: maxPermissions,
      blocked_permissions: blockedPermissions,
      default_ttl_days: defaultTtlDays,
      available_to_roles: availableToEveryone ? ["all"] : [],
      available_to_groups: availableToEveryone ? [] : availableToGroups,
      available_to_users: availableToEveryone ? [] : availableToUsers,
    };

    try {
      await apiClient("admin/delegation-templates", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onOpenChange(false);
      onCreated();
      setAgentId("");
      setMaxPermissions([]);
      setBlockedPermissions([]);
      setDefaultTtlDays(30);
      setAvailableToEveryone(true);
      setAvailableToGroups([]);
      setAvailableToUsers([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Delegation Template</DialogTitle>
          <DialogDescription>
            Define a reusable template for agent delegations.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label>Agent</Label>
            <AgentSelector value={agentId} onChange={setAgentId} />
          </div>

          <div className="space-y-2">
            <Label>
              Max Permissions
              {maxPermissions.length > 0 && (
                <Badge variant="secondary" className="ml-2 text-xs">
                  {maxPermissions.length} selected
                </Badge>
              )}
            </Label>
            <PermissionPicker
              selected={maxPermissions}
              onChange={setMaxPermissions}
            />
          </div>

          <div className="space-y-2">
            <Label>
              Blocked Permissions
              {blockedPermissions.length > 0 && (
                <Badge variant="destructive" className="ml-2 text-xs">
                  {blockedPermissions.length} blocked
                </Badge>
              )}
            </Label>
            <PermissionPicker
              selected={blockedPermissions}
              onChange={setBlockedPermissions}
              variant="block"
            />
          </div>

          <div className="space-y-2">
            <Label>Default TTL</Label>
            <TTLSelector
              value={defaultTtlDays}
              onChange={setDefaultTtlDays}
              unit="days"
            />
          </div>

          <div className="space-y-2">
            <Label>Available To</Label>
            <AvailableToPicker
              everyone={availableToEveryone}
              onEveryoneChange={setAvailableToEveryone}
              selectedGroups={availableToGroups}
              selectedUsers={availableToUsers}
              onGroupsChange={setAvailableToGroups}
              onUsersChange={setAvailableToUsers}
            />
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
            <Button type="submit" disabled={submitting || !agentId}>
              {submitting ? "Creating..." : "Create Template"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const PROVISION_MODE_LABELS: Record<ProvisionMode, string> = {
  off: "Off",
  on_login: "On login",
  on_invite: "Invite",
};

function EditTemplateDialog({
  template,
  open,
  onOpenChange,
  onSaved,
  onInvite,
}: {
  template: DelegationTemplate | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  onInvite: (template: DelegationTemplate) => void;
}) {
  const [provisionMode, setProvisionMode] = useState<ProvisionMode>("off");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleOpen = (isOpen: boolean) => {
    if (isOpen && template) {
      setProvisionMode(template.provision_mode || "off");
      setError(null);
    }
    onOpenChange(isOpen);
  };

  const handleSave = async () => {
    if (!template) return;
    setSubmitting(true);
    setError(null);
    const body: DelegationTemplateUpdateRequest = {
      provision_mode: provisionMode,
      auto_provision: provisionMode === "on_login",
    };
    try {
      await apiClient(`admin/delegation-templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update template");
    } finally {
      setSubmitting(false);
    }
  };

  if (!template) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Template Provisioning</DialogTitle>
          <DialogDescription>
            Configure how delegations are provisioned for {template.agent_id}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {(["off", "on_login", "on_invite"] as ProvisionMode[]).map((mode) => (
            <label key={mode} className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="provision_mode"
                checked={provisionMode === mode}
                onChange={() => setProvisionMode(mode)}
                className="mt-1"
              />
              <span>
                <span className="font-medium">{PROVISION_MODE_LABELS[mode]}</span>
                <span className="block text-xs text-muted-foreground">
                  {mode === "off" && "Template ceiling only — users create delegations manually"}
                  {mode === "on_login" && "Eligible users receive delegation at SSO login"}
                  {mode === "on_invite" && "Admin sends pending invites for users to accept"}
                </span>
              </span>
            </label>
          ))}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
          {provisionMode === "on_invite" && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                onInvite(template);
              }}
            >
              <Mail className="mr-2 h-4 w-4" />
              Invite users
            </Button>
          )}
          <div className="flex gap-2 ml-auto">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={submitting}>
              {submitting ? "Saving..." : "Save Template"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function InviteUsersDialog({
  template,
  open,
  onOpenChange,
  onInvited,
}: {
  template: DelegationTemplate | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: () => void;
}) {
  const [emailsText, setEmailsText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const handleOpen = (isOpen: boolean) => {
    if (isOpen) {
      setEmailsText("");
      setError(null);
      setResult(null);
    }
    onOpenChange(isOpen);
  };

  const handleInvite = async () => {
    if (!template) return;
    const emails = emailsText
      .split(/[\n,]+/)
      .map((e) => e.trim())
      .filter(Boolean);
    if (emails.length === 0) {
      setError("Enter at least one email address");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const data = await apiClient<{ invited: number; skipped: string[] }>(
        `admin/delegation-templates/${template.id}/invite`,
        {
          method: "POST",
          body: JSON.stringify({ user_emails: emails }),
        },
      );
      setResult(
        `Invited ${data.invited} user(s)${
          data.skipped?.length ? ` · skipped ${data.skipped.length}` : ""
        }`,
      );
      onInvited();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send invites");
    } finally {
      setSubmitting(false);
    }
  };

  if (!template) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Invite to {template.agent_id}</DialogTitle>
          <DialogDescription>
            Users receive a pending delegation to accept
          </DialogDescription>
        </DialogHeader>
        <textarea
          className="min-h-[120px] w-full rounded-md border px-3 py-2 text-sm"
          placeholder="One email per line"
          value={emailsText}
          onChange={(e) => setEmailsText(e.target.value)}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        {result && <p className="text-sm text-green-700">{result}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleInvite} disabled={submitting}>
            {submitting ? "Sending..." : "Send invites"}
          </Button>
        </DialogFooter>
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
  const [agentNameMap, setAgentNameMap] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [allowFreeform, setAllowFreeform] = useState<boolean | null>(null);
  const [freeformUpdating, setFreeformUpdating] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<DelegationTemplate | null>(null);
  const [invitingTemplate, setInvitingTemplate] = useState<DelegationTemplate | null>(null);
  const [editingDelegation, setEditingDelegation] = useState<AdminDelegation | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      const resp = await apiClient<Agent[] | { agents: Agent[] }>("agents/");
      const agents = Array.isArray(resp) ? resp : (resp.agents ?? []);
      setAgentNameMap(Object.fromEntries(agents.map((a) => [a.agent_id, a.name || a.agent_id])));
    } catch {
      // non-critical; falls back to showing agent_id
    }
  }, []);

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

  const fetchDelegationPolicy = useCallback(async () => {
    try {
      const data = await apiClient<{ allow_freeform: boolean }>(
        "admin/settings/delegation-policy"
      );
      setAllowFreeform(data.allow_freeform);
    } catch {
      setAllowFreeform(false);
    }
  }, []);

  const toggleFreeform = async () => {
    const newVal = !allowFreeform;
    setFreeformUpdating(true);
    try {
      await apiClient("admin/settings/delegation-policy", {
        method: "PUT",
        body: JSON.stringify({ allow_freeform: newVal }),
      });
      setAllowFreeform(newVal);
    } catch {
      // revert
    } finally {
      setFreeformUpdating(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchTemplates();
    fetchDelegations();
    fetchDelegationPolicy();
  }, [fetchAgents, fetchTemplates, fetchDelegations, fetchDelegationPolicy]);

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
      <div className="space-y-3">
        {templates.map((tmpl) => {
          const grouped = groupPermissionsByService(tmpl.max_permissions);
          const availParts: string[] = [];
          if (tmpl.available_to_roles.includes("all")) {
            availParts.push("Everyone");
          } else {
            if (tmpl.available_to_groups?.length) availParts.push(...tmpl.available_to_groups);
            if (tmpl.available_to_users?.length) availParts.push(...tmpl.available_to_users);
          }

          const createdDate = new Date(tmpl.created_at);
          const expiryDate = new Date(createdDate.getTime() + tmpl.default_ttl_days * 86400000);
          const isExpired = Date.now() > expiryDate.getTime();

          return (
            <Card key={tmpl.id} className="px-6 py-4">
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium">
                      {agentNameMap[tmpl.agent_id] || tmpl.agent_id}
                    </span>
                    <Badge variant={isExpired ? "destructive" : "outline"} className="text-xs">
                      {isExpired
                        ? `Expired · TTL was ${tmpl.default_ttl_days}d · ${expiryDate.toLocaleDateString()}`
                        : `TTL: ${tmpl.default_ttl_days}d · Expires ${expiryDate.toLocaleDateString()}`}
                    </Badge>
                    <Badge variant="secondary" className="text-xs capitalize">
                      {PROVISION_MODE_LABELS[tmpl.provision_mode || "off"]}
                    </Badge>
                    {tmpl.blocked_permissions.length > 0 && (
                      <Badge variant="destructive" className="text-xs">
                        {tmpl.blocked_permissions.length} blocked
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(grouped).map(([svc, perms]) => (
                      <Badge key={svc} variant="secondary" className="text-xs">
                        {svc}: {perms.join(", ")}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Available to: {availParts.length > 0 ? availParts.join(", ") : "Everyone"}
                    {" · "}Created: {createdDate.toLocaleDateString()}
                  </p>
                </div>
                <div className="flex shrink-0 ml-2 gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingTemplate(tmpl)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  {tmpl.provision_mode === "on_invite" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setInvitingTemplate(tmpl)}
                    >
                      <Mail className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleDeleteTemplate(tmpl.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
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
              <th className="px-4 py-3 text-left font-medium">TTL</th>
              <th className="px-4 py-3 text-left font-medium">Expires</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filtered.map((d) => {
              const isRevoked = !!d.revoked_at || d.status === "revoked";
              const isPending = d.status === "pending";
              const expiry = formatExpiryInfo(d.created_at, d.expires_at);
              const isActive = !isRevoked && !expiry.isExpired && !isPending;
              return (
                <tr key={d.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">
                    {agentNameMap[d.agent_id] || d.agent_id}
                  </td>
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
                    {expiry.ttlLabel}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {d.expires_at ? new Date(d.expires_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1.5">
                      <StatusDot active={isActive} />
                      <span className={cn("text-xs", isActive ? "text-green-700" : isPending ? "text-amber-700" : "text-red-700")}>
                        {isPending ? "Invited" : isRevoked ? "Revoked" : expiry.isExpired ? "Expired" : "Active"}
                      </span>
                    </span>
                    {d.revoked_at && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(d.revoked_at).toLocaleDateString()}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      {isActive && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingDelegation(d)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {(isActive || isPending) && (
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
                    </div>
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

      {/* Delegation Policy */}
      {allowFreeform !== null && (
        <Card className="px-5 py-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Free-form delegation creation</p>
              <p className="text-xs text-muted-foreground">
                {allowFreeform
                  ? "Users can create delegations without a template"
                  : "Users must select a template to create delegations"}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={allowFreeform}
              disabled={freeformUpdating}
              onClick={toggleFreeform}
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
                allowFreeform ? "bg-primary" : "bg-muted"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none inline-block h-5 w-5 rounded-full bg-background shadow-lg transition-transform",
                  allowFreeform ? "translate-x-5" : "translate-x-0"
                )}
              />
            </button>
          </div>
        </Card>
      )}

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

      <EditTemplateDialog
        template={editingTemplate}
        open={!!editingTemplate}
        onOpenChange={(open) => !open && setEditingTemplate(null)}
        onSaved={fetchTemplates}
        onInvite={(tmpl) => setInvitingTemplate(tmpl)}
      />

      <InviteUsersDialog
        template={invitingTemplate}
        open={!!invitingTemplate}
        onOpenChange={(open) => !open && setInvitingTemplate(null)}
        onInvited={fetchDelegations}
      />

      <EditDelegationSheet
        delegation={editingDelegation}
        open={!!editingDelegation}
        onOpenChange={(open) => !open && setEditingDelegation(null)}
        onSaved={fetchDelegations}
        agentName={
          editingDelegation
            ? agentNameMap[editingDelegation.agent_id]
            : undefined
        }
      />
    </div>
  );
}
