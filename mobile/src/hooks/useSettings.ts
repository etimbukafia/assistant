/**
 * Settings Hook
 *
 * TanStack Query hook for user settings operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchSettings,
    updateSettings,
    UpdateSettingsRequest,
    UserSettings,
} from '@/src/services/settings';
import { useAuth } from '@/src/context/AuthContext';

export const settingsKeys = {
    all: ['settings'] as const,
    detail: () => [...settingsKeys.all] as const,
};

// Default settings for sandbox mode
const SANDBOX_SETTINGS: UserSettings = {
    auto_approve_tasks: false,
    enable_quick_reply_from_task: true,
    task_detection_instructions: '',
    digest_preferences: {
        enabled: true,
        morning_briefing: { enabled: true, time: '08:00' },
        end_of_day: { enabled: true, time: '18:00' },
        weekly_review: { enabled: true, day: 'monday', time: '09:00' },
    },
    calendar_preferences: {
        working_hours_start: '09:00',
        working_hours_end: '17:00',
        buffer_minutes: 15,
        auto_accept_meetings: false,
    },
    default_timezone: 'UTC',
};

/**
 * Hook for fetching and updating user settings
 */
export function useSettings() {
    const queryClient = useQueryClient();
    const { isSandbox } = useAuth();

    const query = useQuery({
        queryKey: settingsKeys.detail(),
        queryFn: fetchSettings,
        enabled: !isSandbox, // Disable API calls in sandbox mode
    });

    const updateMutation = useMutation({
        mutationFn: (updates: UpdateSettingsRequest) => updateSettings(updates),
        onSuccess: (data) => {
            queryClient.setQueryData(settingsKeys.detail(), data);
        },
        onError: () => {
            Alert.alert('Error', 'Failed to update settings. Please try again.');
        },
    });

    const updateSetting = <K extends keyof UpdateSettingsRequest>(
        key: K,
        value: UpdateSettingsRequest[K]
    ) => {
        updateMutation.mutate({ [key]: value } as UpdateSettingsRequest);
    };

    return {
        settings: isSandbox ? SANDBOX_SETTINGS : query.data,
        isLoading: isSandbox ? false : query.isLoading,
        error: isSandbox ? null : query.error,
        refetch: query.refetch,
        updateSetting,
        updateSettings: updateMutation.mutate,
        isUpdating: updateMutation.isPending,
        isSandbox,
    };
}
