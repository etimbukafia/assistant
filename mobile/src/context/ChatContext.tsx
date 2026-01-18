import React, { createContext, useContext, useState, ReactNode } from 'react';

interface ChatContextType {
    isChatOpen: boolean;
    chatMode: 'action' | 'reflection';
    openChat: () => void;
    closeChat: () => void;
    toggleChat: () => void;
    setChatMode: (mode: 'action' | 'reflection') => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

interface ChatProviderProps {
    children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const [isChatOpen, setIsChatOpen] = useState(false);
    const [chatMode, setChatMode] = useState<'action' | 'reflection'>('action');

    const openChat = () => setIsChatOpen(true);
    const closeChat = () => setIsChatOpen(false);
    const toggleChat = () => setIsChatOpen(prev => !prev);

    return (
        <ChatContext.Provider value={{
            isChatOpen,
            chatMode,
            openChat,
            closeChat,
            toggleChat,
            setChatMode,
        }}>
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = (): ChatContextType => {
    const context = useContext(ChatContext);
    if (!context) {
        throw new Error('useChat must be used within a ChatProvider');
    }
    return context;
};

export default ChatProvider;
