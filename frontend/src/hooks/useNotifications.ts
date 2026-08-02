"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import {
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationsRead,
} from "@/services/notifications";

const UNREAD_POLL_MS = 15_000;

function usePageVisible() {
  const [isVisible, setIsVisible] = useState<boolean>(() => {
    if (typeof document === "undefined") return true;
    return document.visibilityState === "visible";
  });

  useEffect(() => {
    if (typeof document === "undefined") return;
    const onVisibilityChange = () =>
      setIsVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () =>
      document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  return isVisible;
}

export const notificationKeys = {
  all: ["notifications"] as const,
  list: (limit: number, offset: number) =>
    [...notificationKeys.all, "list", limit, offset] as const,
  unreadCount: () => [...notificationKeys.all, "unread-count"] as const,
};

export function useUnreadCount() {
  const { session } = useAuth();
  const isVisible = usePageVisible();

  return useQuery({
    queryKey: notificationKeys.unreadCount(),
    queryFn: () => getUnreadCount(),
    enabled: !!session,
    staleTime: 5_000,
    refetchOnWindowFocus: true,
    refetchInterval: isVisible ? UNREAD_POLL_MS : false,
  });
}

export function useNotificationsFeed(limit = 20, offset = 0, enabled = true) {
  const { session } = useAuth();
  const isVisible = usePageVisible();

  return useQuery({
    queryKey: notificationKeys.list(limit, offset),
    queryFn: () => listNotifications(limit, offset),
    enabled: !!session && enabled,
    staleTime: 10_000,
    refetchOnWindowFocus: true,
    refetchInterval: enabled && isVisible ? 5_000 : false,
  });
}

export function useMarkNotificationsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markNotificationsRead,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
        queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount() }),
      ]);
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
        queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount() }),
      ]);
    },
  });
}
