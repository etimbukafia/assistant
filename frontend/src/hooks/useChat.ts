import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { chatService, SendMessageRequest, type ChatSession, type Message, type PendingAction } from '../services/chat';
import { useState, useCallback, useEffect } from 'react';

const STORAGE_KEYS = {
    CURRENT_SESSION_ID: 'chat_current_session_id',
    LAST_MODE: 'chat_last_mode',
} as const;
const CHAT_SESSION_EVENT = 'chat:current-session-changed';

function normalizeMessageContent(value: string): string {
    return (value || '').trim().split(/\s+/).join(' ');
}

function toTimestampMs(value?: string): number {
    if (!value) return 0;
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? 0 : parsed;
}

type SessionData = {
    session: ChatSession;
    messages: Message[];
    pending_actions: PendingAction[];
};

function mergeTransientUserMessages(
    existing: SessionData | null | undefined,
    fresh: SessionData | null | undefined
): SessionData | null | undefined {
    if (!fresh) return fresh;
    const existingMessages = existing?.messages || [];
    const freshMessages = fresh.messages || [];
    if (existingMessages.length === 0) return fresh;

    const nowMs = Date.now();
    const windowMs = 24 * 60 * 60 * 1000;
    const remoteUserMessages = freshMessages.filter((m) => (m.role || '').toLowerCase() === 'user');
    const remoteUserSignatures = new Set(
        remoteUserMessages.map(
            (m) => `${normalizeMessageContent(m.content)}::${Math.floor(toTimestampMs(m.created_at) / 5000)}`
        )
    );

    const hasLikelyRemoteDuplicate = (candidate: Message): boolean => {
        const normalized = normalizeMessageContent(candidate.content || '');
        const candidateTs = toTimestampMs(candidate.created_at);
        if (!normalized) return false;

        // Consider same-content user messages within this window as the same turn.
        // This removes optimistic duplicates after the server copy arrives.
        const duplicateWindowMs = 3 * 60 * 1000;
        for (const remote of remoteUserMessages) {
            if (normalizeMessageContent(remote.content || '') !== normalized) continue;
            const remoteTs = toTimestampMs(remote.created_at);
            if (!candidateTs || !remoteTs) return true;
            if (Math.abs(remoteTs - candidateTs) <= duplicateWindowMs) return true;
        }
        return false;
    };

    const carryOver = existingMessages.filter((m) => {
        const role = (m.role || '').toLowerCase();
        if (role !== 'user') return false;
        const ts = toTimestampMs(m.created_at);
        if (!ts || nowMs - ts > windowMs) return false;
        const status = String((m.metadata as any)?.status || '').toLowerCase();
        const isTransient = Number(m.id) < 0 || status === 'optimistic' || status === 'sent' || status === 'failed';
        if (!isTransient) return false;
        const signature = `${normalizeMessageContent(m.content)}::${Math.floor(ts / 5000)}`;
        if (remoteUserSignatures.has(signature)) return false;
        if (hasLikelyRemoteDuplicate(m)) return false;
        return true;
    });

    if (carryOver.length === 0) return fresh;

    const merged = [...freshMessages, ...carryOver].sort((a, b) => {
        const delta = toTimestampMs(a.created_at) - toTimestampMs(b.created_at);
        if (delta !== 0) return delta;
        return Number(a.id) - Number(b.id);
    });

    return {
        ...fresh,
        messages: merged,
    };
}

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
        // Keep list snappy while still refreshing in the background.
        staleTime: 15_000,
        gcTime: 10 * 60 * 1000,
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
        refetchInterval: false,
    });
}

