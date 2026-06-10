"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  Building2,
  ChevronRight,
  ClipboardList,
  FileText,
  Home,
  Key,
  ListChecks,
  LogOut,
  ScrollText,
  Shield,
  Shirt,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Nav item definitions — role-aware
// ---------------------------------------------------------------------------

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  roles?: string[]; // undefined = visible to all roles
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: Home },
  { label: "Clubs", href: "/dashboard/clubs", icon: Building2 },
  { label: "Players", href: "/dashboard/players", icon: Shirt },
  { label: "Notifications", href: "/dashboard/notifications", icon: Bell },

  // Player + club admin
  {
    label: "Registrations",
    href: "/dashboard/registrations",
    icon: ClipboardList,
    roles: ["club_admin", "player"],
  },
  {
    label: "Releases",
    href: "/dashboard/releases",
    icon: FileText,
    roles: ["club_admin", "player"],
  },

  // League admin and above
  {
    label: "Seasons",
    href: "/dashboard/seasons",
    icon: ScrollText,
    roles: ["super_admin", "league_admin"],
  },
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
    roles: ["super_admin", "league_admin"],
  },
  {
    label: "Reports",
    href: "/dashboard/reports",
    icon: BarChart3,
    roles: ["super_admin", "league_admin", "club_admin"],
  },
];

// ---------------------------------------------------------------------------
// Sidebar component
// ---------------------------------------------------------------------------

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading, role } = useCurrentUser();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (role && item.roles.includes(role))
  );

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    toast.success("Signed out");
    router.push("/login");
    router.refresh();
  };

  return (
    <aside className="flex flex-col w-56 border-r border-border bg-card shrink-0 h-full">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 h-14 border-b border-border">
        <Image
          src="/logo.png"
          alt="Wattala Football League"
          width={32}
          height={32}
          className="rounded-full shrink-0"
        />
        <div className="leading-tight min-w-0">
          <p className="font-semibold text-xs text-foreground tracking-tight truncate">Wattala</p>
          <p className="text-xs text-muted-foreground truncate">Football League</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          // Active if the path starts with the href (but not for /dashboard root)
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
              {isActive && (
                <ChevronRight className="h-3 w-3 ml-auto text-primary shrink-0" />
              )}
            </Link>
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
            <p className="text-xs font-medium text-foreground truncate">{user?.email}</p>
            <p className="text-xs text-muted-foreground capitalize">
              {role?.replace(/_/g, " ")}
            </p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 w-full px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
