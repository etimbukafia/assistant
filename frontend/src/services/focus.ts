import { api } from './api';
import type { Task } from './messages';

export interface GoalItem {
    text: string;
    completed: boolean;
}

export interface DailyFocus {
    id: number | null;
    focus_date: string;
    goals: GoalItem[];
    frog_task_id: number | null;
    frog_task: Task | null;
    weekly_target: string | null;
    goals_completed: number;
    goals_total: number;
}

export interface DailyFocusUpdate {
    goals?: GoalItem[];
    frog_task_id?: number | null;
    weekly_target?: string | null;
}

export interface WeeklySummary {
    week_start: string;
    week_end: string;
    weekly_target: string | null;
    days: DailyFocus[];
    total_goals_set: number;
    total_goals_completed: number;
    tasks_completed_this_week: number;
}

export async function fetchDailyFocus(date?: string): Promise<DailyFocus> {
    const params = date ? { date } : {};
    const response = await api.get<DailyFocus>('/focus/daily', { params });
    return response.data;
}

export async function updateDailyFocus(payload: DailyFocusUpdate, date?: string): Promise<DailyFocus> {
    const params = date ? { date } : {};
    const response = await api.put<DailyFocus>('/focus/daily', payload, { params });
    return response.data;
}

export async function fetchWeeklySummary(): Promise<WeeklySummary> {
    const response = await api.get<WeeklySummary>('/focus/weekly-summary');
    return response.data;
}
