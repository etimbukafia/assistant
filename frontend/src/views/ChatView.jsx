import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../utils/constants';
import { api } from '../utils/api';

// Icons
const SendIcon = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
);

const ArrowLeftIcon = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
    </svg>
);

const ChatBubbleIcon = () => (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
);

const HeartIcon = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
    </svg>
);

const PlusIcon = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
);

const CheckIcon = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
);

const XIcon = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
);

// Pending Action Card Component
const PendingActionCard = ({ action, onApprove, onReject, isLoading }) => {
    const actionLabels = {
        'create_task': 'Create Task',
        'draft_reply': 'Draft Reply',
        'update_principal_memory': 'Update Preference',
        'reschedule_meeting': 'Reschedule Meeting',
        'add_to_calendar': 'Add to Calendar',
        'cancel_meeting': 'Cancel Meeting'
    };

    const isHighRisk = action.action_type === 'cancel_meeting';

    return (
        <div className={`${isHighRisk ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'} border rounded-lg p-3 mt-2`}>
            <div className="flex items-center justify-between mb-2">
                <span className={`text-xs font-medium ${isHighRisk ? 'text-red-700' : 'text-amber-700'}`}>
                    {actionLabels[action.action_type] || action.action_type}
                </span>
                <span className={`text-xs ${isHighRisk ? 'text-red-500' : 'text-amber-500'}`}>
                    {isHighRisk ? 'High-risk action' : 'Awaiting approval'}
                </span>
            </div>

            <div className="text-sm text-gray-700 mb-3">
                {action.action_type === 'create_task' && (
                    <div>
                        <p className="font-medium">{action.action_data.title}</p>
                        {action.action_data.description && (
                            <p className="text-gray-500 text-xs mt-1">{action.action_data.description}</p>
                        )}
                    </div>
                )}
                {action.action_type === 'update_principal_memory' && (
                    <p>
                        Set <span className="font-medium">{action.action_data.key}</span> to "{action.action_data.value}"
                    </p>
                )}
                {action.action_type === 'draft_reply' && (
                    <p>Draft reply for: {action.action_data.email_subject}</p>
                )}
                {action.action_type === 'add_to_calendar' && (
                    <div>
                        <p className="font-medium">{action.action_data.title}</p>
                        <p className="text-gray-500 text-xs mt-1">
                            {new Date(action.action_data.start_time).toLocaleString()}
                        </p>
                        {action.action_data.participants?.length > 0 && (
                            <p className="text-gray-500 text-xs">
                                With: {action.action_data.participants.join(', ')}
                            </p>
                        )}
                    </div>
                )}
                {action.action_type === 'cancel_meeting' && (
                    <div>
                        <p className="font-medium text-red-700">{action.action_data.event_title}</p>
                        <p className="text-gray-500 text-xs mt-1">
                            {new Date(action.action_data.start_time).toLocaleString()}
                        </p>
                        {action.action_data.reason && (
                            <p className="text-gray-500 text-xs">Reason: {action.action_data.reason}</p>
                        )}
                    </div>
                )}
                {action.action_type === 'reschedule_meeting' && (
                    <div>
                        <p className="font-medium">{action.action_data.event_title}</p>
                        <p className="text-gray-500 text-xs mt-1">
                            New time: {new Date(action.action_data.new_start_time).toLocaleString()}
                        </p>
                    </div>
                )}
            </div>

            <div className="flex gap-2">
                <button
                    onClick={() => onApprove(action.id)}
                    disabled={isLoading}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-green-500 text-white text-sm rounded-lg hover:bg-green-600 disabled:opacity-50"
                >
                    <CheckIcon />
                    Approve
                </button>
                <button
                    onClick={() => onReject(action.id)}
                    disabled={isLoading}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300 disabled:opacity-50"
                >
                    <XIcon />
                    Reject
                </button>
            </div>
        </div>
    );
};

