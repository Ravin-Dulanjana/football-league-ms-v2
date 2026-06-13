"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
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
  Shirt,
  UserCheck,
  Users,
  UserCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  roles?: string[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
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

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading, role } = useCurrentUser();

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
          <p className="font-serif font-semibold text-sm text-foreground tracking-tight truncate">
            Wattala Football League
          </p>
        </div>
      </Link>

      {/* Nav groups */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-4">
        {NAV_GROUPS.map((group) => {
          const visibleItems = group.items.filter(
            (item) => !item.roles || (role && item.roles.includes(role))
          );
          if (visibleItems.length === 0) return null;

          return (
            <div key={group.label}>
              <p className="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-[.14em] text-muted-foreground">
                {group.label}
              </p>
              <div className="space-y-0.5">
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
                      className={cn(
                        "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-semibold transition-colors",
                        isActive
                          ? "bg-primary text-white"
                          : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
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
