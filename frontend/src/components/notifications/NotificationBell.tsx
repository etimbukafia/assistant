"use client";

import { useEffect, useMemo, useState } from "react";
import { Bell, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationsRead,
  useNotificationsFeed,
  useUnreadCount,
} from "@/hooks/useNotifications";
import { NotificationItem } from "@/services/notifications";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const PAGE_SIZE = 20;

function formatNotificationTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function resolveTargetRoute(n: NotificationItem): string {
  switch (n.target_type) {
    case "task":
      return "/dashboard/focus";
    case "message":
      return "/dashboard/inbox";
    case "digest":
      return "/dashboard/focus";
    case "briefing":
      return "/dashboard/calendar";
    case "settings":
      return "/dashboard/settings";
    default:
      return "/dashboard";
  }
}

export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);

  const unreadQuery = useUnreadCount();
  const feedQuery = useNotificationsFeed(PAGE_SIZE, offset, open);
  const markReadMutation = useMarkNotificationsRead();
  const markAllMutation = useMarkAllNotificationsRead();

  const unreadCount = unreadQuery.data?.unread_count ?? 0;
  const total = feedQuery.data?.total ?? 0;

  useEffect(() => {
    if (!open) return;
    setOffset(0);
    setItems([]);
  }, [open]);

  useEffect(() => {
    if (!feedQuery.data) return;
    setItems((prev) => {
      const incoming = feedQuery.data?.notifications ?? [];
      if (offset === 0) return incoming;
      const seen = new Set(prev.map((n) => n.id));
      const merged = [...prev];
      for (const n of incoming) {
        if (!seen.has(n.id)) merged.push(n);
      }
      return merged;
    });
  }, [feedQuery.data, offset]);

  const hasMore = useMemo(() => items.length < total, [items.length, total]);

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
  };

  const handleMarkAllRead = async () => {
    await markAllMutation.mutateAsync();
  };

  const handleOpenNotification = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      try {
        await markReadMutation.mutateAsync({ notification_ids: [notification.id] });
      } catch {
        // No blocking error here; navigation still proceeds.
      }
    }
    setOpen(false);
    router.push(resolveTargetRoute(notification));
  };

  const handleLoadMore = () => {
    if (!hasMore || feedQuery.isFetching) return;
    setOffset((prev) => prev + PAGE_SIZE);
  };

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetTrigger asChild>
        <button
          type="button"
          className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          aria-label="Open notifications"
        >
          <Bell size={17} />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 min-w-[18px] h-[18px] px-1 rounded-full bg-primary text-white text-[10px] font-semibold leading-[18px] text-center">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[92vw] sm:max-w-[420px] p-0">
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-border">
          <div className="flex items-start justify-between gap-3">
            <div>
              <SheetTitle className="text-[17px] font-semibold">Notifications</SheetTitle>
              <SheetDescription className="mt-1 text-[12px]">
                Alerts and updates from Teeks.
              </SheetDescription>
            </div>
            <button
              type="button"
              onClick={handleMarkAllRead}
              disabled={markAllMutation.isPending || unreadCount === 0}
              className="rounded-md border border-border px-2.5 py-1.5 text-[11px] font-medium text-foreground hover:bg-muted/60 disabled:opacity-50"
            >
              Mark all read
            </button>
          </div>
        </SheetHeader>

        <div className="h-[calc(100vh-110px)] overflow-y-auto px-4 py-3 space-y-2">
          {feedQuery.isLoading && items.length === 0 && (
            <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
              <Loader2 size={14} className="animate-spin" />
              Loading notifications...
            </div>
          )}

          {!feedQuery.isLoading && items.length === 0 && (
            <div className="rounded-lg border border-border bg-card px-4 py-3 text-[12px] text-muted-foreground">
              No notifications yet.
            </div>
          )}

          {items.map((notification) => (
            <button
              key={notification.id}
              type="button"
              onClick={() => handleOpenNotification(notification)}
              className={cn(
                "w-full rounded-lg border px-3 py-2 text-left transition-colors",
                notification.is_read
                  ? "border-border bg-card hover:bg-muted/50"
                  : "border-primary/30 bg-primary/5 hover:bg-primary/10"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-[13px] font-semibold text-foreground leading-snug">
                  {notification.title}
                </p>
                <span className="text-[11px] text-muted-foreground shrink-0">
                  {formatNotificationTime(notification.created_at)}
                </span>
              </div>
              {notification.body && (
                <p className="mt-1 text-[12px] text-muted-foreground leading-snug">
                  {notification.body}
                </p>
              )}
            </button>
          ))}

          {hasMore && (
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={feedQuery.isFetching}
              className="w-full rounded-lg border border-border px-3 py-2 text-[12px] font-medium text-foreground hover:bg-muted/60 disabled:opacity-60"
            >
              {feedQuery.isFetching ? "Loading..." : "Load more"}
            </button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

