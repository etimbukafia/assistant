/**
 * Chat Sessions List Screen
 *
 * Displays recent chat sessions with ability to:
 * - View and resume previous sessions
 * - Start new action or reflection sessions
 * - Delete sessions
 *
 * Uses FlashList per mobile instructions for performance.
 */

import React, { useCallback } from 'react';
import { StyleSheet, View, TouchableOpacity, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { FlashList } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { format, isToday, isYesterday } from 'date-fns';

import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { useChatSessions, useDeleteSession, useCreateSession } from '@/src/hooks/useChat';
import { ChatSession } from '@/src/services/chat';

// =============================================================================
// Session Card Component
// =============================================================================

interface SessionCardProps {
  session: ChatSession;
  onPress: () => void;
  onDelete: () => void;
}

const SessionCard: React.FC<SessionCardProps> = ({ session, onPress, onDelete }) => {
  const isReflection = session.session_type === 'reflection';
  const accentColor = isReflection ? Colors.success : Colors.accentSecondary;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isToday(date)) return format(date, "'Today at' h:mm a");
    if (isYesterday(date)) return format(date, "'Yesterday at' h:mm a");
    return format(date, 'MMM d, h:mm a');
  };

  return (
    <TouchableOpacity style={styles.sessionCard} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.sessionContent}>
        {/* Icon */}
        <View style={[styles.sessionIcon, { backgroundColor: `${accentColor}15` }]}>
          <Ionicons
            name={isReflection ? 'leaf' : 'flash'}
            size={20}
            color={accentColor}
          />
        </View>

        {/* Details */}
        <View style={styles.sessionDetails}>
          <DonnaText style={styles.sessionTitle} numberOfLines={1}>
            {session.title || (isReflection ? 'Reflection' : 'Work Chat')}
          </DonnaText>
          <View style={styles.sessionMeta}>
            <DonnaText style={styles.sessionType}>
              {isReflection ? 'Reflection' : 'Action'}
            </DonnaText>
            <View style={styles.metaDot} />
            <DonnaText style={styles.sessionDate}>
              {formatDate(session.last_activity_at)}
            </DonnaText>
          </View>
        </View>

        {/* Delete Button */}
        <TouchableOpacity
          style={styles.deleteButton}
          onPress={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="trash-outline" size={18} color={Colors.textMuted} />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
};

// =============================================================================
// Empty State Component
// =============================================================================

const EmptyState: React.FC<{ onCreateSession: (type: 'command' | 'reflection') => void }> = ({
  onCreateSession,
}) => (
  <View style={styles.emptyState}>
    <View style={styles.emptyIconContainer}>
      <Ionicons name="chatbubbles-outline" size={48} color={Colors.textMuted} />
    </View>
    <DonnaText style={styles.emptyTitle}>No conversations yet</DonnaText>
    <DonnaText style={styles.emptySubtitle}>
      Start a chat to get help with tasks or reflect on your day
    </DonnaText>
    <View style={styles.emptyActions}>
      <TouchableOpacity
        style={[styles.emptyButton, { backgroundColor: Colors.accentSecondary }]}
        onPress={() => onCreateSession('command')}
      >
        <Ionicons name="flash" size={18} color="#FFF" />
        <DonnaText style={styles.emptyButtonText}>Start Action Chat</DonnaText>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.emptyButton, styles.emptyButtonOutline]}
        onPress={() => onCreateSession('reflection')}
      >
        <Ionicons name="leaf" size={18} color={Colors.success} />
        <DonnaText style={[styles.emptyButtonText, { color: Colors.success }]}>
          Start Reflection
        </DonnaText>
      </TouchableOpacity>
    </View>
  </View>
);

// =============================================================================
// Main Screen
// =============================================================================

