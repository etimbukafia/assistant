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

export interface CreateTaskRequest {
    message_id: number;
    title: string;
    description?: string;
    priority?: 'urgent' | 'high' | 'normal' | 'low';
    deadline_at?: string;
}

export interface ManualTaskRequest {
    title: string;
    description?: string;
    priority?: 'urgent' | 'high' | 'normal' | 'low';
    deadline_at?: string;
}

export interface UpdateTaskRequest {
    title?: string;
    description?: string;
    priority?: 'urgent' | 'high' | 'normal' | 'low';
    deadline?: string;
    confirm_deadline?: boolean;
    mark_urgent?: boolean;
    scheduled_reminder_at?: string;
}

export async function fetchTasks(params?: {
    status?: string;
    limit?: number;
    offset?: number;
}): Promise<TasksResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append('status', params.status);
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());

    const query = searchParams.toString();
    const response = await api.get<TasksResponse>(`/tasks${query ? `?${query}` : ''}`);
    return response.data;
}

export async function fetchTask(taskId: number): Promise<Task> {
    const response = await api.get<Task>(`/tasks/${taskId}`);
    return response.data;
}

export async function getTaskStats(): Promise<TaskStats> {
    const response = await api.get<TaskStats>('/tasks/stats');
    return response.data;
}

export async function approveTask(taskId: number): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/approve`);
    return response.data;
}

export async function dismissTask(taskId: number): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/dismiss`);
    return response.data;
}

export async function completeTask(taskId: number): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/complete`);
    return response.data;
}

export async function startTask(taskId: number): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/start`);
    return response.data;
}

export async function updateTask(taskId: number, request: UpdateTaskRequest): Promise<Task> {
    const response = await api.put<Task>(`/tasks/${taskId}`, request);
    return response.data;
}

export async function createTask(request: CreateTaskRequest): Promise<Task> {
    const response = await api.post<Task>('/tasks', request);
    return response.data;
}

export async function createManualTask(request: ManualTaskRequest): Promise<Task> {
    const response = await api.post<Task>('/tasks/manual', request);
    return response.data;
}

export async function snoozeTask(taskId: number, snoozeUntil: string): Promise<Task> {
    const response = await api.post<Task>(`/tasks/${taskId}/snooze`, { snooze_until: snoozeUntil });
    return response.data;
}
