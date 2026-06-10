"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bell, BellOff, CheckCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader, EmptyState, ErrorState } from "@/components/shared/DataTable";
import { notificationsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { NotificationPreferenceRead, NotificationRead } from "@/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Notification item
// ---------------------------------------------------------------------------

function NotificationItem({
  notification,
  onMarkRead,
}: {
  notification: NotificationRead;
  onMarkRead: (id: number) => void;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 p-4 rounded-lg border transition-colors",
        notification.is_read
          ? "border-border bg-card"
          : "border-primary/20 bg-primary/5"
      )}
    >
      <div className="mt-0.5">
        {notification.is_read ? (
          <Bell className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Bell className="h-4 w-4 text-primary" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm", !notification.is_read && "font-medium")}>
          {notification.message}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {notification.event_type.replace(/\./g, " › ")} ·{" "}
          {formatRelative(notification.created_at)}
        </p>
      </div>
      {!notification.is_read && (
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 h-7 text-xs"
          onClick={() => onMarkRead(notification.id)}
        >
          Mark read
        </Button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

function PreferencesSection() {
  const queryClient = useQueryClient();

  const { data: prefs, isLoading } = useQuery<NotificationPreferenceRead[]>({
    queryKey: ["notification-preferences"],
    queryFn: notificationsApi.getPreferences,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      eventType,
      emailEnabled,
      inAppEnabled,
    }: {
      eventType: string;
      emailEnabled: boolean;
      inAppEnabled: boolean;
    }) =>
      notificationsApi.updatePreference(eventType, {
        email_enabled: emailEnabled,
        in_app_enabled: inAppEnabled,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-preferences"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  }

  if (!prefs?.length) {
    return (
      <p className="text-sm text-muted-foreground">No notification preferences configured.</p>
    );
  }

  return (
    <div className="space-y-3">
      {prefs.map((pref) => (
        <div
          key={pref.event_type}
          className="flex items-center justify-between py-3 border-b border-border last:border-0"
        >
          <div>
            <p className="text-sm font-medium capitalize">
              {pref.event_type.replace(/\./g, " › ")}
            </p>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Switch
                id={`email-${pref.event_type}`}
                checked={pref.email_enabled}
                onCheckedChange={(checked) =>
                  updateMutation.mutate({
                    eventType: pref.event_type,
                    emailEnabled: checked,
                    inAppEnabled: pref.in_app_enabled,
                  })
                }
              />
              <Label htmlFor={`email-${pref.event_type}`} className="text-xs text-muted-foreground">
                Email
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id={`app-${pref.event_type}`}
                checked={pref.in_app_enabled}
                onCheckedChange={(checked) =>
                  updateMutation.mutate({
                    eventType: pref.event_type,
                    emailEnabled: pref.email_enabled,
                    inAppEnabled: checked,
                  })
                }
              />
              <Label htmlFor={`app-${pref.event_type}`} className="text-xs text-muted-foreground">
                In-app
              </Label>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function NotificationsPage() {
  const queryClient = useQueryClient();

  const { data: notifications, isLoading, error, refetch } = useQuery<NotificationRead[]>({
    queryKey: ["notifications"],
    queryFn: notificationsApi.list,
    refetchInterval: 30 * 1000,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
    onError: (err: Error) => toast.error(err.message),
  });

  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("All notifications marked as read");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  return (
    <div className="max-w-2xl space-y-8">
      <PageHeader
        title="Notifications"
        description={unreadCount > 0 ? `${unreadCount} unread` : "All caught up"}
        action={
          unreadCount > 0 ? (
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => markAllReadMutation.mutate()}
              disabled={markAllReadMutation.isPending}
            >
              <CheckCheck className="h-4 w-4" />
              Mark all read
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !notifications?.length ? (
        <EmptyState
          title="No notifications"
          description="You're all caught up — nothing new to see"
          icon={<BellOff className="h-6 w-6" />}
        />
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <NotificationItem
              key={n.id}
              notification={n}
              onMarkRead={(id) => markReadMutation.mutate(id)}
            />
          ))}
        </div>
      )}

      <Separator />

      <div>
        <h2 className="text-base font-semibold mb-4">Notification preferences</h2>
        <PreferencesSection />
      </div>
    </div>
  );
}