export default function ChatSessionsScreen() {
  const router = useRouter();
  const { data: sessionsData, isLoading, refetch, isRefetching } = useChatSessions();
  const sessions = sessionsData?.sessions || [];
  const deleteSession = useDeleteSession();
  const createSession = useCreateSession();

  const handleOpenSession = useCallback(
    (sessionId: string) => {
      router.push(`/chat/${sessionId}`);
    },
    [router]
  );

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      deleteSession.mutate(sessionId);
    },
    [deleteSession]
  );

  const handleCreateSession = useCallback(
    async (type: 'command' | 'reflection') => {
      try {
        const session = await createSession.mutateAsync(type);
        router.push(`/chat/${session.id}`);
      } catch (error) {
        console.error('Failed to create session:', error);
      }
    },
    [createSession, router]
  );

  const renderItem = useCallback(
    ({ item }: { item: ChatSession }) => (
      <SessionCard
        session={item}
        onPress={() => handleOpenSession(item.id)}
        onDelete={() => handleDeleteSession(item.id)}
      />
    ),
    [handleOpenSession, handleDeleteSession]
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar style="dark" />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <DonnaText style={styles.headerTitle}>Conversations</DonnaText>
        <View style={styles.headerRight}>
          <TouchableOpacity
            style={styles.newChatButton}
            onPress={() => handleCreateSession('command')}
          >
            <Ionicons name="add" size={24} color={Colors.accentSecondary} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Session List */}
      <View style={styles.listContainer}>
        {!isLoading && (!sessions || sessions.length === 0) ? (
          <EmptyState onCreateSession={handleCreateSession} />
        ) : (
          <FlashList
            data={sessions || []}
            renderItem={renderItem}
            keyExtractor={(item: ChatSession) => item.id}
            estimatedItemSize={80}
            contentContainerStyle={styles.listContent}
            refreshControl={
              <RefreshControl
                refreshing={isRefetching}
                onRefresh={refetch}
                tintColor={Colors.accentSecondary}
              />
            }
            ListHeaderComponent={
              <View style={styles.listHeader}>
                <DonnaText style={styles.listHeaderText}>Recent</DonnaText>
              </View>
            }
          />
        )}
      </View>

      {/* FAB for new session */}
      {sessions && sessions.length > 0 && (
        <View style={styles.fabContainer}>
          <TouchableOpacity
            style={[styles.fab, styles.fabSecondary]}
            onPress={() => handleCreateSession('reflection')}
          >
            <Ionicons name="leaf" size={22} color={Colors.success} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.fab, styles.fabPrimary]}
            onPress={() => handleCreateSession('command')}
          >
            <Ionicons name="add" size={28} color="#FFF" />
          </TouchableOpacity>
        </View>
      )}
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
  headerTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  headerRight: {
    width: 40,
    alignItems: 'flex-end',
  },
  newChatButton: {
    padding: Spacing.xs,
  },
  listContainer: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 100, // Space for FAB
  },
  listHeader: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    paddingTop: Spacing.md,
  },
  listHeaderText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sessionCard: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    backgroundColor: Colors.bgElevated,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sessionContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    gap: Spacing.md,
  },
  sessionIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sessionDetails: {
    flex: 1,
  },
  sessionTitle: {
    fontSize: 16,
    fontWeight: '500',
    color: Colors.textPrimary,
    marginBottom: 2,
  },
  sessionMeta: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sessionType: {
    fontSize: 12,
    color: Colors.textMuted,
  },
  metaDot: {
    width: 3,
    height: 3,
    borderRadius: 1.5,
    backgroundColor: Colors.textMuted,
    marginHorizontal: 6,
  },
  sessionDate: {
    fontSize: 12,
    color: Colors.textMuted,
  },
  deleteButton: {
    padding: Spacing.xs,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
  },
  emptyIconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.bgElevated,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: Colors.textPrimary,
    marginBottom: Spacing.xs,
  },
  emptySubtitle: {
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: Spacing.xl,
  },
  emptyActions: {
    gap: Spacing.sm,
    width: '100%',
  },
  emptyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.md,
    borderRadius: Radius.lg,
  },
  emptyButtonOutline: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: Colors.success,
  },
  emptyButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  fabContainer: {
    position: 'absolute',
    bottom: Spacing.xl,
    right: Spacing.md,
    gap: Spacing.sm,
    alignItems: 'center',
  },
  fab: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 8,
  },
  fabPrimary: {
    backgroundColor: Colors.accentSecondary,
  },
  fabSecondary: {
    backgroundColor: Colors.bgElevated,
    borderWidth: 1,
    borderColor: Colors.border,
    width: 48,
    height: 48,
    borderRadius: 24,
  },
});
