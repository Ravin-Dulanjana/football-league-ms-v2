"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Search } from "lucide-react";
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

  const { data: notifications } = useQuery<NotificationRead[]>({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
    refetchInterval: 30 * 1000,
  });

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  const segments = pathname.split("/").filter(Boolean);
  const breadcrumbs = segments.map((seg, i) => ({
    label: seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    href: "/" + segments.slice(0, i + 1).join("/"),
    isLast: i === segments.length - 1,
  }));

  return (
    <header
      className={cn(
        "flex items-center justify-between border-b border-border bg-card/70 backdrop-blur px-4",
        mobile ? "h-14 lg:hidden" : "h-16 hidden lg:flex"
      )}
    >
      {mobile ? (
        <>
          <div className="flex items-center gap-2 min-w-0">
            <Image
              src="/logo.png"
              alt="Wattala Football League"
              width={28}
              height={28}
              className="rounded-full shrink-0"
            />
            <span className="font-semibold text-sm truncate">Wattala Football League</span>
          </div>
          <Link href="/dashboard/notifications" className="relative">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Button>
          </Link>
        </>
      ) : (
        <>
          {/* Desktop: breadcrumbs prefixed with "Wattala FL" */}
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-1.5 text-sm">
              <li className="flex items-center gap-1.5">
                <Link
                  href="/dashboard"
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  Wattala FL
                </Link>
              </li>
              {breadcrumbs.map((crumb) => (
                <li key={crumb.href} className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">/</span>
                  {crumb.isLast ? (
                    <span className="font-semibold text-foreground">{crumb.label}</span>
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

          {/* Right: search + bell */}
          <div className="flex items-center gap-2">
            <div className="relative hidden xl:flex items-center">
              <Search className="absolute left-3 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
              <input
                type="search"
                placeholder="Search…"
                className="h-9 w-56 rounded-[10px] border border-input bg-secondary pl-8 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <Link href="/dashboard/notifications" className="relative">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Bell className="h-4 w-4" />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </Button>
            </Link>
          </div>
        </>
      )}
    </header>
  );
}
