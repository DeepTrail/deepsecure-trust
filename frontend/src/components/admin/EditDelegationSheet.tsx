"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PermissionPicker } from "@/components/delegation/PermissionPicker";
import type { AdminDelegation } from "@/lib/types/admin";

interface EditDelegationSheetProps {
  delegation: AdminDelegation | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  agentName?: string;
}

export function EditDelegationSheet({
  delegation,
  open,
  onOpenChange,
  onSaved,
  agentName,
}: EditDelegationSheetProps) {
  const [permissions, setPermissions] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleOpen = (isOpen: boolean) => {
    if (isOpen && delegation) {
      setPermissions(delegation.delegated_permissions);
      setError(null);
    }
    onOpenChange(isOpen);
  };

  const handleSave = async () => {
    if (!delegation) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiClient(`admin/delegations/${delegation.id}`, {
        method: "PATCH",
        body: JSON.stringify({ permissions }),
      });
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update delegation");
    } finally {
      setSubmitting(false);
    }
  };

  if (!delegation) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Delegation</DialogTitle>
          <DialogDescription>
            Narrow permissions for {agentName || delegation.agent_id} · {delegation.delegator}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>
              Permissions
              {permissions.length > 0 && (
                <span className="ml-2 text-xs text-muted-foreground">
                  {permissions.length} selected
                </span>
              )}
            </Label>
            <PermissionPicker selected={permissions} onChange={setPermissions} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={submitting}>
            {submitting ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
