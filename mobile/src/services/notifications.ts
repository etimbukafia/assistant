/**
 * Notification API Service
 */

import { api } from './api';

export interface AppNotification {
    id: number;
    title: string;
    body: string | null;
    category: string;
    priority: string;
    target_type: string | null;
    target_id: string | null;
    is_read: boolean;
    read_at: string | null;
    created_at: string;
}

export interface NotificationListResponse {
    notifications: AppNotification[];
    total: number;
    unread_count: number;
}

export interface UnreadCountResponse {
    unread_count: number;
}

export async function fetchNotifications(
    limit: number = 50,
    offset: number = 0
): Promise<NotificationListResponse> {
    const response = await api.get<NotificationListResponse>(
        `/notifications/?limit=${limit}&offset=${offset}`
    );
    return response.data;
}

export async function fetchUnreadCount(): Promise<number> {
    const response = await api.get<UnreadCountResponse>('/notifications/unread-count');
    return response.data.unread_count;
}

export async function markNotificationsRead(ids: number[]): Promise<void> {
    await api.post('/notifications/mark-read', { notification_ids: ids });
}

export async function markAllNotificationsRead(): Promise<void> {
    await api.post('/notifications/mark-all-read');
}

export async function registerDeviceToken(
    expo_push_token: string,
    device_name?: string,
    platform?: string
): Promise<void> {
    await api.post('/notifications/device-token', {
        expo_push_token,
        device_name,
        platform,
    });
}

export async function unregisterDeviceToken(expo_push_token: string): Promise<void> {
    await api.delete('/notifications/device-token', {
        data: { expo_push_token },
    });
}