export function useChatSession(sessionId: string | null) {
    const queryClient = useQueryClient();
    return useQuery({
        queryKey: ['chat', 'session', sessionId],
        queryFn: async () => {
            if (!sessionId) return null;
            const fresh = await chatService.getSession(sessionId);
            const key = ['chat', 'session', sessionId] as const;
            const existing = queryClient.getQueryData<SessionData>(key);
            return mergeTransientUserMessages(existing, fresh);
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

    type ChatSessionQueryData = SessionData;
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
            window.dispatchEvent(new CustomEvent(CHAT_SESSION_EVENT, { detail: { sessionId } }));
        }
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const onStorage = (e: StorageEvent) => {
            if (e.key !== STORAGE_KEYS.CURRENT_SESSION_ID) return;
            setCurrentSessionId(e.newValue || null);
        };
        const onSessionChange = (e: Event) => {
            const detail = (e as CustomEvent<{ sessionId?: string | null }>).detail;
            setCurrentSessionId(detail?.sessionId || null);
        };
        window.addEventListener('storage', onStorage);
        window.addEventListener(CHAT_SESSION_EVENT, onSessionChange as EventListener);
        return () => {
            window.removeEventListener('storage', onStorage);
            window.removeEventListener(CHAT_SESSION_EVENT, onSessionChange as EventListener);
        };
    }, []);

    const createSessionMutation = useMutation({
        mutationFn: chatService.createSession,
        onSuccess: (newSession) => {
            updateCurrentSession(newSession.id);
            // Insert immediately so new session appears without waiting for refetch.
            queryClient.setQueriesData<any>(
                { queryKey: ['chat', 'sessions'] },
                (old: any) => {
                    if (!old || !Array.isArray(old.sessions)) return old;
                    if (old.sessions.some((s: any) => s.id === newSession.id)) return old;
                    return {
                        ...old,
                        sessions: [newSession, ...old.sessions],
                        total: typeof old.total === 'number' ? old.total + 1 : old.total,
                    };
                }
            );
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'], refetchType: 'inactive' });
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
            const normalizedContent = normalizeMessageContent(variables.content);
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

            return { previous, queryKey, optimisticId, optimisticCreatedAt: nowIso, normalizedContent };
        },
        onSuccess: (data, variables, context) => {
            const nowIso = new Date().toISOString();
            const optimisticAssistantId = -(Date.now() + 1);

            queryClient.setQueryData<ChatSessionQueryData>(
                ['chat', 'session', variables.session_id],
                (current) => {
                    const baseSession = current?.session || {
                        id: variables.session_id,
                        session_type: variables.mode === 'reflection' ? 'reflection' : 'command',
                        title: null,
                        created_at: nowIso,
                        last_activity_at: nowIso,
                        message_count: 0,
                    };
                    const currentMessages = [...(current?.messages || [])];
                    const normalizedContent =
                        context?.normalizedContent || normalizeMessageContent(variables.content);

                    let matchedUserIndex = -1;
                    if (context?.optimisticId) {
                        matchedUserIndex = currentMessages.findIndex((m) => m.id === context.optimisticId);
                    }

                    if (matchedUserIndex < 0) {
                        for (let idx = currentMessages.length - 1; idx >= 0; idx -= 1) {
                            const msg = currentMessages[idx];
                            if (msg.role !== 'user') continue;
                            const normalizedMsg = normalizeMessageContent(msg.content || '');
                            if (normalizedMsg === normalizedContent) {
                                matchedUserIndex = idx;
                                break;
                            }
                        }
                    }

                    if (matchedUserIndex >= 0) {
                        const msg = currentMessages[matchedUserIndex];
                        currentMessages[matchedUserIndex] = {
                            ...msg,
                            metadata: {
                                ...(msg.metadata || {}),
                                status: 'sent',
                            },
                        };
                    } else {
                        currentMessages.push({
                            id: context?.optimisticId || -(Date.now() + 2),
                            role: 'user',
                            content: variables.content,
                            created_at: context?.optimisticCreatedAt || nowIso,
                            metadata: { status: 'sent', source: 'reconstructed' },
                        });
                    }

                    const responseText = data.response || '';
                    if (responseText) {
                        const hasAssistantDuplicate = currentMessages.some(
                            (m) => m.role === 'assistant' && (m.content || '').trim() === responseText.trim()
                        );
                        if (!hasAssistantDuplicate) {
                            currentMessages.push({
                                id: optimisticAssistantId,
                                role: 'assistant',
                                content: responseText,
                                created_at: nowIso,
                                metadata: { status: 'optimistic' },
                            });
                        }
                    }

                    return {
                        ...(current || {}),
                        session: baseSession,
                        messages: currentMessages,
                        pending_actions: data.pendingActions || [],
                    };
                }
            );

            // Keep list views eventually consistent without forcing immediate active refetches.
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'], refetchType: 'inactive' });
        },
        onError: (_error, variables, context) => {
            if (!context?.queryKey) return;
            queryClient.setQueryData<ChatSessionQueryData>(
                context.queryKey,
                (current) => {
                    if (!current) {
                        return context.previous || current;
                    }
                    const normalizedTarget =
                        context.normalizedContent || normalizeMessageContent(variables.content);
                    const nextMessages = [...(current.messages || [])];
                    for (let idx = nextMessages.length - 1; idx >= 0; idx -= 1) {
                        const msg = nextMessages[idx];
                        if (msg.role !== 'user') continue;
                        const normalizedMsg = normalizeMessageContent(msg.content || '');
                        if (normalizedMsg !== normalizedTarget) continue;
                        nextMessages[idx] = {
                            ...msg,
                            metadata: {
                                ...(msg.metadata || {}),
                                status: 'failed',
                            },
                        };
                        return {
                            ...current,
                            messages: nextMessages,
                        };
                    }
                    return current;
                }
            );
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
