/**
 * Preferences Hooks
 *
 * TanStack Query hooks for user preferences (PrincipalMemory) and decision patterns.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchPreferences,
    createPreference,
    updatePreference,
    deletePreference,
    fetchPatterns,
    fetchPatternSuggestions,
    actionPattern,
    PrincipalMemory,
    PrincipalMemoryListResponse,
    CreatePreferenceRequest,
    UpdatePreferenceRequest,
    DecisionPattern,
    DecisionPatternListResponse,
} from '@/src/services/memory';
import { useAuth } from '@/src/context/AuthContext';

// Demo preferences for sandbox mode
const SANDBOX_PREFERENCES: PrincipalMemory[] = [
    {
        id: 1,
        key: 'communication_style',
        value: 'I prefer concise, direct communication. Avoid unnecessary pleasantries.',
        context_type: 'communication',
        source: 'manual',
        created_at: '2024-01-15T10:00:00Z',
    },
    {
        id: 2,
        key: 'scheduling_preference',
        value: 'Never schedule meetings before 10am or after 4pm.',
        context_type: 'scheduling',
        source: 'approved_suggestion',
        created_at: '2024-01-10T14:30:00Z',
    },
];

export const preferencesKeys = {
    all: ['preferences'] as const,
    list: () => [...preferencesKeys.all, 'list'] as const,
    patterns: () => [...preferencesKeys.all, 'patterns'] as const,
    patternSuggestions: () => [...preferencesKeys.all, 'patterns', 'suggestions'] as const,
};

// ================================
// Preferences Queries
// ================================

/**
 * Hook for fetching user preferences
 */
export function usePreferences(options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: preferencesKeys.list(),
        queryFn: fetchPreferences,
        enabled: options?.enabled ?? true,
    });
}

/**
 * Hook for fetching approved decision patterns
 */
export function usePatterns(options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: preferencesKeys.patterns(),
        queryFn: fetchPatterns,
        enabled: options?.enabled ?? true,
    });
}

/**
 * Hook for fetching pattern suggestions (pending approval)
 */
export function usePatternSuggestions(options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: preferencesKeys.patternSuggestions(),
        queryFn: fetchPatternSuggestions,
        enabled: options?.enabled ?? true,
    });
}

// ================================
// Preferences Mutations
// ================================

/**
 * Hook for preference mutations (create, update, delete)
 */
export function usePreferenceMutations() {
    const queryClient = useQueryClient();

    const invalidatePreferences = () => {
        queryClient.invalidateQueries({ queryKey: preferencesKeys.list() });
    };

    const createMutation = useMutation({
        mutationFn: (request: CreatePreferenceRequest) => createPreference(request),
        onSuccess: invalidatePreferences,
        onError: () => Alert.alert('Error', 'Failed to add preference'),
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: UpdatePreferenceRequest }) =>
            updatePreference(id, data),
        onSuccess: invalidatePreferences,
        onError: () => Alert.alert('Error', 'Failed to update preference'),
    });

    const deleteMutation = useMutation({
        mutationFn: (preferenceId: number) => deletePreference(preferenceId),
        onSuccess: invalidatePreferences,
        onError: () => Alert.alert('Error', 'Failed to remove preference'),
    });

    return {
        // Create
        create: createMutation.mutate,
        createAsync: createMutation.mutateAsync,
        isCreating: createMutation.isPending,

        // Update
        update: updateMutation.mutate,
        updateAsync: updateMutation.mutateAsync,
        isUpdating: updateMutation.isPending,

        // Delete
        delete: deleteMutation.mutate,
        deleteAsync: deleteMutation.mutateAsync,
        isDeleting: deleteMutation.isPending,

        // Combined loading state
        isAnyPending: createMutation.isPending || updateMutation.isPending || deleteMutation.isPending,
    };
}

// ================================
// Pattern Mutations
// ================================

/**
 * Hook for pattern mutations (approve, reject, not_now)
 */
export function usePatternMutations() {
    const queryClient = useQueryClient();

    const invalidatePatterns = () => {
        queryClient.invalidateQueries({ queryKey: preferencesKeys.patterns() });
        queryClient.invalidateQueries({ queryKey: preferencesKeys.patternSuggestions() });
    };

    const actionMutation = useMutation({
        mutationFn: ({ patternId, action }: { patternId: number; action: 'approve' | 'reject' | 'not_now' }) =>
            actionPattern(patternId, action),
        onSuccess: invalidatePatterns,
        onError: () => Alert.alert('Error', 'Failed to process pattern'),
    });

    return {
        action: actionMutation.mutate,
        actionAsync: actionMutation.mutateAsync,
        isActioning: actionMutation.isPending,

        // Convenience methods
        approve: (patternId: number) => actionMutation.mutate({ patternId, action: 'approve' }),
        reject: (patternId: number) => actionMutation.mutate({ patternId, action: 'reject' }),
        notNow: (patternId: number) => actionMutation.mutate({ patternId, action: 'not_now' }),
    };
}

// ================================
// Combined Hooks
// ================================

/**
 * Combined hook for memory/preferences screen
 */
export function usePreferencesWithMutations(options?: { enabled?: boolean }) {
    const { isSandbox } = useAuth();
    const query = usePreferences({ ...options, enabled: options?.enabled !== false && !isSandbox });
    const mutations = usePreferenceMutations();

    return {
        // Data - use sandbox data when in sandbox mode
        preferences: isSandbox ? SANDBOX_PREFERENCES : (query.data?.preferences || []),
        total: isSandbox ? SANDBOX_PREFERENCES.length : (query.data?.total || 0),
        isLoading: isSandbox ? false : query.isLoading,
        error: isSandbox ? null : query.error,

        // Mutations
        create: mutations.create,
        isCreating: mutations.isCreating,
        update: mutations.update,
        isUpdating: mutations.isUpdating,
        delete: mutations.delete,
        isDeleting: mutations.isDeleting,
        isAnyPending: mutations.isAnyPending,

        // Sandbox indicator
        isSandbox,

        // Refetch
        refetch: query.refetch,
    };
}

/**
 * Combined hook for pattern suggestions
 */
export function usePatternSuggestionsWithMutations(options?: { enabled?: boolean }) {
    const query = usePatternSuggestions(options);
    const mutations = usePatternMutations();

    return {
        // Data
        suggestions: query.data?.patterns || [],
        total: query.data?.total || 0,
        isLoading: query.isLoading,
        error: query.error,

        // Actions
        approve: mutations.approve,
        reject: mutations.reject,
        notNow: mutations.notNow,
        isActioning: mutations.isActioning,

        // Refetch
        refetch: query.refetch,
    };
}
