/**
 * Chat Session Screen
 *
 * Full conversation view with:
 * - Real-time message sending (sync/async support)
 * - Pending action approval/rejection
 * - Typing indicators
 * - Session history drawer
 *
 * Uses real API via chat service and hooks.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  Animated,
  Dimensions,
  Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { FlashList } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { format, isToday, isYesterday } from 'date-fns';

import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import {
  useChatSession,
  useChatSessions,
  useApproveAction,
  useRejectAction,
  useAddMessageToCache,
  useUpdateMessageInCache,
  chatKeys,
} from '@/src/hooks/useChat';
import {
  ChatSession,
  ChatMessage,
  PendingAction,
  sendMessageWithPolling,
} from '@/src/services/chat';
import { useQueryClient } from '@tanstack/react-query';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const DRAWER_WIDTH = SCREEN_WIDTH * 0.8;

// =============================================================================
// Types
// =============================================================================

type MessageStatus = 'sending' | 'processing' | 'complete' | 'error';

interface DisplayMessage extends ChatMessage {
  status?: MessageStatus;
  jobId?: string;
  error?: string;
}

// =============================================================================
// Message Bubble Component
// =============================================================================

interface MessageBubbleProps {
  message: DisplayMessage;
  pendingAction?: PendingAction;
  onApprove?: () => void;
  onReject?: () => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  pendingAction,
  onApprove,
  onReject,
}) => {
  const isUser = message.role === 'user';
  const isProcessing = message.status === 'processing' || message.status === 'sending';
  const isError = message.status === 'error';

  return (
    <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
      {!isUser && (
        <View style={styles.assistantAvatar}>
          <Ionicons name="sparkles" size={14} color={Colors.accentSecondary} />
        </View>
      )}
      <View style={[styles.bubbleContent, isUser ? styles.userContent : styles.assistantContent]}>
        {isProcessing && !message.content ? (
          <View style={styles.processingContainer}>
            <ActivityIndicator size="small" color={Colors.accentSecondary} />
            <DonnaText style={styles.processingText}>Thinking...</DonnaText>
          </View>
        ) : (
          <>
            <DonnaText
              style={[
                styles.messageText,
                isUser && styles.userText,
                isError && styles.errorText,
              ]}
            >
              {message.content}
            </DonnaText>
            <DonnaText style={[styles.timestamp, isUser && styles.userTimestamp]}>
              {format(new Date(message.created_at), 'h:mm a')}
            </DonnaText>
          </>
        )}

        {/* Pending Action Buttons */}
        {pendingAction && pendingAction.status === 'pending' && (
          <View style={styles.actionButtons}>
            <TouchableOpacity style={styles.rejectButton} onPress={onReject}>
              <Ionicons name="close" size={16} color={Colors.textSecondary} />
              <DonnaText style={styles.rejectText}>Decline</DonnaText>
            </TouchableOpacity>
            <TouchableOpacity style={styles.approveButton} onPress={onApprove}>
              <Ionicons name="checkmark" size={16} color="#FFF" />
              <DonnaText style={styles.approveText}>Approve</DonnaText>
            </TouchableOpacity>
          </View>
        )}

        {pendingAction && pendingAction.status !== 'pending' && (
          <View
            style={[
              styles.actionStatus,
              pendingAction.status === 'approved' ? styles.approvedStatus : styles.rejectedStatus,
            ]}
          >
            <Ionicons
              name={pendingAction.status === 'approved' ? 'checkmark-circle' : 'close-circle'}
              size={14}
              color={pendingAction.status === 'approved' ? Colors.success : Colors.textMuted}
            />
            <DonnaText
              style={[
                styles.statusText,
                { color: pendingAction.status === 'approved' ? Colors.success : Colors.textMuted },
              ]}
            >
              {pendingAction.status === 'approved' ? 'Approved' : 'Declined'}
            </DonnaText>
          </View>
        )}
      </View>
    </View>
  );
};

// =============================================================================
// Typing Indicator Component
// =============================================================================

const TypingIndicator: React.FC = () => (
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
);

// =============================================================================
// Session Drawer Item
// =============================================================================

interface SessionDrawerItemProps {
  session: ChatSession;
  isActive: boolean;
  onPress: () => void;
}

