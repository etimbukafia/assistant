/**
 * Tasks Hooks
 *
 * TanStack Query hooks for task operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchTasks,
    fetchTask,
    getTaskStats,
    approveTask,
    dismissTask,
    completeTask,
    startTask,
    updateTask,
    createTask,
    createManualTask,
    snoozeTask,
    Task,
    TasksResponse,
    TaskStats,
    UpdateTaskRequest,
    CreateTaskRequest,
    ManualTaskRequest,
} from '@/src/services/tasks';

export const tasksKeys = {
    all: ['tasks'] as const,
    lists: () => [...tasksKeys.all, 'list'] as const,
    list: (status?: string) => [...tasksKeys.lists(), status] as const,
    details: () => [...tasksKeys.all, 'detail'] as const,
    detail: (id: number) => [...tasksKeys.details(), id] as const,
    stats: () => [...tasksKeys.all, 'stats'] as const,
};

/**
 * Hook for fetching tasks with optional status filter
 */
export function useTasks(params?: { status?: string; limit?: number; offset?: number; enabled?: boolean }) {
    return useQuery({
        queryKey: tasksKeys.list(params?.status),
        queryFn: () => fetchTasks(params),
        enabled: params?.enabled ?? true,
    });
}

/**
 * Hook for fetching a single task
 */
export function useTask(taskId: number | null) {
    return useQuery({
        queryKey: tasksKeys.detail(taskId!),
        queryFn: () => fetchTask(taskId!),
        enabled: taskId !== null,
    });
}

/**
 * Hook for fetching task statistics
 */
export function useTaskStats() {
    return useQuery({
        queryKey: tasksKeys.stats(),
        queryFn: getTaskStats,
    });
}

/**
 * Hook for task mutations (approve, dismiss, complete, update, snooze)
 */
export function useTaskMutations() {
    const queryClient = useQueryClient();

    const invalidateTasks = () => {
        queryClient.invalidateQueries({ queryKey: tasksKeys.all });
    };

    const approveMutation = useMutation({
        mutationFn: approveTask,
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to approve task'),
    });

    const dismissMutation = useMutation({
        mutationFn: dismissTask,
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to dismiss task'),
    });

    const completeMutation = useMutation({
        mutationFn: completeTask,
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to complete task'),
    });

    const startMutation = useMutation({
        mutationFn: startTask,
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to start task'),
    });

    const updateMutation = useMutation({
        mutationFn: ({ taskId, data }: { taskId: number; data: UpdateTaskRequest }) =>
            updateTask(taskId, data),
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to update task'),
    });

    const snoozeMutation = useMutation({
        mutationFn: ({ taskId, snoozeUntil }: { taskId: number; snoozeUntil: string }) =>
            snoozeTask(taskId, snoozeUntil),
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to snooze task'),
    });

    const createMutation = useMutation({
        mutationFn: createTask,
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to create task'),
    });

    const createManualMutation = useMutation({
        mutationFn: createManualTask,
        onSuccess: invalidateTasks,
        onError: () => Alert.alert('Error', 'Failed to create task'),
    });

    return {
        // Approve
        approve: approveMutation.mutate,
        approveAsync: approveMutation.mutateAsync,
        isApproving: approveMutation.isPending,

        // Dismiss
        dismiss: dismissMutation.mutate,
        dismissAsync: dismissMutation.mutateAsync,
        isDismissing: dismissMutation.isPending,

        // Complete
        complete: completeMutation.mutate,
        completeAsync: completeMutation.mutateAsync,
        isCompleting: completeMutation.isPending,

        // Start (move to in_progress)
        start: startMutation.mutate,
        startAsync: startMutation.mutateAsync,
        isStarting: startMutation.isPending,

        // Update
        update: updateMutation.mutate,
        updateAsync: updateMutation.mutateAsync,
        isUpdating: updateMutation.isPending,

        // Snooze
        snooze: snoozeMutation.mutate,
        snoozeAsync: snoozeMutation.mutateAsync,
        isSnoozing: snoozeMutation.isPending,

        // Create
        create: createMutation.mutate,
        createAsync: createMutation.mutateAsync,
        isCreating: createMutation.isPending,

        // Create Manual
        createManual: createManualMutation.mutate,
        createManualAsync: createManualMutation.mutateAsync,
        isCreatingManual: createManualMutation.isPending,

        // Combined loading state
        isAnyPending:
            approveMutation.isPending ||
            dismissMutation.isPending ||
            completeMutation.isPending ||
            startMutation.isPending ||
            updateMutation.isPending ||
            snoozeMutation.isPending,
    };
}

/**
 * Combined hook for task data and mutations
 * Convenient for screens that need both
 */
export function useTasksWithMutations(params?: { status?: string }) {
    const query = useTasks(params);
    const mutations = useTaskMutations();

    return {
        ...query,
        ...mutations,
        tasks: query.data?.tasks || [],
        total: query.data?.total || 0,
    };
}
