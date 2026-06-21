"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  ClipboardList,
  FileText,
  Home,
  Info,
  Key,
  ListChecks,
  LogOut,
  ScrollText,
  Shield,
  Users,
  UserCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { clubMembershipsApi, registrationsApi } from "@/lib/api";
import type { ClubMembershipRequestRead, RegistrationRequestRead } from "@/types";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  exact?: boolean;
  badge?: number;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading, role, isClubAdmin, isLeagueLevel, isSuperAdmin } = useCurrentUser();

  const hasClub = !!user?.club_id;
  const isRegularUser = !isSuperAdmin;

  // Pending invite count for users without a club
  const { data: membershipRequests } = useQuery<ClubMembershipRequestRead[]>({
    queryKey: ["club-memberships", "requests"],
    queryFn: clubMembershipsApi.listRequests,
    enabled: isRegularUser && !hasClub,
    staleTime: 30_000,
  });
  const pendingInviteCount = (membershipRequests ?? []).filter(
    (r) => r.status === "pending"
  ).length;

  // Pending registration request count for users with a club
  const { data: regRequests } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    enabled: isRegularUser && hasClub && !isClubAdmin,
    staleTime: 30_000,
  });
  const pendingRegCount = (regRequests ?? []).filter(
    (r) => r.status === "pending_player_confirmation"
  ).length;

  const profileBadge = !hasClub ? pendingInviteCount : pendingRegCount;

  const NAV_GROUPS: NavGroup[] = [
    {
      label: "Overview",
      items: [
        { label: "Dashboard", href: "/dashboard", icon: Home, exact: true },
        { label: "Clubs", href: "/dashboard/clubs", icon: Building2, exact: true },
        { label: "Members", href: "/dashboard/users", icon: Users },
        { label: "Notifications", href: "/dashboard/notifications", icon: Bell },
        {
          label: "My Profile",
          href: "/dashboard/profile",
          icon: UserCircle,
          badge: profileBadge > 0 ? profileBadge : undefined,
        },
        ...(hasClub
          ? [{ label: "My Club", href: `/dashboard/clubs/${user!.club_id}`, icon: Building2 }]
          : []),
        // All non-super_admin users get a personal release history page
        ...(!isSuperAdmin
          ? [{ label: "My Release Docs", href: "/dashboard/my-docs", icon: BookOpen }]
          : []),
      ],
    },
    {
      label: "Operations",
      items: [
        // Registrations & Releases: club admins and league admins only
        ...(isClubAdmin || isLeagueLevel || isSuperAdmin
          ? [
              { label: "Registrations", href: "/dashboard/registrations", icon: ClipboardList },
              { label: "Releases", href: "/dashboard/releases", icon: FileText },
            ]
          : []),
        ...(isLeagueLevel || isClubAdmin
          ? [{ label: "Seasons", href: "/dashboard/seasons", icon: ScrollText }]
          : []),
      ],
    },
    {
      label: "League Office",
      items: [
        ...(isLeagueLevel
          ? [
              { label: "Squad Submissions", href: "/dashboard/submissions", icon: ListChecks },
              { label: "Unlock Requests", href: "/dashboard/unlock-requests", icon: Key },
              { label: "Analytics", href: "/dashboard/analytics", icon: BarChart3 },
              { label: "Audit Logs", href: "/dashboard/audit-logs", icon: Shield },
              { label: "League Info", href: "/dashboard/league-info", icon: Info },
            ]
          : []),
        ...(isLeagueLevel || isClubAdmin
          ? [{ label: "Reports", href: "/dashboard/reports", icon: BarChart3 }]
          : []),
      ],
    },
  ];

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    toast.success("Signed out");
    router.push("/login");
    router.refresh();
  };

  return (
    <aside className="flex flex-col w-60 border-r border-border bg-card shrink-0 h-full">
      {/* Brand */}
      <Link
        href="/dashboard/league-info"
        className="flex items-center gap-3 px-4 h-16 border-b border-border hover:bg-secondary transition-colors"
      >
        <Image
          src="/logo.png"
          alt="Wattala Football League"
          width={44}
          height={44}
          className="rounded-full shrink-0"
        />
        <div className="leading-tight min-w-0">
          <p className="font-serif font-semibold text-sm text-foreground tracking-tight leading-snug">
            Wattala<br />Football League
          </p>
        </div>
      </Link>

      {/* Nav groups */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-4">
        {NAV_GROUPS.map((group) => {
          if (group.items.length === 0) return null;
          return (
            <div key={group.label}>
              <p className="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-[.14em] text-muted-foreground">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = item.exact
                    ? pathname === item.href
                    : pathname.startsWith(item.href);

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-semibold transition-colors",
                        isActive
                          ? "bg-primary text-white"
                          : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate flex-1">{item.label}</span>
                      {item.badge !== undefined && item.badge > 0 && (
                        <span className={cn(
                          "text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1",
                          isActive
                            ? "bg-white/20 text-white"
                            : "bg-primary text-white"
                        )}>
                          {item.badge > 9 ? "9+" : item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <Separator />

      {/* User footer */}
      <div className="p-3 space-y-1">
        {isLoading ? (
          <div className="space-y-2 px-1">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        ) : (
          <div className="px-3 py-2">
            <p className="text-xs font-semibold text-foreground truncate">{user?.email}</p>
            <p className="text-xs text-muted-foreground capitalize">
              {role?.replace(/_/g, " ")}
            </p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm font-semibold text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