// Message Bubble Component
const MessageBubble = ({ message, pendingActions, onApprove, onReject, isLoadingAction }) => {
    const isUser = message.role === 'user';

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
            <div className={`max-w-[85%] ${isUser ? 'order-2' : 'order-1'}`}>
                <div
                    className={`rounded-2xl px-4 py-2.5 ${
                        isUser
                            ? 'bg-indigo-500 text-white rounded-br-md'
                            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md'
                    }`}
                >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>

                {/* Pending actions for this message */}
                {pendingActions && pendingActions.length > 0 && (
                    <div className="mt-2">
                        {pendingActions.map(action => (
                            <PendingActionCard
                                key={action.id}
                                action={action}
                                onApprove={onApprove}
                                onReject={onReject}
                                isLoading={isLoadingAction}
                            />
                        ))}
                    </div>
                )}

                <p className={`text-xs mt-1 ${isUser ? 'text-right text-gray-400' : 'text-gray-400'}`}>
                    {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
            </div>
        </div>
    );
};

// Session Type Selector
const SessionTypeSelector = ({ onSelect }) => {
    return (
        <div className="flex flex-col items-center justify-center h-full p-6">
            <ChatBubbleIcon />
            <h2 className="text-xl font-semibold text-gray-800 mt-4 mb-2">Start a Conversation</h2>
            <p className="text-gray-500 text-sm text-center mb-6">
                Choose how you'd like to chat
            </p>

            <div className="w-full space-y-3">
                <button
                    onClick={() => onSelect('command')}
                    className="w-full p-4 bg-white border border-gray-200 rounded-xl hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-left"
                >
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
                            <ChatBubbleIcon />
                        </div>
                        <div>
                            <p className="font-medium text-gray-800">Work Assistant</p>
                            <p className="text-xs text-gray-500">Ask about emails, tasks, calendar</p>
                        </div>
                    </div>
                </button>

                <button
                    onClick={() => onSelect('reflection')}
                    className="w-full p-4 bg-white border border-gray-200 rounded-xl hover:border-pink-300 hover:bg-pink-50 transition-colors text-left"
                >
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-pink-100 rounded-full flex items-center justify-center text-pink-500">
                            <HeartIcon />
                        </div>
                        <div>
                            <p className="font-medium text-gray-800">Reflection Space</p>
                            <p className="text-xs text-gray-500">Private, supportive conversation</p>
                        </div>
                    </div>
                </button>
            </div>

            <p className="text-xs text-gray-400 mt-6 text-center">
                Work chats are kept for 30 days. Reflection chats are private and deleted after 24 hours.
            </p>
        </div>
    );
};

