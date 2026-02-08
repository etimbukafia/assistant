/**
 * Chat Service
 *
 * API client for chat functionality with support for both
 * synchronous and asynchronous processing paths.
 *
 * Processing Strategy:
 * - Reflection mode: Always synchronous (warm, immediate)
 * - Action mode: Optimistic sync with async fallback
 */

import { api } from './api';

// =============================================================================
// Types
// =============================================================================

export type SessionType = 'command' | 'reflection';
export type ProcessingStatus = 'complete' | 'processing' | 'failed';
export type ActionStatus = 'pending' | 'approved' | 'rejected';

export interface ChatSession {
  id: string;
  session_type: SessionType;
  title: string | null;
  created_at: string;
  last_activity_at: string;
  message_count?: number;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface PendingAction {
  id: string;
  action_type: string;
  action_data: Record<string, unknown>;
  status: ActionStatus;
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
// Session Operations
// =============================================================================

/**
 * Create a new chat session.
 *
 * @param sessionType - 'command' for work tasks, 'reflection' for supportive chat
 */
export async function createSession(sessionType: SessionType = 'command'): Promise<ChatSession> {
  const response = await api.post<ChatSession>('/chat/sessions', {
    session_type: sessionType,
  });
  return response.data;
}

/**
 * List user's chat sessions.
 */
export async function listSessions(
  limit: number = 20,
  offset: number = 0
): Promise<{ sessions: ChatSession[]; total: number }> {
  const response = await api.get<{ sessions: ChatSession[]; total: number }>('/chat/sessions', {
    params: { limit, offset },
  });
  return response.data;
}

/**
 * Get a session with messages and pending actions.
 */
export async function getSession(sessionId: string): Promise<{
  session: ChatSession;
  messages: ChatMessage[];
  pending_actions: PendingAction[];
}> {
  const response = await api.get(`/chat/sessions/${sessionId}`);
  return response.data;
}

/**
 * Delete a chat session.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/chat/sessions/${sessionId}`);
}

// =============================================================================
// Message Operations
// =============================================================================

/**
 * Send a message and get AI response.
 *
 * Response handling:
 * - status="complete": Response included, display immediately
 * - status="processing": Poll job_id for completion
 */
export async function sendMessage(
  sessionId: string,
  content: string
): Promise<SendMessageResponse> {
  const response = await api.post<SendMessageResponse>(
    `/chat/sessions/${sessionId}/messages`,
    { content }
  );
  return response.data;
}

/**
 * Get messages for a session.
 */
export async function getMessages(
  sessionId: string,
  limit: number = 50,
  offset: number = 0
): Promise<ChatMessage[]> {
  const response = await api.get<{ messages: ChatMessage[] }>(
    `/chat/sessions/${sessionId}/messages`,
    { params: { limit, offset } }
  );
  return response.data.messages;
}

// =============================================================================
// Job Polling
// =============================================================================

/**
 * Check the status of an async chat job.
 *
 * Use this when sendMessage returns status="processing".
 */
export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await api.get<JobStatusResponse>(`/chat/jobs/${jobId}`);
  return response.data;
}

/**
 * Poll for job completion with adaptive intervals.
 *
 * @param jobId - The job ID to poll
 * @param onUpdate - Callback when status changes
 * @param options - Polling options
 * @returns Cleanup function to stop polling
 */
export function pollJobStatus(
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
      const result = await getJobStatus(jobId);
      onUpdate(result);

      if (result.status === 'processing' && attempts < maxAttempts) {
        attempts++;
        // Adaptive backoff
        interval = Math.min(interval * 1.2, maxInterval);
        timeoutId = setTimeout(poll, interval);
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

  // Start polling
  poll();

  // Return cleanup function
  return () => {
    stopped = true;
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  };
}

// =============================================================================
// Action Operations
// =============================================================================

/**
 * Approve a pending action.
 */
export async function approveAction(
  sessionId: string,
  actionId: string
): Promise<{ success: boolean; result?: unknown; error?: string }> {
  const response = await api.post(`/chat/sessions/${sessionId}/approve/${actionId}`);
  return response.data;
}

/**
 * Reject a pending action.
 */
export async function rejectAction(
  sessionId: string,
  actionId: string
): Promise<{ success: boolean; error?: string }> {
  const response = await api.post(`/chat/sessions/${sessionId}/reject/${actionId}`);
  return response.data;
}

// =============================================================================
// Convenience Hook Helpers
// =============================================================================

/**
 * Send a message and handle both sync/async responses.
 *
 * This is the recommended way to send messages - it handles
 * the polling automatically for async responses.
 *
 * @param sessionId - Session to send to
 * @param content - Message content
 * @param callbacks - Event callbacks
 */
export async function sendMessageWithPolling(
  sessionId: string,
  content: string,
  callbacks: {
    onComplete: (response: string, pendingActions: PendingAction[]) => void;
    onError: (error: string) => void;
    onProcessing?: (jobId: string, messageId: number) => void;
  }
): Promise<() => void> {
  let cleanup: (() => void) | null = null;

  try {
    const result = await sendMessage(sessionId, content);

    if (result.status === 'complete') {
      // Sync response - done immediately
      callbacks.onComplete(result.response || '', result.pending_actions || []);
      return () => {};
    }

    if (result.status === 'processing' && result.job_id) {
      // Async response - start polling
      callbacks.onProcessing?.(result.job_id, result.message_id);

      cleanup = pollJobStatus(result.job_id, (jobResult) => {
        if (jobResult.status === 'complete') {
          callbacks.onComplete(jobResult.response || '', jobResult.pending_actions || []);
        } else if (jobResult.status === 'failed') {
          callbacks.onError(jobResult.error || 'Processing failed');
        }
        // status === 'processing' - keep polling
      });

      return () => cleanup?.();
    }

    // Unexpected status
    callbacks.onError(result.error || 'Unexpected response');
    return () => {};
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Network error';
    callbacks.onError(message);
    return () => cleanup?.();
  }
}
