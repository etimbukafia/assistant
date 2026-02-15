import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { chatService, SendMessageRequest, CreateSessionRequest } from '../services/chat';
import { useState, useCallback } from 'react';

const STORAGE_KEYS = {
    CURRENT_SESSION_ID: 'chat_current_session_id',
    LAST_MODE: 'chat_last_mode',
} as const;

export function loadCurrentSessionId(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(STORAGE_KEYS.CURRENT_SESSION_ID);
}

export function saveLastMode(mode: 'action' | 'reflection'): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEYS.LAST_MODE, mode);
}

export function loadLastMode(): 'action' | 'reflection' {
    if (typeof window === 'undefined') return 'action';
    const mode = localStorage.getItem(STORAGE_KEYS.LAST_MODE);
    return (mode as 'action' | 'reflection') || 'action';
}

export function useChatSessions(options?: { limit?: number; offset?: number; enabled?: boolean }) {
    const { limit = 20, offset = 0, enabled = true } = options || {};
    return useQuery({
        queryKey: ['chat', 'sessions', { limit, offset }],
        queryFn: () => chatService.getSessions(limit, offset),
        enabled,
    });
}

export function useChatSession(sessionId: string | null) {
    return useQuery({
        queryKey: ['chat', 'session', sessionId],
        queryFn: async () => {
            if (!sessionId) return null;
            return chatService.getSession(sessionId);
        },
        enabled: !!sessionId,
        refetchInterval: 5000,
    });
}

// Keep legacy for compatibility but wrap new logic if needed, or just deprecate
export function useChatMessages(sessionId: string | null) {
    const { data, isLoading, error } = useChatSession(sessionId);
    return {
        data: data?.messages || [],
        pendingActions: data?.pending_actions || [],
        isLoading,
        error
    };
}

export function useChat() {
    const queryClient = useQueryClient();
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(loadCurrentSessionId);

    const updateCurrentSession = useCallback((sessionId: string | null) => {
        setCurrentSessionId(sessionId);
        if (typeof window !== 'undefined') {
            if (sessionId) {
                localStorage.setItem(STORAGE_KEYS.CURRENT_SESSION_ID, sessionId);
            } else {
                localStorage.removeItem(STORAGE_KEYS.CURRENT_SESSION_ID);
            }
        }
    }, []);

    const createSessionMutation = useMutation({
        mutationFn: chatService.createSession,
        onSuccess: (newSession) => {
            updateCurrentSession(newSession.id);
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] });
        },
    });

    const sendMessageMutation = useMutation({
        mutationFn: async (request: SendMessageRequest) => {
            return new Promise((resolve, reject) => {
                chatService.sendMessageWithPolling(request, {
                    onComplete: (response, pendingActions) => {
                        resolve({ response, pendingActions });
                    },
                    onError: (error) => {
                        reject(new Error(error));
                    },
                    onProcessing: (jobId) => {
                        console.log(`[Chat] Processing job: ${jobId}`);
                    }
                });
            });
        },
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'session', variables.session_id] });
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] });
        },
    });

    const deleteSessionMutation = useMutation({
        mutationFn: chatService.deleteSession,
        onSuccess: (_, sessionId) => {
            if (currentSessionId === sessionId) {
                updateCurrentSession(null);
            }
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] });
        },
    });

    const approveActionMutation = useMutation({
        mutationFn: (variables: { sessionId: string, actionId: string }) =>
            chatService.approveAction(variables.sessionId, variables.actionId),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'session', variables.sessionId] });
        },
    });

    const rejectActionMutation = useMutation({
        mutationFn: (variables: { sessionId: string, actionId: string }) =>
            chatService.rejectAction(variables.sessionId, variables.actionId),
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ['chat', 'session', variables.sessionId] });
        },
    });

    return {
        currentSessionId,
        setCurrentSessionId: updateCurrentSession,
        createSession: createSessionMutation.mutateAsync,
        sendMessage: sendMessageMutation.mutateAsync,
        deleteSession: deleteSessionMutation.mutateAsync,
        approveAction: approveActionMutation.mutateAsync,
        rejectAction: rejectActionMutation.mutateAsync,
        isCreating: createSessionMutation.isPending,
        isSending: sendMessageMutation.isPending,
        isDeleting: deleteSessionMutation.isPending,
        isApproving: approveActionMutation.isPending,
        isRejecting: rejectActionMutation.isPending,
    };
}
