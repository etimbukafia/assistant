/**
 * Chat Hooks with TanStack Query
 *
 * Server state management for chat sessions and messages.
 * Follows mobile instructions: use TanStack Query for server state.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
// Note: Install with: npx expo install @react-native-async-storage/async-storage
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert } from 'react-native';
import {
  ChatSession,
  ChatMessage,
  PendingAction,
  SessionType,
  SendMessageResponse,
  listSessions,
  createSession,
  getSession,
  deleteSession,
  getMessages,
  sendMessage,
  sendMessageWithPolling,
  approveAction,
  rejectAction,
} from '../services/chat';

// =============================================================================
// Query Keys
// =============================================================================

export const chatKeys = {
  all: ['chat'] as const,
  sessions: () => [...chatKeys.all, 'sessions'] as const,
  session: (id: string) => [...chatKeys.all, 'session', id] as const,
  messages: (sessionId: string) => [...chatKeys.all, 'messages', sessionId] as const,
  currentSessionId: () => [...chatKeys.all, 'currentSessionId'] as const,
};

// =============================================================================
// Storage Keys
// =============================================================================

const STORAGE_KEYS = {
  CURRENT_SESSION_ID: 'chat_current_session_id',
  LAST_MODE: 'chat_last_mode',
} as const;

// =============================================================================
// Persistence Helpers
// =============================================================================

export async function saveCurrentSessionId(sessionId: string | null): Promise<void> {
  if (sessionId) {
    await AsyncStorage.setItem(STORAGE_KEYS.CURRENT_SESSION_ID, sessionId);
  } else {
    await AsyncStorage.removeItem(STORAGE_KEYS.CURRENT_SESSION_ID);
  }
}

export async function loadCurrentSessionId(): Promise<string | null> {
  return AsyncStorage.getItem(STORAGE_KEYS.CURRENT_SESSION_ID);
}

export async function saveLastMode(mode: 'action' | 'reflection'): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEYS.LAST_MODE, mode);
}

export async function loadLastMode(): Promise<'action' | 'reflection'> {
  const mode = await AsyncStorage.getItem(STORAGE_KEYS.LAST_MODE);
  return (mode as 'action' | 'reflection') || 'action';
}

// =============================================================================
// Queries
// =============================================================================

/**
 * Fetch all chat sessions for the current user.
 */
export function useChatSessions(options?: { limit?: number; offset?: number; enabled?: boolean }) {
  const { limit = 20, offset = 0, enabled = true } = options || {};
  return useQuery({
    queryKey: chatKeys.sessions(),
    queryFn: () => listSessions(limit, offset),
    staleTime: 1000 * 30, // 30 seconds
    enabled,
  });
}

/**
 * Fetch a specific chat session with messages and pending actions.
 */
export function useChatSession(sessionId: string | null) {
  return useQuery({
    queryKey: chatKeys.session(sessionId || ''),
    queryFn: () => (sessionId ? getSession(sessionId) : null),
    enabled: !!sessionId,
    staleTime: 1000 * 10, // 10 seconds
  });
}

/**
 * Fetch messages for a session.
 */
export function useChatMessages(sessionId: string | null, limit: number = 50) {
  return useQuery({
    queryKey: chatKeys.messages(sessionId || ''),
    queryFn: () => (sessionId ? getMessages(sessionId, limit) : []),
    enabled: !!sessionId,
    staleTime: 1000 * 5, // 5 seconds
  });
}

/**
 * Load persisted current session ID.
 */
export function usePersistedSessionId() {
  return useQuery({
    queryKey: chatKeys.currentSessionId(),
    queryFn: loadCurrentSessionId,
    staleTime: Infinity, // Only fetch once
  });
}

// =============================================================================
// Mutations
// =============================================================================

/**
 * Create a new chat session.
 */
export function useCreateSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sessionType: SessionType) => {
      const session = await createSession(sessionType);
      // Persist the new session ID
      await saveCurrentSessionId(session.id);
      return session;
    },
    onSuccess: (newSession) => {
      // Add to sessions list
      queryClient.setQueryData<ChatSession[]>(chatKeys.sessions(), (old) =>
        old ? [newSession, ...old] : [newSession]
      );
      // Update current session ID cache
      queryClient.setQueryData(chatKeys.currentSessionId(), newSession.id);
    },
  });
}

/**
 * Delete a chat session.
 */
