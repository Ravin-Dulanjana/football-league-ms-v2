import { cn } from "@/lib/utils";

// Semantic color mapping — same color for same status everywhere in the app.
// These map to the status.* tokens defined in tailwind.config.ts.
const STATUS_STYLES: Record<string, string> = {
  // Club status
  active: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  inactive: "bg-gray-100 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400",
  suspended: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",

  // Season status
  draft: "bg-gray-100 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400",
  open: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  closed: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  archived: "bg-gray-200 text-gray-500 dark:bg-gray-800 dark:text-gray-500",

  // Club season profile status
  submitted: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  resubmitted: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400",
  reviewed: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  returned: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",

  // Registration / release status
  pending_player_confirmation: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  accepted: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  cancelled: "bg-gray-100 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400",
  confirmed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  released: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",

  // Player status
  pending_claim: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",

  // Unlock request status
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",

  // Account status
  locked: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  unlocked: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
};

// Human-readable label overrides — converts snake_case API values to display text.
const STATUS_LABELS: Record<string, string> = {
  pending_player_confirmation: "Pending Player",
  pending_claim: "Unclaimed",
  super_admin: "Super Admin",
  league_admin: "League Admin",
  club_admin: "Club Admin",
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400";
  const label = STATUS_LABELS[status] ?? status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-black/5 dark:ring-white/5",
        style,
        className
      )}
    >
      {label}
    </span>
  );
}
