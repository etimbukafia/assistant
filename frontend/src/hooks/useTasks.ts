import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
    type TasksResponse,
    type UpdateTaskRequest,
    type CreateTaskRequest,
    type ManualTaskRequest,
} from "@/services/tasks";
import { messagesKeys } from "./useInbox";

export const tasksKeys = {
    all: ["tasks"] as const,
    lists: () => [...tasksKeys.all, "list"] as const,
    list: (status?: string) => [...tasksKeys.lists(), status] as const,
    details: () => [...tasksKeys.all, "detail"] as const,
    detail: (id: number) => [...tasksKeys.details(), id] as const,
    stats: () => [...tasksKeys.all, "stats"] as const,
};

export function useTasks(params?: { status?: string; limit?: number; offset?: number; enabled?: boolean }) {
    return useQuery({
        queryKey: tasksKeys.list(params?.status),
        queryFn: () => fetchTasks(params),
        enabled: params?.enabled ?? true,
    });
}

export function useTask(taskId: number | null) {
    return useQuery({
        queryKey: tasksKeys.detail(taskId!),
        queryFn: () => fetchTask(taskId!),
        enabled: taskId !== null,
    });
}

export function useTaskStats() {
    return useQuery({
        queryKey: tasksKeys.stats(),
        queryFn: getTaskStats,
    });
}

export function useTaskMutations() {
    const queryClient = useQueryClient();

    const invalidateTaskLists = () => {
        queryClient.invalidateQueries({ queryKey: tasksKeys.lists() });
        queryClient.invalidateQueries({ queryKey: tasksKeys.stats() });
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
    };

    const invalidateTaskDetail = (taskId: number) => {
        queryClient.invalidateQueries({ queryKey: tasksKeys.detail(taskId) });
    };

    const approveMutation = useMutation({
        mutationFn: approveTask,
        onSuccess: (_, taskId) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const dismissMutation = useMutation({
        mutationFn: dismissTask,
        onSuccess: (_, taskId) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const completeMutation = useMutation({
        mutationFn: completeTask,
        onSuccess: (_, taskId) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const startMutation = useMutation({
        mutationFn: startTask,
        onSuccess: (_, taskId) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const updateMutation = useMutation({
        mutationFn: ({ taskId, data }: { taskId: number; data: UpdateTaskRequest }) =>
            updateTask(taskId, data),
        onSuccess: (_, { taskId }) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const snoozeMutation = useMutation({
        mutationFn: ({ taskId, snoozeUntil }: { taskId: number; snoozeUntil: string }) =>
            snoozeTask(taskId, snoozeUntil),
        onSuccess: (_, { taskId }) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const createMutation = useMutation({
        mutationFn: createTask,
        onSuccess: invalidateTaskLists,
    });

    const createManualMutation = useMutation({
        mutationFn: createManualTask,
        onSuccess: invalidateTaskLists,
    });

    return {
        approve: approveMutation.mutate,
        isApproving: approveMutation.isPending,
        dismiss: dismissMutation.mutate,
        isDismissing: dismissMutation.isPending,
        complete: completeMutation.mutate,
        isCompleting: completeMutation.isPending,
        start: startMutation.mutate,
        isStarting: startMutation.isPending,
        update: updateMutation.mutate,
        isUpdating: updateMutation.isPending,
        snooze: snoozeMutation.mutate,
        isSnoozing: snoozeMutation.isPending,
        create: createMutation.mutate,
        isCreating: createMutation.isPending,
        createManual: createManualMutation.mutate,
        isCreatingManual: createManualMutation.isPending,
        isAnyPending:
            approveMutation.isPending ||
            dismissMutation.isPending ||
            completeMutation.isPending ||
            startMutation.isPending ||
            updateMutation.isPending ||
            snoozeMutation.isPending,
    };
}

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
