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

export const digestsKeys = {
    all: ['digests'] as const,
    preferences: () => [...digestsKeys.all, 'preferences'] as const,
};

/**
 * Hook for fetching digest preferences
 */
export function useDigestPreferences(options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: digestsKeys.preferences(),
        queryFn: fetchDigestPreferences,
        enabled: options?.enabled ?? true,
    });
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
