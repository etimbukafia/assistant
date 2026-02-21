import { api } from './api';

// =============================================================================
// Types
// =============================================================================

export interface Message {
    id: number;
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at: string;
    metadata?: Record<string, unknown> | null;
}

export interface ChatSession {
    id: string;
    session_type: 'command' | 'reflection';
    title?: string | null;
    created_at: string;
    last_activity_at: string;
    message_count?: number;
}

export interface SendMessageRequest {
    session_id: string;
    content: string;
    mode: 'action' | 'reflection';
    mentions?: ChatMention[];
}

export interface ChatMention {
    kind: 'contact' | 'thread' | 'event' | 'task' | 'memory';
    ref: string;
    label: string;
    metadata?: Record<string, unknown>;
}

export interface MentionSuggestion {
    kind: 'contact' | 'thread' | 'event' | 'task' | 'memory';
    ref: string;
    label: string;
    display_label?: string;
    subtitle?: string;
    last_seen_at?: string;
    created_at?: string;
    updated_at?: string;
    search_text?: string;
}

export interface ActionChip {
    id: string;
    label: string;
    prompt: string;
}

export interface CreateSessionRequest {
    mode?: 'action' | 'reflection';
}

export interface ChatSessionsResponse {
    sessions: ChatSession[];
    total: number;
}

export type ProcessingStatus = 'complete' | 'processing' | 'failed';

export interface Contact {
    email: string;
    name?: string;
}

export interface DraftEmailData {
    subject?: string;
    body?: string;
    recipients?: string[]; // or Contact[]
    to?: string[];
    cc?: string[];
    bcc?: string[];
}

export interface CreateEventData {
    title?: string;
    start_time?: string;
    end_time?: string;
    description?: string;
    attendees?: string[]; // email strings
    location?: string;
}

export interface CreateTaskData {
    title: string;
    description?: string;
    deadline?: string;
    priority?: 'low' | 'normal' | 'high' | 'urgent';
}

export type ActionData = DraftEmailData | CreateEventData | CreateTaskData | Record<string, unknown>;

export interface PendingAction {
    id: string;
    action_type: 'draft_email' | 'create_event' | 'create_task' | string;
    action_data: ActionData;
    status: 'pending' | 'approved' | 'rejected';
    message_id: number;
}

export interface SendMessageResponse {
    status: ProcessingStatus;
    message_id: number;
    job_id?: string;
    response?: string;
    pending_actions?: PendingAction[];
    error?: string;
}

export interface JobStatusResponse {
    status: ProcessingStatus;
    job_id: string;
    message_id?: number;
    response?: string;
    pending_actions?: PendingAction[];
    error?: string;
}

function isTimeoutError(error: unknown): boolean {
    const candidate = error as { code?: string; message?: string } | undefined;
    const code = (candidate?.code || "").toUpperCase();
    const message = (candidate?.message || "").toLowerCase();
    return code === "ECONNABORTED" || message.includes("timeout");
}

// =============================================================================
// Service
// =============================================================================

