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
} from '@/src/services/settings';

export const settingsKeys = {
    all: ['settings'] as const,
    detail: () => [...settingsKeys.all] as const,
};

/**
 * Hook for fetching and updating user settings
 */
export function useSettings() {
    const queryClient = useQueryClient();

    const query = useQuery({
        queryKey: settingsKeys.detail(),
        queryFn: fetchSettings,
    });

    const updateMutation = useMutation({
        mutationFn: (updates: UpdateSettingsRequest) => updateSettings(updates),
        onMutate: async (updates) => {
            // Cancel any outgoing refetches
            await queryClient.cancelQueries({ queryKey: settingsKeys.detail() });

            // Snapshot previous value for rollback
            const previousSettings = queryClient.getQueryData(settingsKeys.detail());

            // Optimistically update cache
            if (previousSettings) {
                queryClient.setQueryData(settingsKeys.detail(), {
                    ...previousSettings,
                    ...updates,
                });
            }

            return { previousSettings };
        },
        onSuccess: (data) => {
            queryClient.setQueryData(settingsKeys.detail(), data);
        },
        onError: (_error, _updates, context) => {
            // Rollback to previous value on error
            if (context?.previousSettings) {
                queryClient.setQueryData(settingsKeys.detail(), context.previousSettings);
            }
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
        settings: query.data,
        isLoading: query.isLoading,
        error: query.error,
        refetch: query.refetch,
        updateSetting,
        updateSettings: updateMutation.mutate,
        isUpdating: updateMutation.isPending,
    };
}
