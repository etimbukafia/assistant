import { api } from "@/services/api";

export interface NotificationItem {
  id: number;
  title: string;
  body?: string | null;
  category: string;
  priority: string;
  target_type?: string | null;
  target_id?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NotificationItem[];
  total: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface MarkReadRequest {
  notification_ids: number[];
}

export async function listNotifications(
  limit = 20,
  offset = 0
): Promise<NotificationListResponse> {
  const response = await api.get<NotificationListResponse>("/notifications/", {
    params: { limit, offset },
  });
  return response.data;
}

export async function getUnreadCount(): Promise<UnreadCountResponse> {
  const response = await api.get<UnreadCountResponse>(
    "/notifications/unread-count"
  );
  return response.data;
}

export async function markNotificationsRead(
  request: MarkReadRequest
): Promise<{ status: string }> {
  const response = await api.post<{ status: string }>(
    "/notifications/mark-read",
    request
  );
  return response.data;
}

export async function markAllNotificationsRead(): Promise<{ status: string }> {
  const response = await api.post<{ status: string }>(
    "/notifications/mark-all-read",
    {}
  );
  return response.data;
}

