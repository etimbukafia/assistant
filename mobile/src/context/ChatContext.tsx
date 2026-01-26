/**
 * Chat Context
 *
 * Manages chat state, sessions, and message handling.
 * Supports both synchronous and asynchronous processing paths.
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  ReactNode,
} from 'react';
import {
  ChatSession,
  ChatMessage,
  PendingAction,
  SessionType,
  createSession,
  getSession,
  sendMessageWithPolling,
  approveAction,
  rejectAction,
  listSessions,
} from '../services/chat';

// =============================================================================
// Types
// =============================================================================

type ChatMode = 'action' | 'reflection';
type MessageStatus = 'sending' | 'processing' | 'complete' | 'error';

export interface DisplayMessage extends ChatMessage {
  status?: MessageStatus;
  jobId?: string;
  error?: string;
}

interface ChatContextType {
  // UI State
  isChatOpen: boolean;
  chatMode: ChatMode;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  setChatMode: (mode: ChatMode) => void;

  // Session State
  currentSession: ChatSession | null;
  sessions: ChatSession[];
  isLoadingSessions: boolean;

  // Message State
  messages: DisplayMessage[];
  isTyping: boolean;

  // Pending Actions
  pendingActions: PendingAction[];

  // Actions
  startNewSession: (mode?: ChatMode) => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  handleApproveAction: (actionId: string) => Promise<void>;
  handleRejectAction: (actionId: string) => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

interface ChatProviderProps {
  children: ReactNode;
}

// =============================================================================
// Provider
// =============================================================================

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  // UI State
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>('action');

  // Session State
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);

  // Message State
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  // Pending Actions
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);

  // Cleanup refs for polling
  const pollingCleanupRef = useRef<(() => void) | null>(null);

  // ==========================================================================
  // UI Actions
  // ==========================================================================

  const openChat = useCallback(() => setIsChatOpen(true), []);
  const closeChat = useCallback(() => setIsChatOpen(false), []);
  const toggleChat = useCallback(() => setIsChatOpen((prev) => !prev), []);

  // ==========================================================================
  // Session Actions
  // ==========================================================================

  const refreshSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const fetchedSessions = await listSessions();
      setSessions(fetchedSessions);
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  const startNewSession = useCallback(async (mode?: ChatMode) => {
    const sessionType: SessionType = mode === 'reflection' ? 'reflection' : 'command';

    try {
      const session = await createSession(sessionType);
      setCurrentSession(session);
      setMessages([]);
      setPendingActions([]);

      // Update mode if specified
      if (mode) {
        setChatMode(mode);
      }
    } catch (error) {
      console.error('Failed to create session:', error);
      throw error;
    }
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const { session, messages: fetchedMessages, pending_actions } = await getSession(sessionId);
      setCurrentSession(session);
      setMessages(fetchedMessages.map((m) => ({ ...m, status: 'complete' as const })));
      setPendingActions(pending_actions);

      // Set mode based on session type
      setChatMode(session.session_type === 'reflection' ? 'reflection' : 'action');
    } catch (error) {
      console.error('Failed to load session:', error);
      throw error;
    }
  }, []);

  // ==========================================================================
  // Message Actions
  // ==========================================================================

  const sendMessage = useCallback(
    async (content: string) => {
      if (!currentSession) {
        // Create a new session if none exists
        await startNewSession(chatMode);
      }

      const sessionId = currentSession?.id;
      if (!sessionId) {
        console.error('No session available');
        return;
      }

      // Add user message optimistically
      const userMessage: DisplayMessage = {
        id: Date.now(), // Temporary ID
        role: 'user',
        content,
        created_at: new Date().toISOString(),
        status: 'complete',
      };
      setMessages((prev) => [...prev, userMessage]);

      // Add placeholder for assistant response
      const placeholderId = Date.now() + 1;
      const placeholderMessage: DisplayMessage = {
        id: placeholderId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        status: 'sending',
      };
      setMessages((prev) => [...prev, placeholderMessage]);
      setIsTyping(true);

      // Clean up any previous polling
      if (pollingCleanupRef.current) {
        pollingCleanupRef.current();
        pollingCleanupRef.current = null;
      }

      // Send message with polling support
      const cleanup = await sendMessageWithPolling(sessionId, content, {
        onComplete: (response, newPendingActions) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === placeholderId
                ? { ...m, content: response, status: 'complete' as const }
                : m
            )
          );
          setPendingActions((prev) => [...prev, ...newPendingActions]);
          setIsTyping(false);
        },
        onError: (error) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === placeholderId
                ? {
                    ...m,
                    content: 'Sorry, I encountered an error. Please try again.',
                    status: 'error' as const,
                    error,
                  }
                : m
            )
          );
          setIsTyping(false);
        },
        onProcessing: (jobId, messageId) => {
          // Update placeholder with job info
          setMessages((prev) =>
            prev.map((m) =>
              m.id === placeholderId
                ? { ...m, id: messageId, status: 'processing' as const, jobId }
                : m
            )
          );
        },
      });

      pollingCleanupRef.current = cleanup;
    },
    [currentSession, chatMode, startNewSession]
  );

  // ==========================================================================
  // Action Handlers
  // ==========================================================================

  const handleApproveAction = useCallback(
    async (actionId: string) => {
      if (!currentSession) return;

      try {
        const result = await approveAction(currentSession.id, actionId);
        if (result.success) {
          setPendingActions((prev) =>
            prev.map((a) => (a.id === actionId ? { ...a, status: 'approved' as const } : a))
          );
        }
      } catch (error) {
        console.error('Failed to approve action:', error);
      }
    },
    [currentSession]
  );

  const handleRejectAction = useCallback(
    async (actionId: string) => {
      if (!currentSession) return;

      try {
        const result = await rejectAction(currentSession.id, actionId);
        if (result.success) {
          setPendingActions((prev) =>
            prev.map((a) => (a.id === actionId ? { ...a, status: 'rejected' as const } : a))
          );
        }
      } catch (error) {
        console.error('Failed to reject action:', error);
      }
    },
    [currentSession]
  );

  // ==========================================================================
  // Cleanup
  // ==========================================================================

  useEffect(() => {
    return () => {
      if (pollingCleanupRef.current) {
        pollingCleanupRef.current();
      }
    };
  }, []);

  // ==========================================================================
  // Context Value
  // ==========================================================================

  const value: ChatContextType = {
    // UI State
    isChatOpen,
    chatMode,
    openChat,
    closeChat,
    toggleChat,
    setChatMode,

    // Session State
    currentSession,
    sessions,
    isLoadingSessions,

    // Message State
    messages,
    isTyping,

    // Pending Actions
    pendingActions,

    // Actions
    startNewSession,
    loadSession,
    refreshSessions,
    sendMessage,
    handleApproveAction,
    handleRejectAction,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};

// =============================================================================
// Hook
// =============================================================================

export const useChat = (): ChatContextType => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};

export default ChatProvider;
