// This is a server component — no "use client" needed here.
// The sidebar and topbar are client components that import inside.
import { Sidebar } from "@/components/shared/Sidebar";
import { Topbar } from "@/components/shared/Topbar";
import { MobileNav } from "@/components/shared/MobileNav";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      {/* Desktop: sidebar + main content */}
      <div className="hidden lg:flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Topbar />
          <main className="flex-1 overflow-y-auto p-6 animate-fade-in">
            {children}
          </main>
        </div>
      </div>

      {/* Mobile: full-page with bottom nav */}
      <div className="lg:hidden flex flex-col min-h-screen">
        <Topbar mobile />
        <main className="flex-1 overflow-y-auto p-4 pb-20 animate-fade-in">
          {children}
        </main>
        <MobileNav />
      </div>
    </div>
  );
}
