import { api } from './api';

export interface ReminderPreferences {
    enabled: boolean;
    default_time?: string;
    channels?: string[];
    [key: string]: any;
}

export interface NotificationPreferences {
    push_enabled: boolean;
    push_urgent_tasks: boolean;
    push_deadlines: boolean;
    push_digests: boolean;
    push_briefings: boolean;
    [key: string]: any;
}

export interface UserSettings {
    id: number;
    user_email: string;
    notification_email?: string | null;
    auto_approve_tasks: boolean;
    task_detection_instructions: string | null;
    reminder_preferences: ReminderPreferences;
    notification_preferences: NotificationPreferences;
    enable_quick_reply_from_task: boolean;
    subscription_tier: 'trial' | 'pro';
    subscription_status: string | null;
    trial_ends_at: string | null;
    is_active: boolean;
    days_remaining: number;
    assistant_name: string;
    onboarding_completed: boolean;
    initial_sync_completed: boolean;
    initial_sync_failed: boolean;
    gmail_connected: boolean;
    calendar_connected: boolean;
    default_calendar_id?: string | null;
    auto_briefing_enabled?: boolean;
    briefing_hours_before?: number;
    created_at: string;
    updated_at: string;
}

export interface UpdateSettingsRequest {
    auto_approve_tasks?: boolean;
    task_detection_instructions?: string | null;
    reminder_preferences?: ReminderPreferences;
    notification_preferences?: NotificationPreferences;
    enable_quick_reply_from_task?: boolean;
    assistant_name?: string;
    notification_email?: string | null;
    default_calendar_id?: string | null;
    auto_briefing_enabled?: boolean;
    briefing_hours_before?: number;
}

export async function fetchSettings(accessToken?: string): Promise<UserSettings> {
    const config = accessToken
        ? { headers: { Authorization: `Bearer ${accessToken}` } }
        : {};
    const response = await api.get<UserSettings>('/settings/', config);
    return response.data;
}

export async function updateSettings(request: UpdateSettingsRequest): Promise<UserSettings> {
    const response = await api.put<UserSettings>('/settings/', request);
    return response.data;
}