const SessionDrawerItem: React.FC<SessionDrawerItemProps> = ({
  session,
  isActive,
  onPress,
}) => {
  const isReflection = session.session_type === 'reflection';
  const accentColor = isReflection ? Colors.success : Colors.accentSecondary;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isToday(date)) return format(date, 'h:mm a');
    if (isYesterday(date)) return 'Yesterday';
    return format(date, 'MMM d');
  };

  return (
    <TouchableOpacity
      style={[styles.drawerItem, isActive && styles.drawerItemActive]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={[styles.drawerItemIcon, { backgroundColor: `${accentColor}15` }]}>
        <Ionicons
          name={isReflection ? 'leaf' : 'flash'}
          size={16}
          color={accentColor}
        />
      </View>
      <View style={styles.drawerItemContent}>
        <DonnaText style={styles.drawerItemTitle} numberOfLines={1}>
          {session.title || (isReflection ? 'Reflection' : 'Work Chat')}
        </DonnaText>
        <View style={styles.drawerItemMeta}>
          <DonnaText style={styles.drawerItemType}>
            {isReflection ? 'Reflection' : 'Action'}
          </DonnaText>
          {isReflection && (
            <>
              <View style={styles.drawerItemDot} />
              <Ionicons name="hourglass-outline" size={10} color={Colors.textMuted} />
            </>
          )}
        </View>
      </View>
      <DonnaText style={styles.drawerItemDate}>{formatDate(session.last_activity_at)}</DonnaText>
    </TouchableOpacity>
  );
};

// =============================================================================
// Session Drawer Component
// =============================================================================

interface SessionDrawerProps {
  visible: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
}

const SessionDrawer: React.FC<SessionDrawerProps> = ({
  visible,
  onClose,
  sessions,
  currentSessionId,
  onSelectSession,
}) => {
  const slideAnim = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(slideAnim, {
          toValue: 0,
          duration: 250,
          useNativeDriver: true,
        }),
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 250,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(slideAnim, {
          toValue: -DRAWER_WIDTH,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible, slideAnim, fadeAnim]);

  if (!visible) return null;

  return (
    <Modal transparent visible={visible} onRequestClose={onClose}>
      <View style={styles.drawerContainer}>
        <Pressable style={styles.drawerOverlay} onPress={onClose}>
          <Animated.View style={[styles.drawerOverlayBg, { opacity: fadeAnim }]} />
        </Pressable>
        <Animated.View
          style={[styles.drawer, { transform: [{ translateX: slideAnim }] }]}
        >
          <SafeAreaView style={styles.drawerSafe} edges={['top', 'left']}>
            <View style={styles.drawerHeader}>
              <DonnaText style={styles.drawerTitle}>Sessions</DonnaText>
              <TouchableOpacity onPress={onClose} style={styles.drawerCloseBtn}>
                <Ionicons name="close" size={24} color={Colors.textPrimary} />
              </TouchableOpacity>
            </View>
            <FlashList<ChatSession>
              data={sessions}
              keyExtractor={(item: ChatSession) => item.id}
              renderItem={({ item }: { item: ChatSession }) => (
                <SessionDrawerItem
                  session={item}
                  isActive={item.id === currentSessionId}
                  onPress={() => {
                    onSelectSession(item.id);
                    onClose();
                  }}
                />
              )}
              estimatedItemSize={60}
              contentContainerStyle={styles.drawerList}
            />
          </SafeAreaView>
        </Animated.View>
      </View>
    </Modal>
  );
};

// =============================================================================
// Main Screen
// =============================================================================

