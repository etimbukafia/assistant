/**
 * Messages API Service
 * 
 * Functions for message operations against the backend.
 */

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
    deadline_at?: string;
    deadline_source?: 'explicit' | 'inferred';
    deadline_user_confirmed?: boolean;
    urgency_suggested_by_ai?: boolean;
    scheduled_reminder_at?: string;
    created_at: string;
    updated_at: string;
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

export interface DraftReplyResponse {
    draft: string;
    context_used?: string[];
}

export interface SchedulingSuggestion {
    id: number;
    message_id: number;
    detected_intent: string;
    suggested_title: string;
    suggested_duration_minutes: number;
    suggested_attendees: string[];
    time_slots: TimeSlot[];
    draft_message?: string;
    status: 'pending' | 'sent' | 'confirmed' | 'dismissed';
}

export interface TimeSlot {
    start_time: string;
    end_time: string;
    has_conflict: boolean;
    conflict_details?: string;
}

/**
 * Fetch messages with optional filtering
 */
export async function fetchMessages(params?: {
    skip?: number;
    limit?: number;
    needs_reply?: boolean;
}): Promise<MessagesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.needs_reply !== undefined) searchParams.append('needs_reply', params.needs_reply.toString());

    const query = searchParams.toString();
    const response = await api.get<MessagesResponse>(`/messages${query ? `?${query}` : ''}`);
    return response.data;
}

/**
 * Fetch a single message by ID with tasks and thread context
 */
export async function fetchMessage(messageId: number): Promise<Message> {
    const response = await api.get<Message>(`/messages/${messageId}`);
    return response.data;
}

/**
 * Generate a draft reply for a message
 */
export async function generateDraftReply(messageId: number): Promise<DraftReplyResponse> {
    const response = await api.post<DraftReplyResponse>(`/messages/${messageId}/draft-reply`);
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
 * Sync messages from Gmail
 */
export async function syncMessages(maxResults: number = 3): Promise<{ synced: number; processed: number }> {
    const response = await api.post<{ synced: number; processed: number }>(`/messages/sync?max_results=${maxResults}`);
    return response.data;
}

/**
 * Poll for new messages since a timestamp
 * Used for real-time updates without full sync
 */
export async function fetchNewMessages(since: string): Promise<{ messages: Message[]; count: number }> {
    const response = await api.get<{ messages: Message[]; count: number }>(
        `/messages/new?since=${encodeURIComponent(since)}`
    );
    return response.data;
}

/**
 * Sync Gmail-side deletions to mark messages as source_deleted
 * Detects messages deleted from Gmail after being synced
 */
export async function syncDeletions(): Promise<{
    marked_deleted: number;
    total_deletions: number;
    message: string;
}> {
    const response = await api.post<{
        marked_deleted: number;
        total_deletions: number;
        message: string;
    }>('/messages/sync/deletions');
    return response.data;
}

/**
 * Sync sent messages to clear needs_reply flags
 * Any outbound message from user clears ThreadState.needs_reply
 */
export async function syncSentMessages(): Promise<{
    sent_messages_checked: number;
    threads_updated: number;
    thread_ids: string[];
    message: string;
}> {
    const response = await api.post<{
        sent_messages_checked: number;
        threads_updated: number;
        thread_ids: string[];
        message: string;
    }>('/messages/sync/sent');
    return response.data;
}

/**
 * Reprocess a message with AI analysis
 * Updates thread state incrementally
 */
export async function reprocessMessage(messageId: number): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>(`/messages/${messageId}/reprocess`);
    return response.data;
}

// ============================================
// Scheduling APIs
// ============================================

export interface SchedulingSuggestion {
    id: number;
    message_id: number;
    detected_intent: string;
    suggested_title: string;
    suggested_duration_minutes: number;
    suggested_attendees: string[];
    time_slots: TimeSlot[];
    draft_reply?: string;
    status: 'pending' | 'sent' | 'confirmed' | 'dismissed';
    created_at: string;
}

export interface SchedulingSuggestionsResponse {
    suggestions: SchedulingSuggestion[];
    total: number;
}

/**
 * Get scheduling suggestions for a message
 */
export async function getSchedulingSuggestions(messageId: number): Promise<SchedulingSuggestionsResponse> {
    const response = await api.get<SchedulingSuggestionsResponse>(`/scheduling/suggestions?message_id=${messageId}`);
    return response.data;
}

/**
 * Get a specific scheduling suggestion
 */
export async function getSchedulingSuggestion(suggestionId: number): Promise<SchedulingSuggestion> {
    const response = await api.get<SchedulingSuggestion>(`/scheduling/suggestions/${suggestionId}`);
    return response.data;
}

/**
 * Send availability reply for a scheduling suggestion
 */
export async function sendSchedulingReply(suggestionId: number, editedReply?: string): Promise<{ success: boolean; message: string; follow_up_task_id: number }> {
    const body = editedReply ? { edited_reply: editedReply } : undefined;
    const response = await api.post<{ success: boolean; message: string; follow_up_task_id: number }>(
        `/scheduling/suggestions/${suggestionId}/send`,
        body
    );
    return response.data;
}

/**
 * Dismiss a scheduling suggestion
 */
export async function dismissSchedulingSuggestion(suggestionId: number): Promise<{ success: boolean }> {
    const response = await api.post<{ success: boolean }>(`/scheduling/suggestions/${suggestionId}/dismiss`);
    return response.data;
}