export function useDeleteSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sessionId: string) => {
      await deleteSession(sessionId);
      // Clear persisted session if it was the current one
      const currentId = await loadCurrentSessionId();
      if (currentId === sessionId) {
        await saveCurrentSessionId(null);
      }
      return sessionId;
    },
    onSuccess: (deletedId) => {
      // Remove from sessions list
      queryClient.setQueryData<ChatSession[]>(chatKeys.sessions(), (old) =>
        old ? old.filter((s) => s.id !== deletedId) : []
      );
      // Clear session cache
      queryClient.removeQueries({ queryKey: chatKeys.session(deletedId) });
      queryClient.removeQueries({ queryKey: chatKeys.messages(deletedId) });
    },
  });
}

/**
 * Approve a pending action.
 */
export function useApproveAction(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (actionId: string) => approveAction(sessionId, actionId),
    onSuccess: () => {
      // Refetch session to get updated pending actions
      queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
    },
  });
}

/**
 * Reject a pending action.
 */
export function useRejectAction(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (actionId: string) => rejectAction(sessionId, actionId),
    onSuccess: () => {
      // Refetch session to get updated pending actions
      queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
    },
  });
}

/**
 * Send a message to a chat session.
 *
 * Handles both synchronous and asynchronous responses:
 * - Sync: Response is returned immediately
 * - Async: Polls for completion automatically
 */
export function useSendMessage(sessionId: string) {
  const queryClient = useQueryClient();
  const addMessage = useAddMessageToCache(sessionId);

  return useMutation({
    mutationFn: async (content: string) => {
      // Optimistically add user message to cache
      const userMessage: ChatMessage = {
        id: Date.now(), // Temporary ID
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      addMessage(userMessage);

      // Send message and handle sync/async response
      return new Promise<{ response: string; pendingActions: PendingAction[] }>(
        (resolve, reject) => {
          sendMessageWithPolling(sessionId, content, {
            onComplete: (response, pendingActions) => {
              // Add assistant response to cache
              const assistantMessage: ChatMessage = {
                id: Date.now() + 1,
                role: 'assistant',
                content: response,
                created_at: new Date().toISOString(),
              };
              addMessage(assistantMessage);
              resolve({ response, pendingActions });
            },
            onError: (error) => {
              reject(new Error(error));
            },
            onProcessing: (jobId, messageId) => {
              // Could show "typing" indicator here
              console.log(`Processing job ${jobId} for message ${messageId}`);
            },
          });
        }
      );
    },
    onSuccess: () => {
      // Refresh session to get updated state
      queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
    onError: (error) => {
      Alert.alert('Error', error.message || 'Failed to send message');
      // Invalidate to remove optimistic message
      queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
    },
  });
}

/**
 * Simple send message mutation (without polling, for reflection mode).
 */
export function useSendMessageSync(sessionId: string) {
  const queryClient = useQueryClient();
  const addMessage = useAddMessageToCache(sessionId);

  return useMutation({
    mutationFn: async (content: string) => {
      // Optimistically add user message
      const userMessage: ChatMessage = {
        id: Date.now(),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      addMessage(userMessage);

      const result = await sendMessage(sessionId, content);

      if (result.status === 'complete' && result.response) {
        // Add assistant response
        const assistantMessage: ChatMessage = {
          id: result.message_id,
          role: 'assistant',
          content: result.response,
          created_at: new Date().toISOString(),
        };
        addMessage(assistantMessage);
      }

      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
    },
    onError: (error) => {
      Alert.alert('Error', 'Failed to send message');
      queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
    },
  });
}

// =============================================================================
// Cache Helpers
// =============================================================================

/**
 * Invalidate all chat-related queries.
 */
export function useInvalidateChat() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: chatKeys.all });
  };
}

/**
 * Add a message to the cache optimistically.
 */
export function useAddMessageToCache(sessionId: string) {
  const queryClient = useQueryClient();

  return (message: ChatMessage) => {
    queryClient.setQueryData<ChatMessage[]>(chatKeys.messages(sessionId), (old) =>
      old ? [...old, message] : [message]
    );
  };
}

/**
 * Update a message in the cache.
 */
export function useUpdateMessageInCache(sessionId: string) {
  const queryClient = useQueryClient();

  return (messageId: number, updates: Partial<ChatMessage>) => {
    queryClient.setQueryData<ChatMessage[]>(chatKeys.messages(sessionId), (old) =>
      old
        ? old.map((m) => (m.id === messageId ? { ...m, ...updates } : m))
        : []
    );
  };
}
