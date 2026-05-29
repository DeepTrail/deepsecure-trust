"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type { UserRole } from "@/lib/types/admin";

interface UserRoleState {
  role: UserRole;
  isAdmin: boolean;
  isLoading: boolean;
  error: string | null;
}

/**
 * Hook to fetch the current user's role from the backend.
 * Returns the role, a convenience `isAdmin` boolean, and loading/error state.
 *
 * The role is fetched once on mount and cached for the session.
 */
export function useUserRole(): UserRoleState {
  const [state, setState] = useState<UserRoleState>({
    role: "employee",
    isAdmin: false,
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchRole() {
      try {
        const data = await apiClient<{ role?: UserRole }>("users/me");
        if (cancelled) return;
        const role = data.role ?? "employee";
        setState({
          role,
          isAdmin: role === "admin" || role === "security",
          isLoading: false,
          error: null,
        });
      } catch (err) {
        if (cancelled) return;
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: err instanceof Error ? err.message : "Failed to fetch user role",
        }));
      }
    }

    fetchRole();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
