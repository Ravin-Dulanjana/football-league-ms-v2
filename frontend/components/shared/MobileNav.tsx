"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Building2, Home, Shirt } from "lucide-react";
import { cn } from "@/lib/utils";

// Mobile bottom nav — 4 most important destinations.
// The full nav is accessible via the sidebar (hidden on mobile).

const MOBILE_NAV = [
  { label: "Home", href: "/dashboard", icon: Home },
  { label: "Clubs", href: "/dashboard/clubs", icon: Building2 },
  { label: "Players", href: "/dashboard/players", icon: Shirt },
  { label: "Alerts", href: "/dashboard/notifications", icon: Bell },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 lg:hidden">
      <div className="flex items-center justify-around h-16 px-2 safe-area-pb">
        {MOBILE_NAV.map((item) => {
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
                "flex flex-col items-center justify-center gap-1 rounded-md px-3 py-2 min-w-[60px] transition-colors",
                isActive ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className={cn("h-5 w-5", isActive && "stroke-[2.5]")} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
