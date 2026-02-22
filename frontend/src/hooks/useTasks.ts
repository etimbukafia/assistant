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
import type { Task } from "@/services/messages";

export const tasksKeys = {
    all: ["tasks"] as const,
    lists: () => [...tasksKeys.all, "list"] as const,
    list: (status?: string) => [...tasksKeys.lists(), status] as const,
    details: () => [...tasksKeys.all, "detail"] as const,
    detail: (id: number) => [...tasksKeys.details(), id] as const,
    stats: () => [...tasksKeys.all, "stats"] as const,
};

export function useTasks(params?: {
    status?: string;
    priorities?: string;
    limit?: number;
    offset?: number;
    sort?: "priority" | "created_at";
    enabled?: boolean;
}) {
    return useQuery({
        queryKey: [
            ...tasksKeys.list(params?.status),
            params?.priorities ?? null,
            params?.sort ?? null,
            params?.limit ?? null,
            params?.offset ?? null,
        ],
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

    const updateTaskInCache = (taskId: number, updater: (task: Task) => Task) => {
        queryClient.setQueriesData({ queryKey: tasksKeys.all }, (old: unknown) => {
            if (!old) return old;
            // Handle infinite queries
            if (typeof old === "object" && old && "pages" in old) {
                const data = old as { pages: Array<{ tasks: Task[] }>; pageParams: unknown[] };
                return {
                    ...data,
                    pages: data.pages.map((page) => ({
                        ...page,
                        tasks: page.tasks.map((task) => (task.id === taskId ? updater(task) : task)),
                    })),
                };
            }
            // Handle normal list queries
            if (typeof old === "object" && old && "tasks" in old) {
                const data = old as TasksResponse;
                return {
                    ...data,
                    tasks: data.tasks.map((task) => (task.id === taskId ? updater(task) : task)),
                };
            }
            return old;
        });
    };

    const invalidateTaskLists = () => {
        queryClient.invalidateQueries({ queryKey: tasksKeys.lists() });
        queryClient.invalidateQueries({ queryKey: tasksKeys.stats() });
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
        queryClient.invalidateQueries({ queryKey: ["thread-detail"] });
    };

    const invalidateTaskDetail = (taskId: number) => {
        queryClient.invalidateQueries({ queryKey: tasksKeys.detail(taskId) });
    };

    const approveMutation = useMutation({
        mutationFn: approveTask,
        onMutate: async (taskId) => {
            await queryClient.cancelQueries({ queryKey: tasksKeys.all });
            const previous = queryClient.getQueriesData({ queryKey: tasksKeys.all });
            updateTaskInCache(taskId, (task) => ({
                ...task,
                status: "approved",
                approved_at: new Date().toISOString(),
            }));
            return { previous };
        },
        onError: (_error, _taskId, context) => {
            context?.previous?.forEach(([key, data]) => queryClient.setQueryData(key, data));
            queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
            queryClient.invalidateQueries({ queryKey: ["thread-detail"] });
        },
        onSuccess: (_, taskId) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const dismissMutation = useMutation({
        mutationFn: dismissTask,
        onMutate: async (taskId) => {
            await queryClient.cancelQueries({ queryKey: tasksKeys.all });
            const previous = queryClient.getQueriesData({ queryKey: tasksKeys.all });
            updateTaskInCache(taskId, (task) => ({
                ...task,
                status: "dismissed",
                dismissed_at: new Date().toISOString(),
            }));
            return { previous };
        },
        onError: (_error, _taskId, context) => {
            context?.previous?.forEach(([key, data]) => queryClient.setQueryData(key, data));
            queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
            queryClient.invalidateQueries({ queryKey: ["thread-detail"] });
        },
        onSuccess: (_, taskId) => {
            invalidateTaskLists();
            invalidateTaskDetail(taskId);
        },
    });

    const completeMutation = useMutation({
        mutationFn: completeTask,
        onMutate: async (taskId) => {
            await queryClient.cancelQueries({ queryKey: tasksKeys.all });
            const previous = queryClient.getQueriesData({ queryKey: tasksKeys.all });
            updateTaskInCache(taskId, (task) => ({
                ...task,
                status: "completed",
                completed_at: new Date().toISOString(),
            }));
            return { previous };
        },
        onError: (_error, _taskId, context) => {
            context?.previous?.forEach(([key, data]) => queryClient.setQueryData(key, data));
            queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
            queryClient.invalidateQueries({ queryKey: ["thread-detail"] });
        },
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
        onMutate: async ({ taskId, data }) => {
            await queryClient.cancelQueries({ queryKey: tasksKeys.all });
            const previous = queryClient.getQueriesData({ queryKey: tasksKeys.all });
            updateTaskInCache(taskId, (task) => ({
                ...task,
                ...(data.title !== undefined && { title: data.title }),
                ...(data.description !== undefined && { description: data.description }),
                ...(data.priority !== undefined && { priority: data.priority }),
                ...(data.deadline !== undefined && { deadline_at: data.deadline ?? undefined }),
                ...(data.clear_deadline && { deadline_at: undefined }),
            }));
            return { previous };
        },
        onError: (_error, _vars, context) => {
            context?.previous?.forEach(([key, data]) => queryClient.setQueryData(key, data));
        },
        onSuccess: (updatedTask, { taskId }) => {
            // Sync cache with server truth
            updateTaskInCache(taskId, () => updatedTask);
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
        onMutate: async (vars) => {
            await queryClient.cancelQueries({ queryKey: tasksKeys.all });
            const previous = queryClient.getQueriesData({ queryKey: tasksKeys.all });

            // Build an optimistic task with a temporary negative id
            const optimisticTask: Task = {
                id: -Date.now(),
                message_id: 0,
                title: vars.title,
                description: vars.description,
                type: "other",
                task_signal: "explicit",
                priority: (vars.priority ?? "normal") as Task["priority"],
                status: (vars.status ?? "approved") as Task["status"],
                approved_at: new Date().toISOString(),
                deadline_at: vars.deadline ?? undefined,
                deadline_source: vars.deadline ? "explicit" : undefined,
                deadline_user_confirmed: !!vars.deadline,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            };

            // Prepend to every cached page list
            queryClient.setQueriesData({ queryKey: tasksKeys.all }, (old: unknown) => {
                if (!old) return old;
                if (typeof old === "object" && old && "pages" in old) {
                    const data = old as { pages: Array<{ tasks: Task[]; total?: number }>; pageParams: unknown[] };
                    return {
                        ...data,
                        pages: data.pages.map((page, i) =>
                            i === 0
                                ? { ...page, tasks: [optimisticTask, ...page.tasks], total: (page.total ?? 0) + 1 }
                                : page
                        ),
                    };
                }
                if (typeof old === "object" && old && "tasks" in old) {
                    const data = old as TasksResponse;
                    return { ...data, tasks: [optimisticTask, ...data.tasks], total: data.total + 1 };
                }
                return old;
            });

            return { previous };
        },
        onError: (_error, _vars, context) => {
            context?.previous?.forEach(([key, data]) => queryClient.setQueryData(key, data));
        },
        onSuccess: invalidateTaskLists,
    });

    return {
        approve: approveMutation,
        dismiss: dismissMutation,
        complete: completeMutation,
        start: startMutation,
        update: updateMutation,
        snooze: snoozeMutation,
        create: createMutation,
        createManual: createManualMutation,
        isAnyPending:
            approveMutation.isPending ||
            dismissMutation.isPending ||
            completeMutation.isPending ||
            startMutation.isPending ||
            updateMutation.isPending ||
            snoozeMutation.isPending ||
            createManualMutation.isPending,
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