export const chatService = {
    async getSessions(limit = 20, offset = 0): Promise<ChatSessionsResponse> {
        const response = await api.get<ChatSessionsResponse>('/chat/sessions', {
            params: { limit, offset }
        });
        return response.data;
    },

    async createSession(request: CreateSessionRequest): Promise<ChatSession> {
        const sessionType = request.mode === 'reflection' ? 'reflection' : 'command';
        const response = await api.post<ChatSession>('/chat/sessions', {
            session_type: sessionType,
        });
        return response.data;
    },

    async getMessages(sessionId: string): Promise<Message[]> {
        const response = await api.get<{ messages: Message[] }>(`/chat/sessions/${sessionId}/messages`);
        return response.data.messages;
    },

    async getSession(sessionId: string): Promise<{
        session: ChatSession;
        messages: Message[];
        pending_actions: PendingAction[];
    }> {
        const response = await api.get(`/chat/sessions/${sessionId}`);
        return response.data;
    },

    async sendMessage(request: SendMessageRequest): Promise<SendMessageResponse> {
        const response = await api.post<SendMessageResponse>(
            `/chat/sessions/${request.session_id}/messages`,
            { content: request.content, mentions: request.mentions || [] }
        );
        return response.data;
    },

    async getMentionSuggestions(
        query: string,
        limit = 8,
        sessionId = "default",
        offset = 0,
        kind?: "contact" | "thread" | "event" | "task"
    ): Promise<MentionSuggestion[]> {
        const response = await api.get<MentionSuggestion[]>("/chat/mentions", {
            params: { q: query || undefined, limit, offset, kind, session_id: sessionId },
        });
        return response.data || [];
    },

    async getSlashSuggestions(
        query: string,
        limit = 8,
        sessionId = "default",
        offset = 0,
        memoryType?: "decision" | "commitment" | "preferences" | "relationships" | "insight"
    ): Promise<MentionSuggestion[]> {
        const response = await api.get<MentionSuggestion[]>("/chat/slash-suggestions", {
            params: { q: query || undefined, limit, offset, memory_type: memoryType, session_id: sessionId },
        });
        return response.data || [];
    },

    async getActionChips(limit = 5): Promise<ActionChip[]> {
        const response = await api.get<ActionChip[]>("/chat/action-chips", { params: { limit } });
        return response.data || [];
    },

    async deleteSession(sessionId: string): Promise<void> {
        await api.delete(`/chat/sessions/${sessionId}`);
    },

    // =============================================================================
    // Job Polling
    // =============================================================================

    async getJobStatus(jobId: string): Promise<JobStatusResponse> {
        const response = await api.get<JobStatusResponse>(`/chat/jobs/${jobId}`);
        return response.data;
    },

    pollJobStatus(
        jobId: string,
        onUpdate: (result: JobStatusResponse) => void,
        options: {
            initialInterval?: number;
            maxInterval?: number;
            maxAttempts?: number;
        } = {}
    ): () => void {
        const {
            initialInterval = 1000,
            maxInterval = 5000,
            maxAttempts = 60,
        } = options;

        let attempts = 0;
        let interval = initialInterval;
        let timeoutId: ReturnType<typeof setTimeout> | null = null;
        let stopped = false;

        const poll = async () => {
            if (stopped) return;

            try {
                const result = await chatService.getJobStatus(jobId);
                onUpdate(result);

                if (result.status === 'processing') {
                    if (attempts < maxAttempts) {
                        attempts++;
                        interval = Math.min(interval * 1.2, maxInterval);
                        timeoutId = setTimeout(poll, interval);
                    } else {
                        onUpdate({
                            status: 'failed',
                            job_id: jobId,
                            error: 'Response timed out. Please try again.',
                        });
                    }
                }
            } catch (error) {
                console.error('Error polling job status:', error);
                onUpdate({
                    status: 'failed',
                    job_id: jobId,
                    error: 'Failed to check job status',
                });
            }
        };

        poll();

        return () => {
            stopped = true;
            if (timeoutId) clearTimeout(timeoutId);
        };
    },

    pollSessionForReply(
        sessionId: string,
        sentAtMs: number,
        onUpdate: (result: JobStatusResponse) => void,
        options: {
            initialInterval?: number;
            maxInterval?: number;
            maxAttempts?: number;
        } = {}
    ): () => void {
        const {
            initialInterval = 1200,
            maxInterval = 5000,
            maxAttempts = 40,
        } = options;

        let attempts = 0;
        let interval = initialInterval;
        let timeoutId: ReturnType<typeof setTimeout> | null = null;
        let stopped = false;

        const poll = async () => {
            if (stopped) return;
            try {
                const snapshot = await chatService.getSession(sessionId);
                const assistantMessages = (snapshot.messages || []).filter(
                    (m) =>
                        m.role === "assistant" &&
                        Boolean((m.content || "").trim())
                );
                const latest = assistantMessages[assistantMessages.length - 1];
                const createdAtMs = latest ? Date.parse(latest.created_at) : 0;
                if (latest && createdAtMs >= sentAtMs - 1500) {
                    const pending = (snapshot.pending_actions || []).filter((a) => a.message_id === latest.id);
                    onUpdate({
                        status: "complete",
                        job_id: `session-fallback:${sessionId}`,
                        message_id: latest.id,
                        response: latest.content,
                        pending_actions: pending,
                    });
                    return;
                }

                if (attempts < maxAttempts) {
                    attempts++;
                    interval = Math.min(interval * 1.2, maxInterval);
                    timeoutId = setTimeout(poll, interval);
                } else {
                    onUpdate({
                        status: "failed",
                        job_id: `session-fallback:${sessionId}`,
                        error: "I'm still working on that. Please retry.",
                    });
                }
            } catch {
                if (attempts < maxAttempts) {
                    attempts++;
                    interval = Math.min(interval * 1.2, maxInterval);
                    timeoutId = setTimeout(poll, interval);
                } else {
                    onUpdate({
                        status: "failed",
                        job_id: `session-fallback:${sessionId}`,
                        error: "Failed to confirm response status.",
                    });
                }
            }
        };

        poll();

        return () => {
            stopped = true;
            if (timeoutId) clearTimeout(timeoutId);
        };
    },

    async sendMessageWithPolling(
        request: SendMessageRequest,
        callbacks: {
            onComplete: (response: string, pendingActions: PendingAction[]) => void;
            onError: (error: string) => void;
            onProcessing?: (jobId: string, messageId: number) => void;
        }
    ): Promise<() => void> {
        // ... (Implementation continues in next chunk due to complexity if needed, but fitting here)
        let cleanup: (() => void) | null = null;
        const sentAtMs = Date.now();

        try {
            const result = await chatService.sendMessage(request);

            if (result.status === 'complete') {
                callbacks.onComplete(result.response || '', result.pending_actions || []);
                return () => { };
            }

            if (result.status === 'processing' && result.job_id) {
                callbacks.onProcessing?.(result.job_id, result.message_id);

                cleanup = chatService.pollJobStatus(result.job_id, (jobResult) => {
                    if (jobResult.status === 'complete') {
                        callbacks.onComplete(jobResult.response || '', jobResult.pending_actions || []);
                    } else if (jobResult.status === 'failed') {
                        callbacks.onError(jobResult.error || 'Processing failed');
                    }
                });

                return () => cleanup?.();
            }

            callbacks.onError(result.error || 'Unexpected response');
            return () => { };
        } catch (error) {
            if (isTimeoutError(error)) {
                callbacks.onProcessing?.(`session-fallback:${request.session_id}`, -1);
                cleanup = chatService.pollSessionForReply(request.session_id, sentAtMs, (jobResult) => {
                    if (jobResult.status === "complete") {
                        callbacks.onComplete(jobResult.response || "", jobResult.pending_actions || []);
                    } else if (jobResult.status === "failed") {
                        callbacks.onError(jobResult.error || "Processing failed");
                    }
                });
                return () => cleanup?.();
            }
            const message = error instanceof Error ? error.message : 'Network error';
            callbacks.onError(message);
            return () => cleanup?.();
        }
    },

    // =============================================================================
    // Action Operations
    // =============================================================================

    async approveAction(
        sessionId: string,
        actionId: string
    ): Promise<{ success: boolean; result?: unknown; error?: string }> {
        const response = await api.post(`/chat/sessions/${sessionId}/approve/${actionId}`);
        return response.data;
    },

    async rejectAction(
        sessionId: string,
        actionId: string
    ): Promise<{ success: boolean; error?: string }> {
        const response = await api.post(`/chat/sessions/${sessionId}/reject/${actionId}`);
        return response.data;
    }
};
