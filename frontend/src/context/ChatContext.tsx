"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';
import { useChat, loadLastMode, saveLastMode } from '@/hooks/useChat';

interface ChatContextType {
    isOpen: boolean;
    setIsOpen: (isOpen: boolean) => void;
    mode: 'action' | 'reflection';
    setMode: (mode: 'action' | 'reflection') => void;
    toggleChat: () => void;
    currentSessionId: string | null;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({ children }: { children: React.ReactNode }) {
    const [isOpen, setIsOpen] = useState(false);
    const [mode, setModeState] = useState<'action' | 'reflection'>('action');
    const { currentSessionId } = useChat();

    // Load persisted mode on mount
    useEffect(() => {
        setModeState(loadLastMode());
    }, []);

    const setMode = (newMode: 'action' | 'reflection') => {
        setModeState(newMode);
        saveLastMode(newMode);
    };

    const toggleChat = () => setIsOpen(prev => !prev);

    return (
        <ChatContext.Provider value={{
            isOpen,
            setIsOpen,
            mode,
            setMode,
            toggleChat,
            currentSessionId
        }}>
            {children}
            {/* OmniChatOverlay will be mounted here in the layout or used via portal */}
        </ChatContext.Provider>
    );
}

export function useChatContext() {
    const context = useContext(ChatContext);
    if (context === undefined) {
        throw new Error('useChatContext must be used within a ChatProvider');
    }
    return context;
}
