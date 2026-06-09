"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { notificationsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { NotificationRead } from "@/types";

interface TopbarProps {
  mobile?: boolean;
}

export function Topbar({ mobile = false }: TopbarProps) {
  const pathname = usePathname();

  // Count unread notifications for the badge
  const { data: notifications } = useQuery<NotificationRead[]>({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
    refetchInterval: 30 * 1000, // poll every 30s
  });

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  // Build breadcrumb from path segments
  const segments = pathname.split("/").filter(Boolean);
  const breadcrumbs = segments.map((seg, i) => ({
    label: seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    href: "/" + segments.slice(0, i + 1).join("/"),
    isLast: i === segments.length - 1,
  }));

  return (
    <header
      className={cn(
        "flex items-center justify-between border-b border-border bg-card px-4",
        mobile ? "h-14 lg:hidden" : "h-14 hidden lg:flex"
      )}
    >
      {/* Mobile: brand + hamburger */}
      {mobile ? (
        <>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-md bg-primary text-primary-foreground text-xs font-bold">
              FL
            </div>
            <span className="font-semibold text-sm">Football League</span>
          </div>
          <Link href="/dashboard/notifications" className="relative">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Button>
          </Link>
        </>
      ) : (
        <>
          {/* Desktop: breadcrumbs */}
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-1.5 text-sm">
              {breadcrumbs.map((crumb, i) => (
                <li key={crumb.href} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-muted-foreground">/</span>}
                  {crumb.isLast ? (
                    <span className="font-medium text-foreground">{crumb.label}</span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </li>
              ))}
            </ol>
          </nav>

          {/* Desktop: notification bell */}
          <Link href="/dashboard/notifications" className="relative">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Button>
          </Link>
        </>
      )}
    </header>
  );
}
