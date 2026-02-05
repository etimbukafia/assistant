/**
 * Notifications Hook
 *
 * TanStack Query hooks for notification feed and unread count.
 * Handles push token registration on mount.
 */

import { useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as Notifications from 'expo-notifications';
import { useRouter } from 'expo-router';
import { useAuth } from '@/src/context/AuthContext';
import {
    fetchNotifications,
    fetchUnreadCount,
    markNotificationsRead,
    markAllNotificationsRead,
    registerDeviceToken,
} from '@/src/services/notifications';
import { getExpoPushToken, getDeviceInfo } from '@/src/utils/pushNotifications';

export const notificationKeys = {
    all: ['notifications'] as const,
    list: () => [...notificationKeys.all, 'list'] as const,
    unreadCount: () => [...notificationKeys.all, 'unread-count'] as const,
};

/**
 * Hook for unread notification count (bell icon badge).
 * Polls every 30 seconds.
 */
export function useUnreadCount() {
    const { isSandbox } = useAuth();

    const query = useQuery({
        queryKey: notificationKeys.unreadCount(),
        queryFn: fetchUnreadCount,
        enabled: !isSandbox,
        refetchInterval: 30_000,
        staleTime: 15_000,
    });

    return {
        unreadCount: isSandbox ? 0 : (query.data ?? 0),
        isLoading: isSandbox ? false : query.isLoading,
    };
}

/**
 * Hook for notification feed (list of notifications).
 */
export function useNotificationFeed() {
    const { isSandbox } = useAuth();
    const queryClient = useQueryClient();

    const query = useQuery({
        queryKey: notificationKeys.list(),
        queryFn: () => fetchNotifications(50, 0),
        enabled: !isSandbox,
    });

    const markReadMutation = useMutation({
        mutationFn: (ids: number[]) => markNotificationsRead(ids),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: notificationKeys.all });
        },
    });

    const markAllReadMutation = useMutation({
        mutationFn: () => markAllNotificationsRead(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: notificationKeys.all });
        },
    });

    return {
        notifications: isSandbox ? [] : (query.data?.notifications ?? []),
        total: isSandbox ? 0 : (query.data?.total ?? 0),
        unreadCount: isSandbox ? 0 : (query.data?.unread_count ?? 0),
        isLoading: isSandbox ? false : query.isLoading,
        refetch: query.refetch,
        markRead: markReadMutation.mutate,
        markAllRead: markAllReadMutation.mutate,
    };
}

/**
 * Hook for registering push token and handling incoming notifications.
 * Call once at the app root level.
 */
export function usePushNotificationSetup() {
    const { isAuthenticated, isSandbox } = useAuth();
    const router = useRouter();
    const queryClient = useQueryClient();
    const responseListener = useRef<Notifications.Subscription>();

    useEffect(() => {
        if (!isAuthenticated || isSandbox) return;

        // Register push token
        (async () => {
            const token = await getExpoPushToken();
            if (token) {
                const { device_name, platform } = getDeviceInfo();
                try {
                    await registerDeviceToken(token, device_name, platform);
                } catch (error) {
                    console.error('Failed to register push token:', error);
                }
            }
        })();

        // Handle notification tap (when user taps a push notification)
        responseListener.current = Notifications.addNotificationResponseReceivedListener(
            (response) => {
                const data = response.notification.request.content.data;
                queryClient.invalidateQueries({ queryKey: notificationKeys.all });

                if (data?.target_type === 'task') {
                    router.push('/(tabs)/focus' as any);
                } else if (data?.target_type === 'digest') {
                    router.push('/(tabs)' as any);
                } else if (data?.target_type === 'briefing') {
                    router.push('/(tabs)/calendar' as any);
                } else if (data?.target_type === 'settings') {
                    router.push('/settings/subscription' as any);
                }
            }
        );

        return () => {
            if (responseListener.current) {
                Notifications.removeNotificationSubscription(responseListener.current);
            }
        };
    }, [isAuthenticated, isSandbox]);
}
