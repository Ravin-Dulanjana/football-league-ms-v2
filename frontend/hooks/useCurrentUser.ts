"use client";

import { useQuery } from "@tanstack/react-query";
import type { UserRead, UserRole } from "@/types";

async function fetchMe(): Promise<UserRead> {
  const res = await fetch("/api/auth/me");
  if (!res.ok) throw new Error("Unauthorized");
  return res.json();
}

/** Returns the current authenticated user and role-check helpers. */
export function useCurrentUser() {
  const { data: user, isLoading, error } = useQuery<UserRead>({
    queryKey: ["auth", "me"],
    queryFn: fetchMe,
    staleTime: 5 * 60 * 1000, // 5 minutes — don't re-fetch on every component mount
    retry: false,             // 401 means logged out — don't retry
  });

  const role = user?.role as UserRole | undefined;

  return {
    user,
    isLoading,
    isAuthenticated: !!user && !error,
    role,
    isSuperAdmin: role === "super_admin",
    isLeagueAdmin: role === "league_admin",
    isClubAdmin: role === "club_admin",
    isPlayer: role === "player",
    isClubStaff: role === "club_staff",
    isLeagueLevel: role === "super_admin" || role === "league_admin",
    isAnyAdmin:
      role === "super_admin" || role === "league_admin" || role === "club_admin",
  };
}
