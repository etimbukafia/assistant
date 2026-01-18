import React, { useState, useRef, useEffect } from 'react';
import { StyleSheet, View, TextInput, TouchableOpacity, FlatList, KeyboardAvoidingView, Platform, SafeAreaView } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { format } from 'date-fns';

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    pendingAction?: {
        type: 'create_task' | 'draft_reply' | 'add_to_calendar';
        data: any;
        status: 'pending' | 'approved' | 'rejected';
    };
}

// Mock chat session data
const MOCK_MESSAGES: ChatMessage[] = [
    {
        id: '1',
        role: 'user',
        content: 'Can you help me organize my tasks for today?',
        timestamp: new Date(Date.now() - 1000 * 60 * 10),
    },
    {
        id: '2',
        role: 'assistant',
        content: 'Of course! I looked at your inbox and calendar. You have 3 urgent items:\n\n1. Reply to Sarah about the Q4 budget\n2. Prepare slides for tomorrow\'s presentation\n3. Review the contract from legal\n\nWould you like me to create tasks for these?',
        timestamp: new Date(Date.now() - 1000 * 60 * 9),
        pendingAction: {
            type: 'create_task',
            data: { title: 'Reply to Sarah about Q4 budget' },
            status: 'pending',
        },
    },
    {
        id: '3',
        role: 'user',
        content: 'Yes, please create tasks for the first two.',
        timestamp: new Date(Date.now() - 1000 * 60 * 8),
    },
    {
        id: '4',
        role: 'assistant',
        content: 'Done! I\'ve created two tasks:\n\n✅ "Reply to Sarah about Q4 budget" (High priority)\n✅ "Prepare slides for tomorrow\'s presentation" (Urgent)\n\nBoth are now in your Focus Mode. Anything else?',
        timestamp: new Date(Date.now() - 1000 * 60 * 7),
    },
];

