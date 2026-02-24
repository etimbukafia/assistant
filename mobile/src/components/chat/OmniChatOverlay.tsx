/**
 * OmniChat Overlay
 *
 * Quick chat widget that slides from top.
 * Uses TanStack Query for session data (unified state management).
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    StyleSheet,
    View,
    TextInput,
    TouchableOpacity,
    KeyboardAvoidingView,
    Platform,
    Pressable,
    ScrollView,
    ActivityIndicator,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from '../ui/DonnaText';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withTiming,
    Easing,
    runOnJS,
} from 'react-native-reanimated';
import { useChat, DisplayMessage } from '../../context/ChatContext';
import {
    useChatSession,
    useCreateSession,
    chatKeys,
} from '../../hooks/useChat';
import { sendMessageWithPolling, SessionType } from '../../services/chat';
import { useQueryClient } from '@tanstack/react-query';

const OVERLAY_HEIGHT = 420;

interface OmniChatOverlayProps {
    isVisible: boolean;
    onClose: () => void;
}

// Message Bubble Component
const MessageBubble: React.FC<{ message: DisplayMessage; accentColor: string }> = ({
    message,
    accentColor,
}) => {
    const isUser = message.role === 'user';
    const isProcessing = message.status === 'processing' || message.status === 'sending';
    const isError = message.status === 'error';

    return (
        <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
            {isProcessing && !message.content ? (
                <View style={styles.processingBubble}>
                    <ActivityIndicator size="small" color={accentColor} />
                </View>
            ) : (
                <DonnaText
                    style={[
                        styles.messageText,
                        isUser && styles.userMessageText,
                        isError && styles.errorMessageText,
                    ]}
                >
                    {message.content}
                </DonnaText>
            )}
        </View>
    );
};

export const OmniChatOverlay: React.FC<OmniChatOverlayProps> = ({
    isVisible,
    onClose,
}) => {
    const {
        chatMode,
        switchModeAndClearSession,
        currentSessionId,
        setCurrentSessionId,
    } = useChat();

    const queryClient = useQueryClient();

    // TanStack Query hooks
    const { data: sessionData } = useChatSession(currentSessionId);
    const createSession = useCreateSession();

    // Local state for optimistic updates
    const [localMessages, setLocalMessages] = useState<DisplayMessage[]>([]);
    const [inputText, setInputText] = useState('');
    const [isMounted, setIsMounted] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [isSending, setIsSending] = useState(false);

    // Track current session for race condition prevention
    const currentSessionRef = useRef<string | null>(null);
    const pollingCleanupRef = useRef<(() => void) | null>(null);

    // Sync server messages to local state (skip while sending to preserve optimistic messages)
    useEffect(() => {
        if (isSending) return;
        if (sessionData?.messages) {
            // Filter out system messages and ensure role type compatibility
            const displayMessages = sessionData.messages
                .filter((m) => m.role === 'user' || m.role === 'assistant')
                .map((m) => ({
                    ...m,
                    role: m.role as 'user' | 'assistant',
                    status: 'complete' as const,
                }));
            setLocalMessages(displayMessages);
        } else if (!currentSessionId) {
            setLocalMessages([]);
        }
    }, [sessionData?.messages, currentSessionId, isSending]);

    // Update session ref for race condition checks
    useEffect(() => {
        currentSessionRef.current = currentSessionId;
    }, [currentSessionId]);

    // Cleanup polling on unmount or session change
    useEffect(() => {
        return () => {
            if (pollingCleanupRef.current) {
                pollingCleanupRef.current();
                pollingCleanupRef.current = null;
            }
        };
    }, [currentSessionId]);

    // Animation values - slides from top
    const translateY = useSharedValue(-OVERLAY_HEIGHT - 50);
    const opacity = useSharedValue(0);
    const shadowOpacity = useSharedValue(0);

    const handleExitComplete = useCallback(() => {
        setIsMounted(false);
    }, []);

    useEffect(() => {
        if (isVisible) {
            setIsMounted(true);
            translateY.value = withSpring(0, {
                damping: 18,
                stiffness: 90,
                mass: 1.2,
            });
            opacity.value = withTiming(1, { duration: 250 });
            shadowOpacity.value = withTiming(0.25, { duration: 400 });
        } else {
            translateY.value = withTiming(-OVERLAY_HEIGHT - 50, {
                duration: 280,
                easing: Easing.in(Easing.cubic),
            }, (finished) => {
                if (finished) {
                    runOnJS(handleExitComplete)();
                }
            });
            opacity.value = withTiming(0, { duration: 200 });
            shadowOpacity.value = withTiming(0, { duration: 200 });
        }
    }, [isVisible]);

    const animatedOverlayStyle = useAnimatedStyle(() => ({
        transform: [{ translateY: translateY.value }],
    }));

    const backdropStyle = useAnimatedStyle(() => ({
        opacity: opacity.value,
    }));

    const shadowStyle = useAnimatedStyle(() => ({
        opacity: shadowOpacity.value,
    }));

    // Mode Toggle - clears session for proper isolation
    const toggleMode = () => {
        const newMode = chatMode === 'action' ? 'reflection' : 'action';
        switchModeAndClearSession(newMode);
    };

    // Handle send message
    const handleSend = async () => {
        const text = inputText.trim();
        if (!text || isSending) return;

        setInputText('');
        setIsSending(true);

        // Get or create session
        let sessionId = currentSessionId;
        if (!sessionId) {
            try {
                const sessionType: SessionType = chatMode === 'reflection' ? 'reflection' : 'command';
                const newSession = await createSession.mutateAsync(sessionType);
                sessionId = newSession.id;
                setCurrentSessionId(sessionId);
            } catch (error) {
                console.error('Failed to create session:', error);
                setIsSending(false);
                return;
            }
        }

        // Store session ID for race condition check
        const targetSessionId = sessionId;

        // Add user message optimistically
        const userMessage: DisplayMessage = {
            id: Date.now(),
            role: 'user',
            content: text,
            created_at: new Date().toISOString(),
            status: 'complete',
        };
        setLocalMessages((prev) => [...prev, userMessage]);

        // Add placeholder for assistant response
        const placeholderId = Date.now() + 1;
        const placeholderMessage: DisplayMessage = {
            id: placeholderId,
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            status: 'sending',
        };
        setLocalMessages((prev) => [...prev, placeholderMessage]);
        setIsTyping(true);

        // Cleanup previous polling
        if (pollingCleanupRef.current) {
            pollingCleanupRef.current();
            pollingCleanupRef.current = null;
        }

        // Track mount state for cleanup
        let isMountedLocal = true;

        // Send with polling support
        const cleanup = await sendMessageWithPolling(targetSessionId, text, {
            onComplete: (response, pendingActions) => {
                // Race condition check: only update if still on same session
                if (!isMountedLocal || currentSessionRef.current !== targetSessionId) {
                    console.log('Ignoring response for different session');
                    return;
                }

                setLocalMessages((prev) =>
                    prev.map((m) =>
                        m.id === placeholderId
                            ? { ...m, content: response, status: 'complete' as const }
                            : m
                    )
                );
                // Invalidate to sync pending actions
                queryClient.invalidateQueries({ queryKey: chatKeys.session(targetSessionId) });
                setIsTyping(false);
                setIsSending(false);
            },
            onError: (error) => {
                if (!isMountedLocal || currentSessionRef.current !== targetSessionId) {
                    return;
                }

                setLocalMessages((prev) =>
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
                setIsSending(false);
            },
            onProcessing: (jobId, messageId) => {
                if (!isMountedLocal || currentSessionRef.current !== targetSessionId) {
                    return;
                }

                setLocalMessages((prev) =>
                    prev.map((m) =>
                        m.id === placeholderId
                            ? { ...m, id: messageId, status: 'processing' as const, jobId }
                            : m
                    )
                );
            },
        });

        // Store cleanup
        pollingCleanupRef.current = () => {
            isMountedLocal = false;
            cleanup();
        };
    };

    const isAction = chatMode === 'action';
    const accentColor = isAction ? Colors.accentSecondary : Colors.success;
    const placeholderText = isAction
        ? "How can I help you execute?"
        : "What's on your mind?";

    if (!isVisible && !isMounted) {
        return null;
    }

    return (
        <>
            {/* Backdrop with tap-to-dismiss */}
            <Animated.View style={[styles.backdrop, backdropStyle]} pointerEvents={isVisible ? 'auto' : 'none'}>
                <Pressable style={styles.backdropTouch} onPress={onClose} />
            </Animated.View>

            {/* Shadow Layer */}
            <Animated.View style={[styles.shadowLayer, shadowStyle]} pointerEvents="none" />

            {/* The Monolith - slides from TOP */}
            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                style={styles.container}
                pointerEvents="box-none"
            >
                <Animated.View style={[styles.monolithContainer, animatedOverlayStyle]}>
                    <BlurView intensity={95} tint="light" style={styles.blurView}>

                        {/* Pull Handle */}
                        <View style={styles.pullHandle}>
                            <View style={styles.handleBar} />
                        </View>

                        {/* Header / Mode Toggle */}
                        <View style={styles.header}>
                            <View style={styles.modeToggleContainer}>
                                <TouchableOpacity onPress={toggleMode} style={styles.modeButton}>
                                    <Ionicons
                                        name={isAction ? "flash" : "leaf"}
                                        size={20}
                                        color={accentColor}
                                    />
                                    <DonnaText style={[styles.modeText, { color: accentColor }]}>
                                        {isAction ? "ACTION" : "REFLECTION"}
                                    </DonnaText>
                                </TouchableOpacity>

                                <TouchableOpacity onPress={toggleMode} style={styles.switchIcon}>
                                    <Ionicons name="swap-horizontal" size={16} color={Colors.textMuted} />
                                </TouchableOpacity>
                            </View>

                            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
                                <Ionicons name="chevron-up" size={24} color={Colors.textSecondary} />
                            </TouchableOpacity>
                        </View>

                        {/* Chat Content Area */}
                        <View style={styles.contentArea}>
                            {localMessages.length === 0 ? (
                                <DonnaText style={styles.placeholderMessage}>
                                    {isAction
                                        ? "I'm ready to help you clear your inbox, schedule meetings, or organize tasks."
                                        : "Let's pause. Reflect on your day, capture thoughts, or clear your mind."}
                                </DonnaText>
                            ) : (
                                <ScrollView
                                    style={styles.messagesContainer}
                                    contentContainerStyle={styles.messagesContent}
                                    showsVerticalScrollIndicator={false}
                                >
                                    {localMessages.map((msg) => (
                                        <MessageBubble key={msg.id} message={msg} accentColor={accentColor} />
                                    ))}
                                    {isTyping && (
                                        <View style={styles.typingIndicator}>
                                            <ActivityIndicator size="small" color={accentColor} />
                                            <DonnaText style={styles.typingText}>Thinking...</DonnaText>
                                        </View>
                                    )}
                                </ScrollView>
                            )}
                        </View>

                        {/* Input Area */}
                        <View style={styles.inputContainer}>
                            <TextInput
                                style={styles.input}
                                placeholder={placeholderText}
                                placeholderTextColor={Colors.textMuted}
                                value={inputText}
                                onChangeText={setInputText}
                                multiline
                                maxLength={500}
                                editable={!isSending}
                            />
                            <TouchableOpacity
                                style={[
                                    styles.sendButton,
                                    { backgroundColor: inputText.trim() && !isSending ? accentColor : Colors.border }
                                ]}
                                disabled={!inputText.trim() || isSending}
                                onPress={handleSend}
                            >
                                {isSending ? (
                                    <ActivityIndicator size="small" color="#FFF" />
                                ) : (
                                    <Ionicons name="arrow-up" size={20} color="#FFF" />
                                )}
                            </TouchableOpacity>
                        </View>

                    </BlurView>
                </Animated.View>
            </KeyboardAvoidingView>
        </>
    );
};

