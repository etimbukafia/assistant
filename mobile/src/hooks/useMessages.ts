/**
 * Messages Hooks
 *
 * TanStack Query hooks for message operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchMessages,
    fetchMessage,
    fetchNewMessages,
    syncMessages,
    syncDeletions,
    syncSentMessages,
    reprocessMessage,
    markMessageDone,
    archiveMessage,
    deleteMessage,
    generateDraftReply,
    getSchedulingSuggestions,
    getSchedulingSuggestion,
    sendSchedulingReply,
    dismissSchedulingSuggestion,
    fetchProcessingStatus,
    Message,
    MessagesResponse,
    SchedulingSuggestion,
} from '@/src/services/messages';

export const messagesKeys = {
    all: ['messages'] as const,
    lists: () => [...messagesKeys.all, 'list'] as const,
    list: (filters?: { needs_reply?: boolean }) => [...messagesKeys.lists(), filters] as const,
    details: () => [...messagesKeys.all, 'detail'] as const,
    detail: (id: number) => [...messagesKeys.details(), id] as const,
    new: (since: string) => [...messagesKeys.all, 'new', since] as const,
};

/**
 * Hook for fetching messages with optional filtering
 */
export function useMessages(params?: { limit?: number; offset?: number; needs_reply?: boolean; enabled?: boolean }) {
    return useQuery({
        queryKey: messagesKeys.list({ needs_reply: params?.needs_reply }),
        queryFn: () => fetchMessages(params),
        enabled: params?.enabled ?? true,
    });
}

/**
 * Hook for fetching a single message
 */
export function useMessage(messageId: number | null) {
    return useQuery({
        queryKey: messagesKeys.detail(messageId!),
        queryFn: () => fetchMessage(messageId!),
        enabled: messageId !== null,
    });
}

/**
 * Hook for polling new messages since a timestamp
 */
export function useNewMessages(since: string | null, options?: { enabled?: boolean; refetchInterval?: number }) {
    return useQuery({
        queryKey: messagesKeys.new(since || ''),
        queryFn: () => fetchNewMessages(since!),
        enabled: !!since && (options?.enabled ?? true),
        refetchInterval: options?.refetchInterval,
    });
}

/**
 * Hook for message sync operations (sync, deletions, sent)
 */
export function useMessageSync() {
    const queryClient = useQueryClient();

    // Invalidate message lists only, not individual details
    const invalidateMessageLists = () => {
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
    };

    const syncMutation = useMutation({
        mutationFn: (maxResults?: number) => syncMessages(maxResults),
        onSuccess: invalidateMessageLists,
    });

    const syncDeletionsMutation = useMutation({
        mutationFn: syncDeletions,
        onSuccess: invalidateMessageLists,
    });

    const syncSentMutation = useMutation({
        mutationFn: syncSentMessages,
        onSuccess: invalidateMessageLists,
    });

    return {
        sync: syncMutation.mutate,
        isSyncing: syncMutation.isPending,
        syncResult: syncMutation.data,

        syncDeletions: syncDeletionsMutation.mutate,
        isSyncingDeletions: syncDeletionsMutation.isPending,
        deletionsResult: syncDeletionsMutation.data,

        syncSent: syncSentMutation.mutate,
        isSyncingSent: syncSentMutation.isPending,
        sentResult: syncSentMutation.data,

        // Combined loading state
        isAnySyncing: syncMutation.isPending || syncDeletionsMutation.isPending || syncSentMutation.isPending,
    };
}

/**
 * Hook for message mutations (done, archive, delete, reprocess)
 */