export default function ChatSessionScreen() {
    const { sessionId } = useLocalSearchParams();
    const router = useRouter();
    const flatListRef = useRef<FlatList>(null);

    const [messages, setMessages] = useState<ChatMessage[]>(MOCK_MESSAGES);
    const [inputText, setInputText] = useState('');
    const [isTyping, setIsTyping] = useState(false);

    const handleSend = () => {
        if (!inputText.trim()) return;

        const userMessage: ChatMessage = {
            id: Date.now().toString(),
            role: 'user',
            content: inputText.trim(),
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInputText('');
        setIsTyping(true);

        // Mock AI response after delay
        setTimeout(() => {
            const aiResponse: ChatMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: 'I understand. Let me help you with that. Is there anything specific you\'d like me to prioritize?',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, aiResponse]);
            setIsTyping(false);
        }, 1500);
    };

    const handleActionResponse = (messageId: string, approved: boolean) => {
        setMessages(prev => prev.map(msg => {
            if (msg.id === messageId && msg.pendingAction) {
                return {
                    ...msg,
                    pendingAction: {
                        ...msg.pendingAction,
                        status: approved ? 'approved' : 'rejected',
                    },
                };
            }
            return msg;
        }));
    };

    const renderMessage = ({ item }: { item: ChatMessage }) => {
        const isUser = item.role === 'user';

        return (
            <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
                {!isUser && (
                    <View style={styles.assistantAvatar}>
                        <Ionicons name="sparkles" size={14} color={Colors.accentSecondary} />
                    </View>
                )}
                <View style={[styles.bubbleContent, isUser ? styles.userContent : styles.assistantContent]}>
                    <DonnaText style={[styles.messageText, isUser && styles.userText]}>
                        {item.content}
                    </DonnaText>
                    <DonnaText style={styles.timestamp}>
                        {format(item.timestamp, 'h:mm a')}
                    </DonnaText>

                    {/* Pending Action Buttons */}
                    {item.pendingAction && item.pendingAction.status === 'pending' && (
                        <View style={styles.actionButtons}>
                            <TouchableOpacity
                                style={styles.rejectButton}
                                onPress={() => handleActionResponse(item.id, false)}
                            >
                                <Ionicons name="close" size={16} color={Colors.textSecondary} />
                                <DonnaText style={styles.rejectText}>Decline</DonnaText>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={styles.approveButton}
                                onPress={() => handleActionResponse(item.id, true)}
                            >
                                <Ionicons name="checkmark" size={16} color="#FFF" />
                                <DonnaText style={styles.approveText}>Approve</DonnaText>
                            </TouchableOpacity>
                        </View>
                    )}

                    {item.pendingAction && item.pendingAction.status !== 'pending' && (
                        <View style={[
                            styles.actionStatus,
                            item.pendingAction.status === 'approved' ? styles.approvedStatus : styles.rejectedStatus
                        ]}>
                            <Ionicons
                                name={item.pendingAction.status === 'approved' ? 'checkmark-circle' : 'close-circle'}
                                size={14}
                                color={item.pendingAction.status === 'approved' ? Colors.success : Colors.textMuted}
                            />
                            <DonnaText style={[
                                styles.statusText,
                                { color: item.pendingAction.status === 'approved' ? Colors.success : Colors.textMuted }
                            ]}>
                                {item.pendingAction.status === 'approved' ? 'Approved' : 'Declined'}
                            </DonnaText>
                        </View>
                    )}
                </View>
            </View>
        );
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <View style={styles.headerCenter}>
                    <DonnaText style={styles.headerTitle}>Donna</DonnaText>
                    <DonnaText style={styles.headerSubtitle}>Your AI Assistant</DonnaText>
                </View>
                <TouchableOpacity style={styles.menuButton}>
                    <Ionicons name="ellipsis-horizontal" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
            </View>

            {/* Messages */}
            <KeyboardAvoidingView
                style={styles.chatContainer}
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                keyboardVerticalOffset={90}
            >
                <FlatList
                    ref={flatListRef}
                    data={messages}
                    keyExtractor={(item) => item.id}
                    renderItem={renderMessage}
                    contentContainerStyle={styles.messagesList}
                    onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
                    ListFooterComponent={isTyping ? (
                        <View style={styles.typingIndicator}>
                            <View style={styles.assistantAvatar}>
                                <Ionicons name="sparkles" size={14} color={Colors.accentSecondary} />
                            </View>
                            <View style={styles.typingDots}>
                                <View style={styles.dot} />
                                <View style={[styles.dot, { opacity: 0.6 }]} />
                                <View style={[styles.dot, { opacity: 0.3 }]} />
                            </View>
                        </View>
                    ) : null}
                />

                {/* Input Bar */}
                <View style={styles.inputBar}>
                    <TextInput
                        style={styles.input}
                        value={inputText}
                        onChangeText={setInputText}
                        placeholder="Ask Donna anything..."
                        placeholderTextColor={Colors.textMuted}
                        multiline
                        maxLength={500}
                    />
                    <TouchableOpacity
                        style={[styles.sendButton, !inputText.trim() && styles.sendButtonDisabled]}
                        onPress={handleSend}
                        disabled={!inputText.trim()}
                    >
                        <Ionicons name="arrow-up" size={20} color="#FFF" />
                    </TouchableOpacity>
                </View>
            </KeyboardAvoidingView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
        backgroundColor: Colors.bgElevated,
    },
    backButton: {
        padding: Spacing.xs,
    },
    headerCenter: {
        flex: 1,
        alignItems: 'center',
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    headerSubtitle: {
        fontSize: 12,
        color: Colors.textMuted,
    },
    menuButton: {
        padding: Spacing.xs,
    },
    chatContainer: {
        flex: 1,
    },
    messagesList: {
        padding: Spacing.md,
        paddingBottom: Spacing.xl,
    },
    messageBubble: {
        flexDirection: 'row',
        marginBottom: Spacing.md,
        maxWidth: '85%',
    },
    userBubble: {
        alignSelf: 'flex-end',
    },
    assistantBubble: {
        alignSelf: 'flex-start',
    },
    assistantAvatar: {
        width: 28,
        height: 28,
        borderRadius: 14,
        backgroundColor: 'rgba(217, 119, 69, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.sm,
    },
    bubbleContent: {
        borderRadius: Radius.lg,
        padding: Spacing.md,
        maxWidth: '100%',
    },
    userContent: {
        backgroundColor: Colors.textPrimary,
        borderBottomRightRadius: 4,
    },
    assistantContent: {
        backgroundColor: Colors.bgElevated,
        borderWidth: 1,
        borderColor: Colors.border,
        borderBottomLeftRadius: 4,
    },
    messageText: {
        fontSize: 15,
        color: Colors.textPrimary,
        lineHeight: 22,
    },
    userText: {
        color: '#FFF',
    },
    timestamp: {
        fontSize: 11,
        color: Colors.textMuted,
        marginTop: Spacing.xs,
        alignSelf: 'flex-end',
    },
    actionButtons: {
        flexDirection: 'row',
        gap: Spacing.sm,
        marginTop: Spacing.md,
        paddingTop: Spacing.sm,
        borderTopWidth: 1,
        borderTopColor: 'rgba(0,0,0,0.05)',
    },
    rejectButton: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        paddingVertical: 8,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    rejectText: {
        fontSize: 13,
        color: Colors.textSecondary,
    },
    approveButton: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        paddingVertical: 8,
        borderRadius: Radius.component,
        backgroundColor: Colors.accentSecondary,
    },
    approveText: {
        fontSize: 13,
        color: '#FFF',
        fontWeight: '600',
    },
    actionStatus: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        marginTop: Spacing.sm,
        paddingTop: Spacing.sm,
        borderTopWidth: 1,
        borderTopColor: 'rgba(0,0,0,0.05)',
    },
    approvedStatus: {},
    rejectedStatus: {},
    statusText: {
        fontSize: 12,
        fontWeight: '500',
    },
    typingIndicator: {
        flexDirection: 'row',
        alignItems: 'center',
        marginTop: Spacing.sm,
    },
    typingDots: {
        flexDirection: 'row',
        gap: 4,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    dot: {
        width: 8,
        height: 8,
        borderRadius: 4,
        backgroundColor: Colors.textMuted,
    },
    inputBar: {
        flexDirection: 'row',
        alignItems: 'flex-end',
        gap: Spacing.sm,
        padding: Spacing.md,
        paddingBottom: Spacing.lg,
        backgroundColor: Colors.bgElevated,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    input: {
        flex: 1,
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: Colors.textPrimary,
        maxHeight: 100,
        paddingVertical: 10,
        paddingHorizontal: 14,
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    sendButton: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: Colors.accentSecondary,
        justifyContent: 'center',
        alignItems: 'center',
    },
    sendButtonDisabled: {
        backgroundColor: Colors.border,
    },
});
