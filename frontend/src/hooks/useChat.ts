import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { chatService, SendMessageRequest } from '../services/chat';
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

export function useChatActionChips(options?: { limit?: number; enabled?: boolean }) {
    const { limit = 5, enabled = true } = options || {};
    return useQuery({
        queryKey: ['chat', 'action-chips', limit],
        queryFn: () => chatService.getActionChips(limit),
        enabled,
        staleTime: 10 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        refetchOnWindowFocus: false,
    });
}

export function useChat() {
    const queryClient = useQueryClient();
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(loadCurrentSessionId);

    type ChatSessionQueryData = {
        session: {
            id: string;
            session_type: 'command' | 'reflection';
            title?: string | null;
            created_at: string;
            last_activity_at: string;
            message_count?: number;
        };
        messages: Array<{
            id: number;
            role: 'user' | 'assistant' | 'system';
            content: string;
            created_at: string;
            metadata?: Record<string, unknown> | null;
        }>;
        pending_actions: Array<{
            id: string;
            message_id?: number;
            action_type: string;
            action_data: unknown;
            status: string;
            created_at?: string;
        }>;
    };
    type SendMessageResult = {
        response: string;
        pendingActions: ChatSessionQueryData["pending_actions"];
    };

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
            return new Promise<SendMessageResult>((resolve, reject) => {
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
        onMutate: async (variables) => {
            const queryKey = ['chat', 'session', variables.session_id] as const;
            await queryClient.cancelQueries({ queryKey });

            const previous = queryClient.getQueryData<ChatSessionQueryData>(queryKey);
            const nowIso = new Date().toISOString();
            const optimisticId = -Date.now();
            const optimisticMessage = {
                id: optimisticId,
                role: 'user' as const,
                content: variables.content,
                created_at: nowIso,
                metadata: {
                    status: 'optimistic',
                    mentions: variables.mentions || [],
                },
            };

            if (previous) {
                queryClient.setQueryData<ChatSessionQueryData>(queryKey, {
                    ...previous,
                    messages: [...(previous.messages || []), optimisticMessage],
                });
            } else {
                queryClient.setQueryData<ChatSessionQueryData>(queryKey, {
                    session: {
                        id: variables.session_id,
                        session_type: variables.mode === 'reflection' ? 'reflection' : 'command',
                        title: null,
                        created_at: nowIso,
                        last_activity_at: nowIso,
                        message_count: 1,
                    },
                    messages: [optimisticMessage],
                    pending_actions: [],
                });
            }

            return { previous, queryKey };
        },
        onSuccess: (data, variables) => {
            const nowIso = new Date().toISOString();
            const optimisticAssistantId = -(Date.now() + 1);

            queryClient.setQueryData<ChatSessionQueryData>(
                ['chat', 'session', variables.session_id],
                (current) => {
                    if (!current) return current;
                    const currentMessages = [...(current.messages || [])];
                    if (currentMessages.length > 0) {
                        const tail = currentMessages[currentMessages.length - 1];
                        if (
                            tail.role === 'user' &&
                            Number(tail.id) < 0 &&
                            tail.content === variables.content
                        ) {
                            currentMessages[currentMessages.length - 1] = {
                                ...tail,
                                metadata: {
                                    ...(tail.metadata || {}),
                                    status: 'sent',
                                },
                            };
                        }
                    }

                    const responseText = data.response || '';
                    if (responseText) {
                        currentMessages.push({
                            id: optimisticAssistantId,
                            role: 'assistant',
                            content: responseText,
                            created_at: nowIso,
                            metadata: { status: 'optimistic' },
                        });
                    }

                    return {
                        ...current,
                        messages: currentMessages,
                        pending_actions: data.pendingActions || [],
                    };
                }
            );

            // Keep list views eventually consistent without forcing immediate active refetches.
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'], refetchType: 'inactive' });
        },
        onError: (_error, _variables, context) => {
            if (context?.previous && context.queryKey) {
                queryClient.setQueryData(context.queryKey, context.previous);
            }
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
