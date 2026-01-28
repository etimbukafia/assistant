/**
 * Notification Feed Screen
 *
 * Shows all in-app notifications with unread indicators.
 * Accessed by tapping the bell icon in the header.
 */

import React, { useCallback } from 'react';
import {
    StyleSheet, View, FlatList, TouchableOpacity,
    ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useNotificationFeed } from '@/src/hooks/useNotifications';
import type { AppNotification } from '@/src/services/notifications';

const CATEGORY_ICONS: Record<string, string> = {
    task_urgent: 'alert-circle',
    task_deadline: 'time',
    digest_ready: 'mail',
    briefing_ready: 'calendar',
    reminder_due: 'alarm',
    system: 'information-circle',
};

const CATEGORY_COLORS: Record<string, string> = {
    task_urgent: Colors.error,
    task_deadline: Colors.accentSecondary,
    digest_ready: Colors.accentPrecision,
    briefing_ready: Colors.accentPrecision,
    reminder_due: Colors.accentSecondary,
    system: Colors.textSecondary,
};

function formatTimeAgo(dateString: string): string {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

function NotificationItem({
    item, onPress,
}: {
    item: AppNotification;
    onPress: (n: AppNotification) => void;
}) {
    const iconName = CATEGORY_ICONS[item.category] || 'notifications';
    const iconColor = CATEGORY_COLORS[item.category] || Colors.textSecondary;

    return (
        <TouchableOpacity
            style={[styles.notificationRow, !item.is_read && styles.unreadRow]}
            onPress={() => onPress(item)}
        >
            <View style={[styles.iconContainer, { backgroundColor: iconColor + '15' }]}>
                <Ionicons name={iconName as any} size={20} color={iconColor} />
            </View>
            <View style={styles.textContainer}>
                <DonnaText style={[styles.title, !item.is_read && styles.unreadTitle]} numberOfLines={2}>
                    {item.title}
                </DonnaText>
                {item.body && (
                    <DonnaText style={styles.body} numberOfLines={2}>
                        {item.body}
                    </DonnaText>
                )}
                <DonnaText style={styles.time}>{formatTimeAgo(item.created_at)}</DonnaText>
            </View>
            {!item.is_read && <View style={styles.unreadDot} />}
        </TouchableOpacity>
    );
}

export default function NotificationsScreen() {
    const router = useRouter();
    const {
        notifications, isLoading, refetch,
        markRead, markAllRead, unreadCount,
    } = useNotificationFeed();

    const handleNotificationPress = useCallback((notification: AppNotification) => {
        if (!notification.is_read) {
            markRead([notification.id]);
        }

        if (notification.target_type === 'task') {
            router.push('/(tabs)/focus' as any);
        } else if (notification.target_type === 'digest') {
            router.push('/(tabs)' as any);
        } else if (notification.target_type === 'briefing') {
            router.push('/(tabs)/calendar' as any);
        }
    }, [markRead, router]);

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Notifications</DonnaText>
                {unreadCount > 0 ? (
                    <TouchableOpacity onPress={() => markAllRead()}>
                        <DonnaText style={styles.markAllRead}>Mark all read</DonnaText>
                    </TouchableOpacity>
                ) : (
                    <View style={styles.headerPlaceholder} />
                )}
            </View>

            {isLoading ? (
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                </View>
            ) : (
                <FlatList
                    data={notifications}
                    keyExtractor={(item) => item.id.toString()}
                    renderItem={({ item }) => (
                        <NotificationItem item={item} onPress={handleNotificationPress} />
                    )}
                    refreshControl={
                        <RefreshControl refreshing={false} onRefresh={refetch} />
                    }
                    ListEmptyComponent={
                        <View style={styles.emptyContainer}>
                            <Ionicons name="notifications-off-outline" size={48} color={Colors.textMuted} />
                            <DonnaText style={styles.emptyText}>No notifications yet</DonnaText>
                        </View>
                    }
                    contentContainerStyle={notifications.length === 0 ? styles.emptyList : undefined}
                />
            )}
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: Colors.bgBase },
    loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    backButton: { padding: Spacing.xs },
    headerTitle: { fontSize: 17, fontWeight: '600', color: Colors.textPrimary },
    headerPlaceholder: { width: 80 },
    markAllRead: { fontSize: 13, color: Colors.accentSecondary, fontWeight: '500' },
    notificationRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    unreadRow: { backgroundColor: 'rgba(217, 119, 69, 0.04)' },
    iconContainer: {
        width: 36,
        height: 36,
        borderRadius: 10,
        justifyContent: 'center',
        alignItems: 'center',
    },
    textContainer: { flex: 1 },
    title: { fontSize: 14, fontWeight: '400', color: Colors.textPrimary },
    unreadTitle: { fontWeight: '600' },
    body: { fontSize: 13, color: Colors.textMuted, marginTop: 2 },
    time: { fontSize: 11, color: Colors.textMuted, marginTop: 4 },
    unreadDot: {
        width: 8,
        height: 8,
        borderRadius: 4,
        backgroundColor: Colors.accentSecondary,
    },
    emptyContainer: { alignItems: 'center', gap: Spacing.md, paddingTop: 80 },
    emptyText: { fontSize: 15, color: Colors.textMuted },
    emptyList: { flex: 1 },
});
