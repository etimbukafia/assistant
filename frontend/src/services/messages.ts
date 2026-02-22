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
    type?: string;
    task_signal?: string;
    priority: 'urgent' | 'high' | 'normal' | 'low';
    status: 'pending_approval' | 'approved' | 'in_progress' | 'completed' | 'dismissed';
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

// Thread Intelligence View types
export interface ThreadStateDetail {
    summary?: string;
    open_tasks: Array<{ id: string; title: string; status: string }>;
    decisions: Array<{ decision: string; made_by: string; made_at: string }>;
    participants: Array<{ email: string; name: string; role: string }>;
    action_points: string[];
    needs_reply: boolean;
    message_count: number;
    last_action?: string;
    last_action_by?: string;
}

export interface ThreadMessageDetail {
    id: number;
    sender: string;
    subject?: string;
    body: string;
    summary?: string;
    received_at: string;
    scheduling_intent: boolean;
    scheduling_intent_type?: string;
}

export interface SchedulingSuggestion {
    id: number;
    thread_id: string;
    suggested_slots: Array<{ start_time: string; end_time: string; has_conflict: boolean }>;
    draft_reply?: string;
    meeting_type: string;
    duration_minutes: number;
    status: string;
}

export interface ThreadDetailResponse {
    thread_state: ThreadStateDetail;
    messages: ThreadMessageDetail[];
    tasks: Task[];
    scheduling_suggestions: SchedulingSuggestion[];
}

/**
 * Fetch messages with optional filtering
 */
export async function fetchMessages(params?: {
    limit?: number;
    offset?: number;
    needs_reply?: boolean;
    status?: string;
}): Promise<MessagesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());
    if (params?.needs_reply !== undefined) searchParams.append('needs_reply', params.needs_reply.toString());
    if (params?.status) searchParams.append('status', params.status);

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

/**
 * Fetch full thread detail for Thread Intelligence View
 */
export async function fetchThreadDetail(threadId: string): Promise<ThreadDetailResponse> {
    const response = await api.get<ThreadDetailResponse>(`/messages/thread/${threadId}`);
    return response.data;
}

/**
 * Generate a draft reply for a message
 */
export async function generateDraftReply(messageId: number, context?: string): Promise<{ draft: string }> {
    const response = await api.post<{ draft: string }>(`/messages/${messageId}/draft-reply`, { context });
    return response.data;
}

/**
 * Send a reply to a message
 */
export interface SendReplyRequest {
    body: string;
    to: string;
    cc?: string[];
    bcc?: string[];
    subject?: string;
}

export interface SendReplyResponse {
    sent: boolean;
    message_id?: string;
    thread_id?: string;
    error?: string;
}

export async function sendReply(messageId: number, data: SendReplyRequest): Promise<SendReplyResponse> {
    const response = await api.post<SendReplyResponse>(`/messages/${messageId}/send-reply`, data);
    return response.data;
}