// Main Chat View Component
const ChatView = ({ onNavigate, demoMode = false }) => {
    const [sessions, setSessions] = useState([]);
    const [currentSession, setCurrentSession] = useState(null);
    const [messages, setMessages] = useState([]);
    const [pendingActions, setPendingActions] = useState([]);
    const [inputText, setInputText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingAction, setIsLoadingAction] = useState(false);
    const [showSessionList, setShowSessionList] = useState(false);
    const [showTypeSelector, setShowTypeSelector] = useState(false);

    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Scroll to bottom of messages
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Load sessions on mount
    useEffect(() => {
        if (!demoMode) {
            loadSessions();
        }
    }, [demoMode]);

    const loadSessions = async () => {
        try {
            const res = await api.get('/chat/sessions');
            setSessions(res.sessions || []);

            // Auto-load most recent session if exists
            if (res.sessions && res.sessions.length > 0) {
                await loadSession(res.sessions[0].id);
            } else {
                setShowTypeSelector(true);
            }
        } catch (err) {
            console.error('Failed to load sessions:', err);
            setShowTypeSelector(true);
        }
    };

    const loadSession = async (sessionId) => {
        try {
            const res = await api.get(`/chat/sessions/${sessionId}`);
            setCurrentSession(res.session);
            setMessages(res.messages || []);
            setPendingActions(res.pending_actions || []);
            setShowTypeSelector(false);
            setShowSessionList(false);
        } catch (err) {
            console.error('Failed to load session:', err);
        }
    };

    const createSession = async (sessionType) => {
        if (demoMode) {
            const demoSession = {
                id: 'demo-' + Date.now(),
                session_type: sessionType,
                title: sessionType === 'command' ? 'Work Chat' : 'Reflection',
                created_at: new Date().toISOString(),
                last_activity_at: new Date().toISOString()
            };
            setCurrentSession(demoSession);
            setMessages([]);
            setPendingActions([]);
            setShowTypeSelector(false);
            return;
        }

        try {
            setIsLoading(true);
            const res = await api.post('/chat/sessions', {
                session_type: sessionType
            });
            setCurrentSession(res);
            setMessages([]);
            setPendingActions([]);
            setShowTypeSelector(false);
            setSessions(prev => [res, ...prev]);
        } catch (err) {
            console.error('Failed to create session:', err);
            alert('Failed to start chat. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const sendMessage = async () => {
        if (!inputText.trim() || !currentSession || isLoading) return;

        const userMessage = {
            id: Date.now(),
            session_id: currentSession.id,
            role: 'user',
            content: inputText.trim(),
            created_at: new Date().toISOString()
        };

        setMessages(prev => [...prev, userMessage]);
        setInputText('');
        setIsLoading(true);

        if (demoMode) {
            // Demo response
            setTimeout(() => {
                setMessages(prev => [...prev, {
                    id: Date.now(),
                    session_id: currentSession.id,
                    role: 'assistant',
                    content: currentSession.session_type === 'reflection'
                        ? "It sounds like you have a lot on your plate right now. That can be really stressful. Want to talk through what's on your mind?"
                        : "I can help with that! Based on your inbox, you have 3 emails needing replies and 2 urgent tasks. Would you like me to summarize the most important items?",
                    created_at: new Date().toISOString()
                }]);
                setIsLoading(false);
            }, 1000);
            return;
        }

        try {
            const res = await api.post(`/chat/sessions/${currentSession.id}/messages`, {
                content: userMessage.content
            });

            // Remove temp user message and add both from response
            setMessages(prev => {
                const withoutTemp = prev.filter(m => m.id !== userMessage.id);
                return [...withoutTemp,
                    { ...userMessage, id: res.id - 1 }, // Approximate user message ID
                    res
                ];
            });

            // Add any new pending actions
            if (res.pending_actions && res.pending_actions.length > 0) {
                setPendingActions(prev => [...prev, ...res.pending_actions]);
            }
        } catch (err) {
            console.error('Failed to send message:', err);
            // Remove the optimistic user message
            setMessages(prev => prev.filter(m => m.id !== userMessage.id));
            alert('Failed to send message. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleApproveAction = async (actionId) => {
        if (demoMode) {
            setPendingActions(prev => prev.filter(a => a.id !== actionId));
            return;
        }

        setIsLoadingAction(true);
        try {
            await api.post(`/chat/sessions/${currentSession.id}/approve/${actionId}`);
            setPendingActions(prev => prev.filter(a => a.id !== actionId));
        } catch (err) {
            console.error('Failed to approve action:', err);
            alert('Failed to approve action. Please try again.');
        } finally {
            setIsLoadingAction(false);
        }
    };

    const handleRejectAction = async (actionId) => {
        if (demoMode) {
            setPendingActions(prev => prev.filter(a => a.id !== actionId));
            return;
        }

        setIsLoadingAction(true);
        try {
            await api.post(`/chat/sessions/${currentSession.id}/reject/${actionId}`);
            setPendingActions(prev => prev.filter(a => a.id !== actionId));
        } catch (err) {
            console.error('Failed to reject action:', err);
            alert('Failed to reject action. Please try again.');
        } finally {
            setIsLoadingAction(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    // Session List View
    if (showSessionList) {
        return (
            <div className="flex flex-col h-full bg-gray-50">
                <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
                    <button
                        onClick={() => setShowSessionList(false)}
                        className="p-2 -ml-2 hover:bg-gray-100 rounded-full"
                    >
                        <ArrowLeftIcon />
                    </button>
                    <h1 className="font-semibold text-gray-800">Chat History</h1>
                    <button
                        onClick={() => {
                            setShowSessionList(false);
                            setShowTypeSelector(true);
                        }}
                        className="p-2 -mr-2 hover:bg-gray-100 rounded-full text-indigo-500"
                    >
                        <PlusIcon />
                    </button>
                </div>

                <div className="flex-1 overflow-auto p-4">
                    {sessions.length === 0 ? (
                        <p className="text-center text-gray-500 mt-8">No chat history yet</p>
                    ) : (
                        <div className="space-y-2">
                            {sessions.map(session => (
                                <button
                                    key={session.id}
                                    onClick={() => loadSession(session.id)}
                                    className="w-full p-3 bg-white rounded-lg border border-gray-200 hover:border-indigo-300 text-left"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                            session.session_type === 'reflection' ? 'bg-pink-100 text-pink-500' : 'bg-indigo-100 text-indigo-500'
                                        }`}>
                                            {session.session_type === 'reflection' ? <HeartIcon /> : <ChatBubbleIcon />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-medium text-gray-800 truncate">
                                                {session.title || (session.session_type === 'reflection' ? 'Reflection' : 'Work Chat')}
                                            </p>
                                            <p className="text-xs text-gray-500">
                                                {new Date(session.last_activity_at).toLocaleDateString()}
                                                {session.message_count && ` · ${session.message_count} messages`}
                                            </p>
                                        </div>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Type Selector View
    if (showTypeSelector || !currentSession) {
        return (
            <div className="flex flex-col h-full bg-gray-50">
                <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
                    <button
                        onClick={() => onNavigate('dashboard')}
                        className="p-2 -ml-2 hover:bg-gray-100 rounded-full"
                    >
                        <ArrowLeftIcon />
                    </button>
                    <h1 className="font-semibold text-gray-800">AI Chat</h1>
                    {sessions.length > 0 && (
                        <button
                            onClick={() => setShowSessionList(true)}
                            className="text-sm text-indigo-500 hover:text-indigo-600"
                        >
                            History
                        </button>
                    )}
                </div>

                <div className="flex-1">
                    <SessionTypeSelector onSelect={createSession} />
                </div>
            </div>
        );
    }

    // Chat View
    return (
        <div className="flex flex-col h-full bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b px-4 py-3 flex items-center gap-3">
                <button
                    onClick={() => onNavigate('dashboard')}
                    className="p-2 -ml-2 hover:bg-gray-100 rounded-full"
                >
                    <ArrowLeftIcon />
                </button>

                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    currentSession.session_type === 'reflection' ? 'bg-pink-100 text-pink-500' : 'bg-indigo-100 text-indigo-500'
                }`}>
                    {currentSession.session_type === 'reflection' ? <HeartIcon /> : <ChatBubbleIcon />}
                </div>

                <div className="flex-1">
                    <h1 className="font-semibold text-gray-800">
                        {currentSession.session_type === 'reflection' ? 'Reflection Space' : 'Work Assistant'}
                    </h1>
                    <p className="text-xs text-gray-500">
                        {currentSession.session_type === 'reflection' ? 'Private · 24hr' : 'Work · 30 days'}
                    </p>
                </div>

                <button
                    onClick={() => {
                        setCurrentSession(null);
                        setShowTypeSelector(true);
                    }}
                    className="p-2 hover:bg-gray-100 rounded-full text-gray-500"
                >
                    <PlusIcon />
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-auto p-4">
                {messages.length === 0 ? (
                    <div className="text-center text-gray-500 mt-8">
                        <p className="text-sm">
                            {currentSession.session_type === 'reflection'
                                ? "This is a safe space. What's on your mind?"
                                : "Ask me about your emails, tasks, or calendar."}
                        </p>
                    </div>
                ) : (
                    messages.map(message => (
                        <MessageBubble
                            key={message.id}
                            message={message}
                            pendingActions={pendingActions.filter(a => a.message_id === message.id)}
                            onApprove={handleApproveAction}
                            onReject={handleRejectAction}
                            isLoadingAction={isLoadingAction}
                        />
                    ))
                )}

                {isLoading && (
                    <div className="flex justify-start mb-3">
                        <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3">
                            <div className="flex gap-1">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="bg-white border-t p-3">
                <div className="flex items-end gap-2">
                    <textarea
                        ref={inputRef}
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder={
                            currentSession.session_type === 'reflection'
                                ? "How are you feeling?"
                                : "Ask about your inbox, tasks..."
                        }
                        className="flex-1 px-4 py-2.5 bg-gray-100 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-200 text-sm"
                        rows={1}
                        style={{ maxHeight: '120px' }}
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!inputText.trim() || isLoading}
                        className="p-2.5 bg-indigo-500 text-white rounded-full hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <SendIcon />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ChatView;
