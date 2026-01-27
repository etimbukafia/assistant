/**
 * Digests Hooks
 *
 * TanStack Query hooks for digest preferences.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchDigestPreferences,
    updateDigestPreferences,
    DigestPreferences,
} from '@/src/services/digests';
import { useAuth } from '@/src/context/AuthContext';

// Default digest preferences for sandbox mode
const SANDBOX_DIGEST_PREFERENCES: DigestPreferences = {
    enabled: true,
    morning_briefing: { enabled: true, time: '07:30' },
    end_of_day: { enabled: true, time: '17:00' },
    weekly_review: { enabled: false, time: '09:00', day: 'monday' },
    delivery_channel: 'email',
};

export const digestsKeys = {
    all: ['digests'] as const,
    preferences: () => [...digestsKeys.all, 'preferences'] as const,
};

/**
 * Hook for fetching digest preferences
 */
export function useDigestPreferences(options?: { enabled?: boolean }) {
    const { isSandbox } = useAuth();

    const query = useQuery({
        queryKey: digestsKeys.preferences(),
        queryFn: fetchDigestPreferences,
        enabled: (options?.enabled ?? true) && !isSandbox, // Disable API calls in sandbox mode
    });

    // Return sandbox data when in sandbox mode
    if (isSandbox) {
        return {
            ...query,
            data: SANDBOX_DIGEST_PREFERENCES,
            isLoading: false,
            error: null,
        };
    }

    return query;
}

/**
 * Hook for digest mutations
 */
export function useDigestMutations() {
    const queryClient = useQueryClient();

    const updateMutation = useMutation({
        mutationFn: (preferences: DigestPreferences) => updateDigestPreferences(preferences),
        onSuccess: (data) => {
            queryClient.setQueryData(digestsKeys.preferences(), data);
        },
        onError: () => Alert.alert('Error', 'Failed to save digest preferences'),
    });

    return {
        update: updateMutation.mutate,
        updateAsync: updateMutation.mutateAsync,
        isUpdating: updateMutation.isPending,
    };
}

/**
 * Combined hook for digest settings screen
 */
export function useDigestsWithMutations(options?: { enabled?: boolean }) {
    const query = useDigestPreferences(options);
    const mutations = useDigestMutations();

    return {
        // Data
        preferences: query.data,
        isLoading: query.isLoading,
        error: query.error,

        // Mutations
        update: mutations.update,
        isUpdating: mutations.isUpdating,

        // Refetch
        refetch: query.refetch,
    };
}