export default function ChatSessionScreen() {
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const router = useRouter();
  const listRef = useRef<React.ElementRef<typeof FlashList<DisplayMessage>>>(null);
  const queryClient = useQueryClient();

  // State
  const [inputText, setInputText] = useState('');
  const [localMessages, setLocalMessages] = useState<DisplayMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Refs for race condition protection
  const currentSessionRef = useRef<string | null>(sessionId || null);
  const pollingCleanupRef = useRef<(() => void) | null>(null);
  const hardTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset state when sessionId changes (e.g., switching via drawer)
  useEffect(() => {
    currentSessionRef.current = sessionId || null;
    // Cleanup polling from previous session
    if (pollingCleanupRef.current) {
      pollingCleanupRef.current();
      pollingCleanupRef.current = null;
    }
    if (hardTimeoutRef.current) {
      clearTimeout(hardTimeoutRef.current);
      hardTimeoutRef.current = null;
    }
    // Reset send state so input is usable in the new session
    setIsSending(false);
    setIsTyping(false);
  }, [sessionId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingCleanupRef.current) {
        pollingCleanupRef.current();
      }
      if (hardTimeoutRef.current) {
        clearTimeout(hardTimeoutRef.current);
      }
    };
  }, []);

  // Queries
  const { data: sessionData, isLoading } = useChatSession(sessionId || null);
  const { data: sessionsData } = useChatSessions({});
  const approveAction = useApproveAction(sessionId || '');
  const rejectAction = useRejectAction(sessionId || '');

  const allSessions = sessionsData?.sessions || [];

  // Sync server messages to local state
  useEffect(() => {
    if (sessionData?.messages) {
      // Filter out system messages and ensure role type compatibility
      const displayMessages = sessionData.messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({
          ...m,
          role: m.role as 'user' | 'assistant',
          status: 'complete' as const,
        }))
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      setLocalMessages(displayMessages);
    }
  }, [sessionData?.messages]);

  // Get pending action for a message
  const getPendingAction = useCallback(
    (messageId: number): PendingAction | undefined => {
      return sessionData?.pending_actions?.find((pa) => pa.message_id === messageId);
    },
    [sessionData?.pending_actions]
  );

  // Handle send message
  const handleSend = useCallback(async () => {
    const text = inputText.trim();
    if (!text || !sessionId || isSending) return;

    setInputText('');
    setIsSending(true);

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
    let isMounted = true;

    // Send with polling support
    const cleanup = await sendMessageWithPolling(targetSessionId, text, {
      onComplete: (response, pendingActions) => {
        // Race condition check: only update if still on same session
        if (!isMounted || currentSessionRef.current !== targetSessionId) {
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
        // Invalidate to get updated pending actions
        queryClient.invalidateQueries({ queryKey: chatKeys.session(targetSessionId) });
        setIsTyping(false);
        setIsSending(false);
      },
      onError: (error) => {
        if (!isMounted || currentSessionRef.current !== targetSessionId) {
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
        if (!isMounted || currentSessionRef.current !== targetSessionId) {
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

    // Store cleanup function
    pollingCleanupRef.current = () => {
      isMounted = false;
      cleanup();
    };

    // Hard timeout: reset UI state after 3 minutes regardless
    if (hardTimeoutRef.current) {
      clearTimeout(hardTimeoutRef.current);
    }
    hardTimeoutRef.current = setTimeout(() => {
      if (isMounted) {
        setIsTyping(false);
        setIsSending(false);
      }
      hardTimeoutRef.current = null;
    }, 180000);
  }, [inputText, sessionId, isSending, queryClient]);

  // Handle action approval
  const handleApprove = useCallback(
    (actionId: string) => {
      approveAction.mutate(actionId);
    },
    [approveAction]
  );

  // Handle action rejection
  const handleReject = useCallback(
    (actionId: string) => {
      rejectAction.mutate(actionId);
    },
    [rejectAction]
  );

  // Render message item
  const renderMessage = useCallback(
    ({ item }: { item: DisplayMessage }) => {
      const pendingAction = getPendingAction(item.id);
      return (
        <MessageBubble
          message={item}
          pendingAction={pendingAction}
          onApprove={pendingAction ? () => handleApprove(pendingAction.id) : undefined}
          onReject={pendingAction ? () => handleReject(pendingAction.id) : undefined}
        />
      );
    },
    [getPendingAction, handleApprove, handleReject]
  );

  // Session info
  const session = sessionData?.session;
  const isReflection = session?.session_type === 'reflection';

  // Handle session switch from drawer
  const handleSelectSession = useCallback(
    (newSessionId: string) => {
      if (newSessionId !== sessionId) {
        router.replace(`/chat/${newSessionId}`);
      }
    },
    [sessionId, router]
  );

  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.accentSecondary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />

      {/* Session Drawer */}
      <SessionDrawer
        visible={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        sessions={allSessions}
        currentSessionId={sessionId || ''}
        onSelectSession={handleSelectSession}
      />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.headerCenter}
          onPress={() => setIsDrawerOpen(true)}
          activeOpacity={0.7}
        >
          <View style={styles.headerTitleRow}>
            <DonnaText style={styles.headerTitle}>Donna</DonnaText>
            <Ionicons name="chevron-down" size={16} color={Colors.textMuted} />
          </View>
          <View style={styles.headerSubtitleRow}>
            <Ionicons
              name={isReflection ? 'leaf' : 'flash'}
              size={12}
              color={isReflection ? Colors.success : Colors.accentSecondary}
            />
            <DonnaText style={styles.headerSubtitle}>
              {isReflection ? 'Reflection Mode' : 'Action Mode'}
            </DonnaText>
            {isReflection && (
              <>
                <View style={styles.headerDot} />
                <Ionicons name="hourglass-outline" size={11} color={Colors.textMuted} />
                <DonnaText style={styles.ephemeralText}>Temporary</DonnaText>
              </>
            )}
          </View>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.menuButton}
          onPress={() => setIsDrawerOpen(true)}
        >
          <Ionicons name="menu-outline" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <KeyboardAvoidingView
        style={styles.chatContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        <View style={styles.listContainer}>
          <FlashList<DisplayMessage>
            ref={listRef}
            data={localMessages}
            keyExtractor={(item: DisplayMessage) => String(item.id)}
            renderItem={renderMessage}
            estimatedItemSize={100}
            contentContainerStyle={styles.messagesList}
            onContentSizeChange={() => {
              listRef.current?.scrollToEnd({ animated: true });
            }}
            ListFooterComponent={isTyping ? <TypingIndicator /> : null}
          />
        </View>

        {/* Input Bar */}
        <View style={styles.inputBar}>
          <TextInput
            style={styles.input}
            value={inputText}
            onChangeText={setInputText}
            placeholder={isReflection ? "What's on your mind?" : 'Ask Donna anything...'}
            placeholderTextColor={Colors.textMuted}
            multiline
            maxLength={500}
            editable={!isSending}
          />
          <TouchableOpacity
            style={[
              styles.sendButton,
              (!inputText.trim() || isSending) && styles.sendButtonDisabled,
            ]}
            onPress={handleSend}
            disabled={!inputText.trim() || isSending}
          >
            {isSending ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <Ionicons name="arrow-up" size={20} color="#FFF" />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// =============================================================================
// Styles
// =============================================================================

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgBase,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
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
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  headerSubtitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  headerSubtitle: {
    fontSize: 12,
    color: Colors.textMuted,
  },
  headerDot: {
    width: 3,
    height: 3,
    borderRadius: 1.5,
    backgroundColor: Colors.textMuted,
    marginHorizontal: 2,
  },
  ephemeralText: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  menuButton: {
    padding: Spacing.xs,
  },
  chatContainer: {
    flex: 1,
  },
  listContainer: {
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
  processingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  processingText: {
    fontSize: 14,
    color: Colors.textMuted,
  },
  messageText: {
    fontSize: 15,
    color: Colors.textPrimary,
    lineHeight: 22,
  },
  userText: {
    color: '#FFF',
  },
  errorText: {
    color: Colors.error,
  },
  timestamp: {
    fontSize: 11,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
    alignSelf: 'flex-end',
  },
  userTimestamp: {
    color: 'rgba(255,255,255,0.7)',
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
  // Drawer styles
  drawerContainer: {
    flex: 1,
    flexDirection: 'row',
  },
  drawerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  drawerOverlayBg: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  drawer: {
    width: DRAWER_WIDTH,
    backgroundColor: Colors.bgBase,
    height: '100%',
    shadowColor: '#000',
    shadowOffset: { width: 2, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 10,
  },
  drawerSafe: {
    flex: 1,
  },
  drawerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.bgElevated,
  },
  drawerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  drawerCloseBtn: {
    padding: Spacing.xs,
  },
  drawerList: {
    paddingVertical: Spacing.sm,
  },
  drawerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    gap: Spacing.sm,
  },
  drawerItemActive: {
    backgroundColor: `${Colors.accentSecondary}10`,
  },
  drawerItemIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  drawerItemContent: {
    flex: 1,
  },
  drawerItemTitle: {
    fontSize: 14,
    fontWeight: '500',
    color: Colors.textPrimary,
  },
  drawerItemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 2,
  },
  drawerItemType: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  drawerItemDot: {
    width: 2,
    height: 2,
    borderRadius: 1,
    backgroundColor: Colors.textMuted,
  },
  drawerItemDate: {
    fontSize: 11,
    color: Colors.textMuted,
  },
});