export function useMessageMutations() {
    const queryClient = useQueryClient();

    // Invalidate message lists only, not individual details
    const invalidateMessageLists = () => {
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
    };

    // Invalidate specific message detail
    const invalidateMessageDetail = (messageId: number) => {
        queryClient.invalidateQueries({ queryKey: messagesKeys.detail(messageId) });
    };

    const doneMutation = useMutation({
        mutationFn: markMessageDone,
        onSuccess: (_, messageId) => {
            invalidateMessageLists();
            invalidateMessageDetail(messageId);
        },
    });

    const archiveMutation = useMutation({
        mutationFn: archiveMessage,
        onSuccess: (_, messageId) => {
            invalidateMessageLists();
            invalidateMessageDetail(messageId);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: deleteMessage,
        onSuccess: invalidateMessageLists,
    });

    const reprocessMutation = useMutation({
        mutationFn: reprocessMessage,
        onSuccess: (_, messageId) => {
            invalidateMessageLists();
            invalidateMessageDetail(messageId);
        },
    });

    return {
        markDone: doneMutation.mutate,
        isMarkingDone: doneMutation.isPending,

        archive: archiveMutation.mutate,
        isArchiving: archiveMutation.isPending,

        delete: deleteMutation.mutate,
        isDeleting: deleteMutation.isPending,

        reprocess: reprocessMutation.mutate,
        isReprocessing: reprocessMutation.isPending,
    };
}

// ================================
// Draft Reply Hooks
// ================================

export const draftReplyKeys = {
    all: ['draft-reply'] as const,
    message: (messageId: number) => [...draftReplyKeys.all, messageId] as const,
};

/**
 * Hook for generating a draft reply for a message
 */
export function useDraftReply() {
    const queryClient = useQueryClient();

    const mutation = useMutation({
        mutationFn: (messageId: number) => generateDraftReply(messageId),
        onError: () => Alert.alert('Error', 'Failed to generate draft reply'),
    });

    return {
        generate: mutation.mutate,
        generateAsync: mutation.mutateAsync,
        isGenerating: mutation.isPending,
        draft: mutation.data?.draft,
        contextUsed: mutation.data?.context_used,
        reset: mutation.reset,
    };
}

// ================================
// Scheduling Suggestions Hooks
// ================================

export const schedulingKeys = {
    all: ['scheduling'] as const,
    suggestions: () => [...schedulingKeys.all, 'suggestions'] as const,
    suggestionsByMessage: (messageId: number) => [...schedulingKeys.suggestions(), messageId] as const,
    suggestion: (id: number) => [...schedulingKeys.suggestions(), 'detail', id] as const,
};

/**
 * Hook for fetching scheduling suggestions for a message
 */
export function useSchedulingSuggestions(messageId: number | null, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: schedulingKeys.suggestionsByMessage(messageId!),
        queryFn: () => getSchedulingSuggestions(messageId!),
        enabled: messageId !== null && (options?.enabled ?? true),
    });
}

/**
 * Hook for fetching a single scheduling suggestion
 */
export function useSchedulingSuggestion(suggestionId: number | null) {
    return useQuery({
        queryKey: schedulingKeys.suggestion(suggestionId!),
        queryFn: () => getSchedulingSuggestion(suggestionId!),
        enabled: suggestionId !== null,
    });
}

/**
 * Hook for scheduling suggestion mutations (send, dismiss)
 */
export function useSchedulingMutations() {
    const queryClient = useQueryClient();

    const invalidateSuggestions = () => {
        queryClient.invalidateQueries({ queryKey: schedulingKeys.suggestions() });
    };

    const sendMutation = useMutation({
        mutationFn: ({ suggestionId, editedReply }: { suggestionId: number; editedReply?: string }) =>
            sendSchedulingReply(suggestionId, editedReply),
        onSuccess: invalidateSuggestions,
        onError: () => Alert.alert('Error', 'Failed to send scheduling reply'),
    });

    const dismissMutation = useMutation({
        mutationFn: (suggestionId: number) => dismissSchedulingSuggestion(suggestionId),
        onSuccess: invalidateSuggestions,
        onError: () => Alert.alert('Error', 'Failed to dismiss suggestion'),
    });

    return {
        send: sendMutation.mutate,
        sendAsync: sendMutation.mutateAsync,
        isSending: sendMutation.isPending,
        sendResult: sendMutation.data,

        dismiss: dismissMutation.mutate,
        dismissAsync: dismissMutation.mutateAsync,
        isDismissing: dismissMutation.isPending,

        isAnyPending: sendMutation.isPending || dismissMutation.isPending,
    };
}

/**
 * Hook for polling email processing status after sync.
 * Only polls when enabled. Caller disables when count hits 0.
 */
export function useProcessingStatus(enabled: boolean = false) {
    return useQuery({
        queryKey: ['processing-status'],
        queryFn: fetchProcessingStatus,
        enabled,
        refetchInterval: enabled ? 3000 : false,
        refetchIntervalInBackground: false,
        staleTime: 0,
    });
}
