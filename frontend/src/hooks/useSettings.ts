import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    fetchSettings,
    updateSettings,
    UpdateSettingsRequest,
} from '@/services/settings';
import { useAuth } from '@/context/AuthContext';

export const settingsKeys = {
    all: ['settings'] as const,
    detail: () => [...settingsKeys.all] as const,
};

export function useSettings() {
    const queryClient = useQueryClient();
    const { session } = useAuth();

    const query = useQuery({
        queryKey: settingsKeys.detail(),
        queryFn: () => fetchSettings(),
        enabled: !!session,
    });

    const updateMutation = useMutation({
        mutationFn: (updates: UpdateSettingsRequest) => updateSettings(updates),
        onMutate: async (updates) => {
            await queryClient.cancelQueries({ queryKey: settingsKeys.detail() });
            const previousSettings = queryClient.getQueryData(settingsKeys.detail());

            if (previousSettings) {
                queryClient.setQueryData(settingsKeys.detail(), {
                    ...(previousSettings as any),
                    ...updates,
                });
            }

            return { previousSettings };
        },
        onSuccess: (data) => {
            queryClient.setQueryData(settingsKeys.detail(), data);
        },
        onError: (_error, _updates, context) => {
            if (context?.previousSettings) {
                queryClient.setQueryData(settingsKeys.detail(), context.previousSettings);
            }
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
