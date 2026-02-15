import { api } from './api';
import type { Task } from './messages';
export type { Task };

export interface TasksResponse {
    tasks: Task[];
    total: number;
}

export interface TaskStats {
    pending_approval: number;
    approved: number;
    in_progress: number;
    completed: number;
    dismissed: number;
}

/**
 * Approve a pending task
 */
export async function approveTask(taskId: number): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/approve`);
    return response.data;
}

/**
 * Dismiss a task (mark as not relevant)
 */
export async function dismissTask(taskId: number): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/dismiss`);
    return response.data;
}

/**
 * Get task statistics
 */
export async function getTaskStats(): Promise<TaskStats> {
    const response = await api.get<TaskStats>('/tasks/stats');
    return response.data;
}
