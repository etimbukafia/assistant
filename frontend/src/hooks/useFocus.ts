import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    fetchDailyFocus,
    updateDailyFocus,
    fetchWeeklySummary,
    type DailyFocusUpdate,
} from "@/services/focus";

export const focusKeys = {
    all: ["focus"] as const,
    daily: (date?: string) => [...focusKeys.all, "daily", date ?? "today"] as const,
    weekly: () => [...focusKeys.all, "weekly"] as const,
};

export function useDailyFocus(date?: string) {
    return useQuery({
        queryKey: focusKeys.daily(date),
        queryFn: () => fetchDailyFocus(date),
    });
}

export function useWeeklySummary() {
    return useQuery({
        queryKey: focusKeys.weekly(),
        queryFn: fetchWeeklySummary,
    });
}

export function useFocusMutations() {
    const qc = useQueryClient();

    const invalidateAll = () => {
        qc.invalidateQueries({ queryKey: focusKeys.all });
    };

    const updateDaily = useMutation({
        mutationFn: (payload: DailyFocusUpdate) => updateDailyFocus(payload),
        onSuccess: invalidateAll,
    });

    return { updateDaily };
}
