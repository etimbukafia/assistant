/**
 * Settings API Service
 *
 * Functions for user settings operations (GET/PUT).
 */

import { api } from './api';

// ================================
// Types
// ================================

export interface ReminderPreferences {
    enabled: boolean;
    default_time?: string;
    channels?: string[];
    [key: string]: any;
}

export interface UserSettings {
    id: number;
    user_email: string;
    auto_approve_tasks: boolean;
    task_detection_instructions: string | null;
    reminder_preferences: ReminderPreferences;
    enable_quick_reply_from_task: boolean;
    // Subscription fields
    subscription_tier: 'trial' | 'pro';
    subscription_status: string | null;
    trial_ends_at: string | null;
    is_active: boolean;
    days_remaining: number;
    // Integration status
    initial_sync_completed: boolean;
    gmail_connected: boolean;
    calendar_connected: boolean;
    created_at: string;
    updated_at: string;
}

export interface UpdateSettingsRequest {
    auto_approve_tasks?: boolean;
    task_detection_instructions?: string | null;
    reminder_preferences?: ReminderPreferences;
    enable_quick_reply_from_task?: boolean;
}

// ================================
// Settings API
// ================================

/**
 * Fetch current user settings
 */
export async function fetchSettings(): Promise<UserSettings> {
    const response = await api.get<UserSettings>('/settings/');
    return response.data;
}

/**
 * Update user settings
 */
export async function updateSettings(request: UpdateSettingsRequest): Promise<UserSettings> {
    const response = await api.put<UserSettings>('/settings/', request);
    return response.data;
}
