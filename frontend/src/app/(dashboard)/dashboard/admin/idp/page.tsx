"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Fingerprint,
  Plus,
  RefreshCw,
  Pencil,
  Trash2,
  Upload,
  Info,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import type {
  CanonicalRole,
  IdpMapping,
  IdpMappingCreateRequest,
  IdpMappingListResponse,
  IdpMappingUpdateRequest,
  IdpImportYamlResponse,
} from "@/lib/types/admin";

const CANONICAL_ROLES: CanonicalRole[] = [
  "employee",
  "engineer",
  "sales",
  "admin",
  "security",
];

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; payload: IdpMappingListResponse };

interface FormState {
  group_name: string;
  role: CanonicalRole;
  enabled: boolean;
}

const EMPTY_FORM: FormState = { group_name: "", role: "employee", enabled: true };

export default function AdminIdpPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<IdpMapping | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const fetchMappings = useCallback(async () => {
    try {
      const payload = await apiClient<IdpMappingListResponse>("admin/idp/mappings");
      setState({ kind: "data", payload });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load IdP mappings",
      });
    }
  }, []);

  useEffect(() => {
    fetchMappings();
  }, [fetchMappings]);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(mapping: IdpMapping) {
    setEditing(mapping);
    setForm({
      group_name: mapping.group_name,
      role: mapping.role,
      enabled: mapping.enabled,
    });
    setFormError(null);
    setDialogOpen(true);
  }

  async function handleSubmit() {
    if (!form.group_name.trim()) {
      setFormError("Group name is required");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      if (editing) {
        const body: IdpMappingUpdateRequest = {
          group_name: form.group_name.trim(),
          role: form.role,
          enabled: form.enabled,
        };
        await apiClient(`admin/idp/mappings/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      } else {
        const body: IdpMappingCreateRequest = {
          group_name: form.group_name.trim(),
          role: form.role,
          enabled: form.enabled,
        };
        await apiClient("admin/idp/mappings", {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      setDialogOpen(false);
      await fetchMappings();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(mapping: IdpMapping) {
    if (!confirm(`Delete mapping for group "${mapping.group_name}"?`)) return;
    try {
      await apiClient(`admin/idp/mappings/${mapping.id}`, { method: "DELETE" });
      await fetchMappings();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function handleImportYaml() {
    setImporting(true);
    try {
      const result = await apiClient<IdpImportYamlResponse>(
        "admin/idp/mappings/import-yaml",
        { method: "POST" }
      );
      await fetchMappings();
      alert(`Imported ${result.imported} mappings (${result.skipped} skipped).`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error") {
    return <ErrorCard title="IdP Integration" message={state.message} retry={fetchMappings} />;
  }

  const { payload } = state;
  const { mappings, idp_metadata } = payload;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Fingerprint className="h-6 w-6" />
            IdP Integration
          </h1>
          <p className="text-muted-foreground">
            Map IdP groups to DeepSecure roles. DB mappings override YAML for the same group.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchMappings}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleImportYaml} disabled={importing}>
            <Upload className="mr-1.5 h-4 w-4" />
            Import from YAML
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add mapping
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <p className="text-sm font-medium text-muted-foreground">Connection (read-only)</p>
        <div className="mt-2 grid gap-1 text-sm">
          <p>
            <span className="text-muted-foreground">Provider:</span>{" "}
            {idp_metadata.provider}
          </p>
          <p>
            <span className="text-muted-foreground">Issuer:</span>{" "}
            {idp_metadata.issuer_url}
          </p>
        </div>
      </Card>

      <div className="flex items-start gap-2 rounded-lg border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          DB mappings override YAML for the same (issuer, group) key. Roles apply on the
          user&apos;s next SSO login.
        </p>
      </div>

      {mappings.length === 0 ? (
        <EmptyState
          title="No group mappings configured"
          description="YAML fallbacks still apply. Add a mapping or import from group_policies.yaml."
          action={{ label: "Add mapping", onClick: openCreate }}
        />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    IdP Group
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    DeepSecure Role
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Updated
                  </th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((mapping) => (
                  <tr
                    key={mapping.id}
                    className={cn(
                      "border-b last:border-0 hover:bg-muted/30",
                      !mapping.enabled && "opacity-60",
                    )}
                  >
                    <td className="px-6 py-3 font-medium">{mapping.group_name}</td>
                    <td className="px-6 py-3">
                      <Badge variant="outline">{mapping.role}</Badge>
                    </td>
                    <td className="px-6 py-3">
                      <Badge
                        variant="outline"
                        className={cn(
                          mapping.enabled
                            ? "border-green-500 text-green-700"
                            : "border-gray-400 text-gray-500",
                        )}
                      >
                        {mapping.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </td>
                    <td className="px-6 py-3 text-muted-foreground">
                      {mapping.updated_at
                        ? new Date(mapping.updated_at).toLocaleString()
                        : new Date(mapping.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(mapping)}
                          aria-label="Edit mapping"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(mapping)}
                          aria-label="Delete mapping"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit mapping" : "Add mapping"}</DialogTitle>
            <DialogDescription>
              Map an IdP group name to a canonical DeepSecure role for issuer{" "}
              {idp_metadata.issuer_url}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="group_name">IdP Group</Label>
              <Input
                id="group_name"
                value={form.group_name}
                onChange={(e) => setForm((f) => ({ ...f, group_name: e.target.value }))}
                placeholder="engineering or sales@acme.com"
              />
            </div>
            <div className="space-y-2">
              <Label>DeepSecure Role</Label>
              <Select
                value={form.role}
                onValueChange={(v) => setForm((f) => ({ ...f, role: v as CanonicalRole }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CANONICAL_ROLES.map((role) => (
                    <SelectItem key={role} value={role}>
                      {role}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <input
                id="enabled"
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
                className="h-4 w-4"
              />
              <Label htmlFor="enabled">Enabled</Label>
            </div>
            {formError && <p className="text-sm text-destructive">{formError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Saving…" : editing ? "Save changes" : "Create mapping"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