const styles = StyleSheet.create({
    backdrop: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'rgba(0,0,0,0.15)',
        zIndex: 998,
    },
    backdropTouch: {
        flex: 1,
    },
    shadowLayer: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: OVERLAY_HEIGHT + 100,
        backgroundColor: 'transparent',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 15 },
        shadowOpacity: 1,
        shadowRadius: 30,
        elevation: 15,
        zIndex: 999,
    },
    container: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        overflow: 'hidden',
        pointerEvents: 'box-none',
    },
    monolithContainer: {
        marginHorizontal: Spacing.md,
        marginTop: 60,
        borderRadius: Radius.xl,
        overflow: 'hidden',
        height: OVERLAY_HEIGHT,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.2,
        shadowRadius: 20,
        elevation: 12,
    },
    blurView: {
        flex: 1,
        backgroundColor: 'rgba(255, 255, 255, 0.88)',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.5)',
    },
    pullHandle: {
        alignItems: 'center',
        paddingVertical: Spacing.sm,
    },
    handleBar: {
        width: 40,
        height: 4,
        borderRadius: 2,
        backgroundColor: 'rgba(0,0,0,0.1)',
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingBottom: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(0,0,0,0.05)',
    },
    modeToggleContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
    },
    modeButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
        paddingVertical: 6,
        paddingHorizontal: 12,
        borderRadius: Radius.full,
        backgroundColor: 'rgba(255,255,255,0.6)',
        borderWidth: 1,
        borderColor: 'rgba(0,0,0,0.05)',
    },
    modeText: {
        fontSize: 12,
        fontWeight: '700',
        letterSpacing: 0.5,
    },
    switchIcon: {
        opacity: 0.6,
    },
    closeButton: {
        padding: 4,
    },
    contentArea: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
    },
    placeholderMessage: {
        textAlign: 'center',
        color: Colors.textSecondary,
        fontSize: 15,
        lineHeight: 22,
        fontFamily: 'Inter_400Regular',
        paddingHorizontal: Spacing.md,
    },
    messagesContainer: {
        flex: 1,
        width: '100%',
    },
    messagesContent: {
        paddingVertical: Spacing.sm,
        gap: Spacing.sm,
    },
    messageBubble: {
        maxWidth: '85%',
        paddingVertical: Spacing.sm,
        paddingHorizontal: Spacing.md,
        borderRadius: Radius.lg,
    },
    userBubble: {
        alignSelf: 'flex-end',
        backgroundColor: Colors.accentSecondary,
    },
    assistantBubble: {
        alignSelf: 'flex-start',
        backgroundColor: 'rgba(0,0,0,0.05)',
    },
    messageText: {
        fontSize: 14,
        lineHeight: 20,
        color: Colors.textPrimary,
    },
    userMessageText: {
        color: '#FFFFFF',
    },
    errorMessageText: {
        color: Colors.error,
    },
    processingBubble: {
        paddingVertical: Spacing.xs,
        paddingHorizontal: Spacing.sm,
    },
    typingIndicator: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        alignSelf: 'flex-start',
        paddingVertical: Spacing.xs,
        paddingHorizontal: Spacing.sm,
    },
    typingText: {
        fontSize: 12,
        color: Colors.textMuted,
    },
    inputContainer: {
        flexDirection: 'row',
        alignItems: 'flex-end',
        padding: Spacing.md,
        gap: Spacing.sm,
        borderTopWidth: 1,
        borderTopColor: 'rgba(0,0,0,0.05)',
        backgroundColor: 'rgba(255,255,255,0.5)',
    },
    input: {
        flex: 1,
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: Colors.textPrimary,
        maxHeight: 100,
        paddingVertical: 10,
        paddingHorizontal: 4,
    },
    sendButton: {
        width: 38,
        height: 38,
        borderRadius: 19,
        justifyContent: 'center',
        alignItems: 'center',
    },
});

export default OmniChatOverlay;
