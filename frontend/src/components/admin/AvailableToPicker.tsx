"use client";

import { useEffect, useState, useCallback } from "react";
import { ChevronDown, ChevronRight, Loader2, Users, User } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { OrgDirectoryResponse, OrgDirectoryEntry } from "@/lib/types/admin";

interface AvailableToPickerProps {
  selectedGroups: string[];
  selectedUsers: string[];
  onGroupsChange: (groups: string[]) => void;
  onUsersChange: (users: string[]) => void;
  everyone: boolean;
  onEveryoneChange: (everyone: boolean) => void;
}

export function AvailableToPicker({
  selectedGroups,
  selectedUsers,
  onGroupsChange,
  onUsersChange,
  everyone,
  onEveryoneChange,
}: AvailableToPickerProps) {
  const [directory, setDirectory] = useState<OrgDirectoryResponse | null>(null);
  const [dirLoading, setDirLoading] = useState(true);
  const [dirError, setDirError] = useState<string | null>(null);
  const [groupsOpen, setGroupsOpen] = useState(true);
  const [usersOpen, setUsersOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadDirectory() {
      try {
        const data = await apiClient<OrgDirectoryResponse>("admin/directory");
        if (!cancelled) setDirectory(data);
      } catch {
        if (!cancelled) setDirError("Failed to load directory");
      } finally {
        if (!cancelled) setDirLoading(false);
      }
    }
    loadDirectory();
    return () => { cancelled = true; };
  }, []);

  const getGroupMembers = useCallback(
    (groupEmail: string): string[] => {
      if (!directory) return [];
      const group = directory.groups.find((g) => g.email === groupEmail);
      return group?.members ?? [];
    },
    [directory]
  );

  const getUserGroups = useCallback(
    (userEmail: string): string[] => {
      if (!directory) return [];
      return directory.groups
        .filter((g) => (g.members ?? []).includes(userEmail))
        .map((g) => g.email);
    },
    [directory]
  );

  function toggleGroup(email: string) {
    if (everyone) onEveryoneChange(false);

    if (selectedGroups.includes(email)) {
      const members = getGroupMembers(email);
      const remainingGroupMembers = new Set<string>();
      for (const otherGroup of selectedGroups) {
        if (otherGroup !== email) {
          for (const m of getGroupMembers(otherGroup)) {
            remainingGroupMembers.add(m);
          }
        }
      }
      const usersToRemove = members.filter(
        (m) => !remainingGroupMembers.has(m)
      );
      onGroupsChange(selectedGroups.filter((g) => g !== email));
      onUsersChange(
        selectedUsers.filter((u) => !usersToRemove.includes(u))
      );
    } else {
      const members = getGroupMembers(email);
      onGroupsChange([...selectedGroups, email]);
      const newUsers = members.filter((m) => !selectedUsers.includes(m));
      if (newUsers.length > 0) {
        onUsersChange([...selectedUsers, ...newUsers]);
      }
    }
  }

  function toggleUser(email: string) {
    if (everyone) onEveryoneChange(false);

    if (selectedUsers.includes(email)) {
      onUsersChange(selectedUsers.filter((u) => u !== email));
    } else {
      const userGroups = getUserGroups(email);
      const newGroups = userGroups.filter((g) => !selectedGroups.includes(g));
      onUsersChange([...selectedUsers, email]);
      if (newGroups.length > 0) {
        const membersToAdd: string[] = [];
        for (const g of newGroups) {
          for (const m of getGroupMembers(g)) {
            if (!selectedUsers.includes(m) && m !== email && !membersToAdd.includes(m)) {
              membersToAdd.push(m);
            }
          }
        }
        onGroupsChange([...selectedGroups, ...newGroups]);
        if (membersToAdd.length > 0) {
          onUsersChange([...selectedUsers, email, ...membersToAdd]);
          return;
        }
      }
    }
  }

  const hasDirectory =
    directory &&
    (directory.groups.length > 0 || directory.users.length > 0);

  return (
    <div className="grid gap-3">
      {/* Everyone toggle */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={everyone}
          onChange={(e) => {
            onEveryoneChange(e.target.checked);
            if (e.target.checked) {
              onGroupsChange([]);
              onUsersChange([]);
            }
          }}
          className="h-4 w-4 rounded border-border accent-primary"
        />
        <span className="text-sm font-medium">Everyone</span>
        <span className="text-xs text-muted-foreground">
          — available to all users in the organization
        </span>
      </label>

      {everyone && (
        <p className="text-xs text-muted-foreground ml-6">
          Uncheck to restrict access to specific groups or users.
        </p>
      )}

      {/* Groups */}
      <div className={cn("rounded-md border", everyone && "opacity-40")}>
        <button
          type="button"
          onClick={() => !everyone && setGroupsOpen(!groupsOpen)}
          disabled={everyone}
          className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors disabled:cursor-not-allowed"
        >
          {groupsOpen && !everyone ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <Users className="h-3.5 w-3.5 text-muted-foreground" />
          <span>Groups</span>
          {selectedGroups.length > 0 && (
            <span className="ml-auto rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
              {selectedGroups.length}
            </span>
          )}
        </button>
        {groupsOpen && !everyone && (
          <div className="border-t px-3 py-2">
            {dirLoading ? (
              <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading groups...
              </div>
            ) : dirError ? (
              <p className="py-2 text-sm text-red-600">{dirError}</p>
            ) : !hasDirectory ? (
              <p className="py-2 text-xs text-muted-foreground">
                No directory data — sync happens automatically on admin login
              </p>
            ) : directory!.groups.length === 0 ? (
              <p className="py-2 text-xs text-muted-foreground">No groups found</p>
            ) : (
              <div className="max-h-48 space-y-1 overflow-y-auto">
                {directory!.groups.map((group: OrgDirectoryEntry) => (
                  <label
                    key={group.email}
                    className="flex items-center gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedGroups.includes(group.email)}
                      onChange={() => toggleGroup(group.email)}
                      className="h-3.5 w-3.5 rounded border-border accent-primary"
                    />
                    <span className="truncate">
                      {group.display_name || group.email}
                      {group.member_count != null && (
                        <span className="ml-1 text-muted-foreground">
                          ({group.member_count} members)
                        </span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Users */}
      <div className={cn("rounded-md border", everyone && "opacity-40")}>
        <button
          type="button"
          onClick={() => !everyone && setUsersOpen(!usersOpen)}
          disabled={everyone}
          className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors disabled:cursor-not-allowed"
        >
          {usersOpen && !everyone ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <User className="h-3.5 w-3.5 text-muted-foreground" />
          <span>Users</span>
          {selectedUsers.length > 0 && (
            <span className="ml-auto rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
              {selectedUsers.length}
            </span>
          )}
        </button>
        {usersOpen && !everyone && (
          <div className="border-t px-3 py-2">
            {dirLoading ? (
              <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading users...
              </div>
            ) : dirError ? (
              <p className="py-2 text-sm text-red-600">{dirError}</p>
            ) : !hasDirectory ? (
              <p className="py-2 text-xs text-muted-foreground">
                No directory data — sync happens automatically on admin login
              </p>
            ) : directory!.users.length === 0 ? (
              <p className="py-2 text-xs text-muted-foreground">No users found</p>
            ) : (
              <div className="max-h-48 space-y-1 overflow-y-auto">
                {directory!.users.map((user: OrgDirectoryEntry) => (
                  <label
                    key={user.email}
                    className="flex items-center gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedUsers.includes(user.email)}
                      onChange={() => toggleUser(user.email)}
                      className="h-3.5 w-3.5 rounded border-border accent-primary"
                    />
                    <span className="truncate">
                      {user.display_name || user.email}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
