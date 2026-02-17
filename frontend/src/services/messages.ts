import { api } from './api';

// Types matching backend schemas
export interface Message {
    id: number;
    gmail_id: string;
    thread_id?: string;
    subject: string;
    sender: string;
    recipients: string[];
    received_at: string;
    body: string;
    snippet?: string;
    summary?: string;
    category?: string;
    needs_reply?: boolean;
    is_starred?: boolean;
    status: 'inbox' | 'done' | 'archived';
    scheduling_intent?: {
        detected: boolean;
        confidence: number;
        suggested_duration_minutes?: number;
    };
    extracted_tasks?: ExtractedTask[];
    tasks?: Task[];
    thread_context?: ThreadMessage[];
}

export interface ExtractedTask {
    title: string;
    priority?: string;
    deadline_text?: string;
    source_snippet?: string;
}

export interface Task {
    id: number;
    message_id: number;
    title: string;
    description?: string;
    priority: 'urgent' | 'high' | 'normal' | 'low';
    status: 'pending_approval' | 'approved' | 'in_progress' | 'completed' | 'dismissed' | 'waiting_for';
    approved_at?: string;
    completed_at?: string;
    dismissed_at?: string;
    deadline_at?: string;
    deadline_source?: 'explicit' | 'inferred';
    deadline_user_confirmed?: boolean;
    urgency_suggested_by_ai?: boolean;
    scheduled_reminder_at?: string;
    created_at: string;
    updated_at: string;
    source_message?: TaskSourceMessage;
}

export interface TaskSourceMessage {
    id: number;
    message_id: string;
    thread_id?: string;
    subject: string;
    sender: string;
    recipient: string;
    body: string;
    received_at: string;
    summary?: string;
}

export interface ThreadMessage {
    id: number;
    subject: string;
    sender: string;
    received_at: string;
    snippet?: string;
    is_current?: boolean;
}

export interface MessagesResponse {
    messages: Message[];
    total: number;
}

/**
 * Fetch messages with optional filtering
 */
export async function fetchMessages(params?: {
    limit?: number;
    offset?: number;
    needs_reply?: boolean;
}): Promise<MessagesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());
    if (params?.needs_reply !== undefined) searchParams.append('needs_reply', params.needs_reply.toString());

    const query = searchParams.toString();
    const response = await api.get<MessagesResponse>(`/messages${query ? `?${query}` : ''}`);
    return response.data;
}

/**
 * Update message status (inbox, done, archived)
 */
export async function updateMessageStatus(messageId: number, status: 'inbox' | 'done' | 'archived'): Promise<Message> {
    const response = await api.patch<Message>(`/messages/${messageId}/status`, { status });
    return response.data;
}

/**
 * Mark message as done
 */
export async function markMessageDone(messageId: number): Promise<Message> {
    const response = await api.post<Message>(`/messages/${messageId}/done`);
    return response.data;
}

/**
 * Archive a message
 */
export async function archiveMessage(messageId: number): Promise<Message> {
    const response = await api.post<Message>(`/messages/${messageId}/archive`);
    return response.data;
}

/**
 * Delete a message permanently
 */
export async function deleteMessage(messageId: number): Promise<void> {
    await api.delete(`/messages/${messageId}`);
}
