import { api } from './api';

// =============================================================================
// Types
// =============================================================================

export interface Message {
    id: string; // Changed to string to match mobile/backend if needed, keeping string for now based on previous file
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at: string;
}

export interface ChatSession {
    id: string;
    snippet: string;
    updated_at: string;
}

export interface SendMessageRequest {
    session_id: string;
    content: string;
    mode: 'action' | 'reflection';
}

export interface CreateSessionRequest {
    initial_message?: string;
    mode?: 'action' | 'reflection';
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

// =============================================================================
// Service
// =============================================================================

export const chatService = {
    async getSessions(limit = 20, offset = 0): Promise<ChatSession[]> {
        const response = await api.get<ChatSession[]>('/chat/sessions', {
            params: { limit, offset }
        });
        return response.data;
    },

    async createSession(request: CreateSessionRequest): Promise<ChatSession> {
        const response = await api.post<ChatSession>('/chat/sessions', request);
        return response.data;
    },

    async getMessages(sessionId: string): Promise<Message[]> {
        const response = await api.get<Message[]>(`/chat/sessions/${sessionId}/messages`);
        return response.data;
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
        const response = await api.post<SendMessageResponse>('/chat/messages', request);
        return response.data;
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
