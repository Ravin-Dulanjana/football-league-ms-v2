"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  Building2,
  ChevronRight,
  ClipboardList,
  FileText,
  Home,
  Info,
  Key,
  ListChecks,
  LogOut,
  MoreHorizontal,
  ScrollText,
  Search,
  Shield,
  Shirt,
  UserCheck,
  UserCircle,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { notificationsApi } from "@/lib/api";
import type { NotificationRead } from "@/types";

// ---------------------------------------------------------------------------
// Bottom tab bar — 5 tabs
// ---------------------------------------------------------------------------

const TABS = [
  { label: "Home", href: "/dashboard", icon: Home },
  { label: "Clubs", href: "/dashboard/clubs", icon: Building2 },
  { label: "Players", href: "/dashboard/players", icon: Shirt },
  { label: "Alerts", href: "/dashboard/notifications", icon: Bell, isAlerts: true },
  { label: "More", href: "#more", icon: MoreHorizontal, isMore: true },
];

// ---------------------------------------------------------------------------
// All destinations for the More sheet
// ---------------------------------------------------------------------------

interface SheetItem {
  label: string;
  href: string;
  icon: React.ElementType;
  roles?: string[];
}

interface SheetGroup {
  label: string;
  items: SheetItem[];
}

const SHEET_GROUPS: SheetGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: Home },
      { label: "Clubs", href: "/dashboard/clubs", icon: Building2 },
      { label: "Players", href: "/dashboard/players", icon: Shirt },
      { label: "Notifications", href: "/dashboard/notifications", icon: Bell },
      { label: "My Profile", href: "/dashboard/profile", icon: UserCircle },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        label: "Club Roster",
        href: "/dashboard/club-memberships",
        icon: UserCheck,
        roles: ["super_admin", "league_admin", "club_admin"],
      },
      {
        label: "Registrations",
        href: "/dashboard/registrations",
        icon: ClipboardList,
        roles: ["club_admin", "club_staff", "player"],
      },
      {
        label: "Releases",
        href: "/dashboard/releases",
        icon: FileText,
        roles: ["club_admin", "club_staff", "player"],
      },
      {
        label: "Seasons",
        href: "/dashboard/seasons",
        icon: ScrollText,
        roles: ["super_admin", "league_admin", "club_admin"],
      },
    ],
  },
  {
    label: "League Office",
    items: [
      {
        label: "Squad Submissions",
        href: "/dashboard/submissions",
        icon: ListChecks,
        roles: ["super_admin", "league_admin"],
      },
      {
        label: "Unlock Requests",
        href: "/dashboard/unlock-requests",
        icon: Key,
        roles: ["super_admin", "league_admin"],
      },
      {
        label: "Analytics",
        href: "/dashboard/analytics",
        icon: BarChart3,
        roles: ["super_admin", "league_admin"],
      },
      {
        label: "Audit Logs",
        href: "/dashboard/audit-logs",
        icon: Shield,
        roles: ["super_admin", "league_admin"],
      },
      {
        label: "Users",
        href: "/dashboard/users",
        icon: Users,
        roles: ["super_admin", "league_admin", "club_admin"],
      },
      {
        label: "Reports",
        href: "/dashboard/reports",
        icon: BarChart3,
        roles: ["super_admin", "league_admin", "club_admin"],
      },
      {
        label: "League Info",
        href: "/dashboard/league-info",
        icon: Info,
        roles: ["super_admin", "league_admin"],
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// More sheet
// ---------------------------------------------------------------------------

function MoreSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role } = useCurrentUser();
  const [search, setSearch] = useState("");

  const handleLogout = async () => {
    onClose();
    await fetch("/api/auth/logout", { method: "POST" });
    toast.success("Signed out");
    router.push("/login");
    router.refresh();
  };

  const allItems = SHEET_GROUPS.flatMap((g) =>
    g.items.filter((item) => !item.roles || (role && item.roles.includes(role)))
  );

  const filtered = search.trim()
    ? allItems.filter((item) =>
        item.label.toLowerCase().includes(search.toLowerCase())
      )
    : null;

  if (!open) return null;

  return (
    <>
      {/* Scrim */}
      <div
        className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Sheet */}
      <div className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl bg-card shadow-card animate-slide-up max-h-[85vh] flex flex-col">
        {/* Grabber */}
        <div className="flex justify-center pt-3 pb-1 shrink-0">
          <div className="w-10 h-1 rounded-full bg-border" />
        </div>

        {/* Close */}
        <div className="flex items-center justify-between px-4 pb-3 shrink-0">
          <span className="text-sm font-bold text-foreground">Menu</span>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-muted-foreground hover:bg-secondary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Profile card */}
        <Link
          href="/dashboard/profile"
          onClick={onClose}
          className="mx-4 mb-3 flex items-center gap-3 rounded-xl border border-border bg-secondary p-3 shrink-0"
        >
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
            <span className="text-sm font-bold text-primary">
              {user?.email?.[0]?.toUpperCase() ?? "?"}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-foreground truncate">{user?.email}</p>
            <p className="text-xs text-muted-foreground capitalize">
              {role?.replace(/_/g, " ")}
            </p>
          </div>
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        </Link>

        {/* Search */}
        <div className="px-4 mb-3 shrink-0">
          <div className="relative flex items-center">
            <Search className="absolute left-3 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <input
              type="search"
              placeholder="Search menu…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-[10px] border border-input bg-secondary pl-8 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        {/* Nav grid / search results */}
        <div className="overflow-y-auto flex-1 px-4 pb-2">
          {filtered ? (
            <div className="grid grid-cols-4 gap-2">
              {filtered.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
                    className={cn(
                      "flex flex-col items-center gap-1.5 rounded-xl p-2.5 border border-border text-center transition-colors",
                      isActive
                        ? "bg-primary border-primary text-white"
                        : "bg-secondary text-foreground"
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    <span className="text-[10px] font-semibold leading-tight">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div className="space-y-4">
              {SHEET_GROUPS.map((group) => {
                const visibleItems = group.items.filter(
                  (item) => !item.roles || (role && item.roles.includes(role))
                );
                if (visibleItems.length === 0) return null;

                return (
                  <div key={group.label}>
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-[.14em] text-muted-foreground">
                      {group.label}
                    </p>
                    <div className="grid grid-cols-4 gap-2">
                      {visibleItems.map((item) => {
                        const Icon = item.icon;
                        const isActive =
                          item.href === "/dashboard"
                            ? pathname === "/dashboard"
                            : pathname.startsWith(item.href);
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            onClick={onClose}
                            className={cn(
                              "flex flex-col items-center gap-1.5 rounded-xl p-2.5 border border-border text-center transition-colors",
                              isActive
                                ? "bg-primary border-primary text-white"
                                : "bg-secondary text-foreground"
                            )}
                          >
                            <Icon className="h-5 w-5 shrink-0" />
                            <span className="text-[10px] font-semibold leading-tight">{item.label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Sign out */}
        <div className="px-4 py-3 border-t border-border shrink-0">
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-xl text-sm font-semibold text-destructive hover:bg-destructive/10 transition-colors"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Sign out
          </button>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main MobileNav export
// ---------------------------------------------------------------------------

export function MobileNav() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);

  const { data: notifications } = useQuery<NotificationRead[]>({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
    refetchInterval: 30 * 1000,
  });
  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  return (
    <>
      <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />

      <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 lg:hidden">
        <div className="flex items-stretch justify-around h-16 px-1 pb-[env(safe-area-inset-bottom)]">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = tab.isMore
              ? moreOpen
              : tab.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(tab.href);

            if (tab.isMore) {
              return (
                <button
                  key="more"
                  onClick={() => setMoreOpen(true)}
                  className={cn(
                    "flex flex-col items-center justify-center gap-1 px-3 py-2 min-w-[56px] relative transition-colors",
                    isActive ? "text-primary" : "text-muted-foreground"
                  )}
                >
                  {isActive && (
                    <span className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-8 rounded-full bg-gold" />
                  )}
                  <Icon className={cn("h-5 w-5", isActive && "stroke-[2.5]")} />
                  <span className="text-[10px] font-semibold">{tab.label}</span>
                </button>
              );
            }

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 px-3 py-2 min-w-[56px] relative transition-colors",
                  isActive ? "text-primary" : "text-muted-foreground"
                )}
              >
                {isActive && (
                  <span className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-8 rounded-full bg-gold" />
                )}
                <div className="relative">
                  <Icon className={cn("h-5 w-5", isActive && "stroke-[2.5]")} />
                  {tab.isAlerts && unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-white">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-semibold">{tab.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
