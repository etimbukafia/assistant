/**
 * Chat Context - UI State Only
 *
 * Manages UI state for chat:
 * - Chat overlay visibility
 * - Current mode (action/reflection)
 * - Current session ID
 *
 * Session data (messages, pending actions) comes from TanStack Query hooks.
 * This separation ensures proper state isolation and prevents dual-state issues.
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  ReactNode,
} from 'react';
import { saveCurrentSessionId, loadCurrentSessionId, saveLastMode, loadLastMode } from '../hooks/useChat';

// =============================================================================
// Types
// =============================================================================

export type ChatMode = 'action' | 'reflection';

interface ChatContextType {
  // UI State
  isChatOpen: boolean;
  chatMode: ChatMode;
  currentSessionId: string | null;

  // UI Actions
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  setChatMode: (mode: ChatMode) => void;
  setCurrentSessionId: (id: string | null) => void;

  // Helper to clear session when mode changes
  switchModeAndClearSession: (mode: ChatMode) => void;
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
  const [chatMode, setChatModeInternal] = useState<ChatMode>('action');
  const [currentSessionId, setCurrentSessionIdInternal] = useState<string | null>(null);

  // Load persisted state on mount
  useEffect(() => {
    const loadPersistedState = async () => {
      const [sessionId, mode] = await Promise.all([
        loadCurrentSessionId(),
        loadLastMode(),
      ]);
      if (sessionId) setCurrentSessionIdInternal(sessionId);
      setChatModeInternal(mode);
    };
    loadPersistedState();
  }, []);

  // ==========================================================================
  // UI Actions
  // ==========================================================================

  const openChat = useCallback(() => setIsChatOpen(true), []);
  const closeChat = useCallback(() => setIsChatOpen(false), []);
  const toggleChat = useCallback(() => setIsChatOpen((prev) => !prev), []);

  const setChatMode = useCallback((mode: ChatMode) => {
    setChatModeInternal(mode);
    saveLastMode(mode);
  }, []);

  const setCurrentSessionId = useCallback((id: string | null) => {
    setCurrentSessionIdInternal(id);
    saveCurrentSessionId(id);
  }, []);

  // When mode changes, clear current session to ensure proper isolation
  // Next message will create a new session with the correct type
  const switchModeAndClearSession = useCallback((mode: ChatMode) => {
    if (mode !== chatMode) {
      setCurrentSessionIdInternal(null);
      saveCurrentSessionId(null);
      setChatModeInternal(mode);
      saveLastMode(mode);
    }
  }, [chatMode]);

  // ==========================================================================
  // Context Value
  // ==========================================================================

  const value: ChatContextType = {
    // UI State
    isChatOpen,
    chatMode,
    currentSessionId,

    // UI Actions
    openChat,
    closeChat,
    toggleChat,
    setChatMode,
    setCurrentSessionId,
    switchModeAndClearSession,
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

// Re-export DisplayMessage type for backward compatibility
export interface DisplayMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  status?: 'sending' | 'processing' | 'complete' | 'error';
  jobId?: string;
  error?: string;
}

export default ChatProvider;
