import { api } from './api';

export interface ExportData {
    export_timestamp: string;
    export_version: string;
    messages: any[];
    tasks: any[];
    scheduling_suggestions: any[];
    calendar_events: any[];
    principal_memory: any[];
    decision_patterns: any[];
    contact_contexts: any[];
    agent_activity_logs: any[];
    settings?: any;
    gmail_account?: any;
}

export interface DeletionSummary {
    success: boolean;
    message: string;
    deleted: Record<string, number>;
}

/**
 * GDPR Data Export - Export all user data as JSON.
 */
export async function exportUserData(): Promise<ExportData> {
    const response = await api.get<ExportData>('/user/export');
    return response.data;
}

/**
 * Revoke Gmail Access - Disconnect Gmail and delete email data.
 */
export async function revokeGmailAccess(): Promise<{ success: boolean; message: string }> {
    const response = await api.post<{ success: boolean; message: string }>('/auth/gmail/revoke');
    return response.data;
}

/**
 * GDPR Right to Erasure - Complete data deletion.
 */
export async function deleteAllData(): Promise<DeletionSummary> {
    const response = await api.delete<DeletionSummary>('/user/delete', {
        params: { confirm: true }
    });
    return response.data;
}
