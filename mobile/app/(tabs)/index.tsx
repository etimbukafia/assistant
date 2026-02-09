import React, { useState, useMemo, useCallback } from 'react';
import { StyleSheet, View, SectionList, TouchableOpacity, RefreshControl, ScrollView, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { DonnaCard } from '../../src/components/ui/DonnaCard';
import { SubscriptionExpiredCTA } from '../../src/components/ui/SubscriptionExpiredCTA';
import { StatusBar } from 'expo-status-bar';
import { Message } from '../../src/services/messages';
import { parseISO, formatDistanceToNow, isToday, isYesterday } from 'date-fns';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../src/context/AuthContext';
import { useMessages, useProcessingStatus } from '../../src/hooks/useMessages';
import { useTaskMutations } from '../../src/hooks/useTasks';
import { ImmersiveBackground } from '../../src/components/ui/ImmersiveBackground';

type FilterType = 'all' | 'needs_reply' | 'today';

export default function DashboardScreen() {
  const router = useRouter();
  const { isActive, subscriptionTier, initialSyncCompleted } = useAuth();
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [focusMode, setFocusMode] = useState(false);
  const [processingActive, setProcessingActive] = useState(false);

  // Fetch messages
  const { data: messagesResponse, isLoading, isRefetching, refetch } = useMessages();

  // Processing status polling - starts on pull-to-refresh
  const { data: processingData } = useProcessingStatus(isActive && processingActive);
  const processingCount = processingData?.processing_count ?? 0;

  React.useEffect(() => {
    if (processingActive && processingCount === 0 && processingData !== undefined) {
      setProcessingActive(false);
    }
  }, [processingActive, processingCount, processingData]);
  const { approve, dismiss } = useTaskMutations();

  const handleApproveTask = useCallback((taskId: number) => {
    approve(taskId);
  }, [approve]);

  const handleDismissTask = useCallback((taskId: number) => {
    dismiss(taskId);
  }, [dismiss]);

  // Messages from API
  const messages = useMemo(() => {
    return messagesResponse?.messages || [];
  }, [messagesResponse]);

  const onRefresh = React.useCallback(() => {
    refetch();
    if (isActive) {
      setProcessingActive(true);
    }
  }, [refetch, isActive]);

  const filteredMessages = useMemo(() => {
    let filtered = messages;
    if (activeFilter === 'needs_reply') {
      filtered = messages.filter(m => m.needs_reply);
    } else if (activeFilter === 'today') {
      filtered = messages.filter(m => isToday(parseISO(m.received_at)));
    }

    // Focus Mode: Hide non-urgent messages
    if (focusMode) {
      filtered = filtered.filter(m => m.needs_reply);
    }

    return filtered.sort((a, b) => new Date(b.received_at).getTime() - new Date(a.received_at).getTime());
  }, [messages, activeFilter, focusMode]);

  const sections = useMemo(() => {
    const today: Message[] = [];
    const yesterday: Message[] = [];
    const older: Message[] = [];

    filteredMessages.forEach(msg => {
      const date = parseISO(msg.received_at);
      if (isToday(date)) today.push(msg);
      else if (isYesterday(date)) yesterday.push(msg);
      else older.push(msg);
    });

    const result = [];
    if (today.length > 0) result.push({ title: 'Today', data: today });
    if (yesterday.length > 0) result.push({ title: 'Yesterday', data: yesterday });
    if (older.length > 0) result.push({ title: 'Older', data: older });
    return result;
  }, [filteredMessages]);

  const renderHeader = () => (
    <View style={styles.header}>
      {/* Title Row with Actions */}
      <View style={styles.titleRow}>
        <DonnaText variant="h1" style={styles.greeting}>Good Afternoon, J.</DonnaText>
        <View style={styles.headerActions}>
          {/* Focus Mode Toggle */}
          <TouchableOpacity
            style={[styles.actionButton, focusMode && styles.actionButtonActive]}
            onPress={() => setFocusMode(!focusMode)}
          >
            <Ionicons
              name={focusMode ? "flash" : "flash-outline"}
              size={18}
              color={focusMode ? '#FFFFFF' : Colors.textPrimary}
            />
          </TouchableOpacity>
        </View>
      </View>

      {/* Subscription Expired Banner */}
      {!isActive && (
        <View style={styles.ctaBanner}>
          <SubscriptionExpiredCTA tier={subscriptionTier as 'trial' | 'pro'} />
        </View>
      )}

      {/* Initial Sync Progress Banner (When active and syncing) */}
      {isActive && !initialSyncCompleted && (
        <View style={styles.syncBanner}>
          <ActivityIndicator size="small" color={Colors.accentPrimary} />
          <View style={styles.syncContent}>
            <DonnaText style={styles.syncTitle}>Syncing your world...</DonnaText>
            <DonnaText style={styles.syncDesc}>Processing emails from the last 24 hours.</DonnaText>
          </View>
        </View>
      )}

      {/* Processing Status Banner */}
      {processingActive && processingCount > 0 && (
        <View style={styles.syncBanner}>
          <ActivityIndicator size="small" color={Colors.accentSecondary} />
          <View style={styles.syncContent}>
            <DonnaText style={styles.syncTitle}>
              Processing {processingCount} email{processingCount !== 1 ? 's' : ''}...
            </DonnaText>
            <DonnaText style={styles.syncDesc}>AI is analyzing your messages</DonnaText>
          </View>
        </View>
      )}

      {/* Focus Mode Banner */}
      {focusMode && (
        <View style={styles.focusBanner}>
          <Ionicons name="flash" size={14} color={Colors.accentSecondary} />
          <DonnaText style={styles.focusBannerText}>Focus Mode: Only urgent notifications will interrupt you</DonnaText>
        </View>
      )}

      {/* Filter Chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
        <TouchableOpacity
          style={[styles.filterChip, activeFilter === 'all' && styles.filterChipActive]}
          onPress={() => setActiveFilter('all')}
        >
          <DonnaText style={[styles.filterText, activeFilter === 'all' && styles.filterTextActive]}>
            All ({messages.length})
          </DonnaText>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterChip, activeFilter === 'needs_reply' && styles.filterChipActiveUrgent]}
          onPress={() => setActiveFilter('needs_reply')}
        >
          <DonnaText style={[styles.filterText, activeFilter === 'needs_reply' && styles.filterTextActive]}>
            Needs Reply ({messages.filter(m => m.needs_reply).length})
          </DonnaText>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterChip, activeFilter === 'today' && styles.filterChipActive]}
          onPress={() => setActiveFilter('today')}
        >
          <DonnaText style={[styles.filterText, activeFilter === 'today' && styles.filterTextActive]}>
            Today ({messages.filter(m => isToday(parseISO(m.received_at))).length})
          </DonnaText>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );

  if (isLoading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color={Colors.accentPrimary} />
      </View>
    );
  }

  return (
    <ImmersiveBackground style={styles.container}>
      <StatusBar style="dark" />
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.id.toString()}
        ListHeaderComponent={renderHeader}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={onRefresh} tintColor={Colors.accentPrimary} />
        }
        renderSectionHeader={({ section: { title } }) => (
          <View style={styles.sectionHeader}>
            <DonnaText variant="overline">{title}</DonnaText>
          </View>
        )}
        renderItem={({ item }) => (
          <DonnaCard
            title={item.subject}
            sender={item.sender.split('<')[0].trim()}
            time={formatDistanceToNow(parseISO(item.received_at), { addSuffix: true })}
            insight={item.summary}
            type={item.needs_reply ? 'urgent' : item.scheduling_intent ? 'insight' : 'fyi'}
            tasks={item.tasks}
            extractedTasks={item.extracted_tasks?.map((t: any) => typeof t === 'string' ? t : t.title)}
            onApproveTask={handleApproveTask}
            onDismissTask={handleDismissTask}
            onPress={() => router.push(`/inbox/${item.id}` as any)}
          />
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            {activeFilter !== 'today' && (
              <Ionicons name="mail-open-outline" size={48} color={Colors.textMuted} />
            )}
            <DonnaText variant="h2" style={styles.emptyTitle}>
              {activeFilter === 'today' ? 'Nothing new today' : 'Inbox Zero!'}
            </DonnaText>
            <DonnaText style={styles.emptyText}>
              {activeFilter === 'today'
                ? 'Check back later for new updates'
                : 'Nothing needs your attention right now.'}
            </DonnaText>
          </View>
        }
      />
    </ImmersiveBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    // Background handled by ImmersiveBackground
  },
  center: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.sm,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
  },
  greeting: {
    // No margin needed
    color: Colors.textPrimary, // Ensure text is white
  },
  headerActions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  actionButton: {
    padding: Spacing.sm,
    backgroundColor: Colors.bgElevated,
    borderRadius: Radius.full,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  actionButtonActive: {
    backgroundColor: Colors.accentSecondary,
    borderColor: Colors.accentSecondary,
  },
  actionButtonDisabled: {
    opacity: 0.5,
  },
  ctaBanner: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
  },
  focusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    backgroundColor: 'rgba(217, 119, 69, 0.08)',
    borderRadius: Radius.component,
    borderWidth: 1,
    borderColor: 'rgba(217, 119, 69, 0.15)',
  },
  focusBannerText: {
    fontSize: 12,
    color: Colors.accentSecondary,
    fontWeight: '500',
  },
  syncBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.bgElevated,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    padding: Spacing.md,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.md,
  },
  syncContent: {
    flex: 1,
  },
  syncTitle: {
    fontWeight: '600',
    fontSize: 14,
    color: Colors.textPrimary,
  },
  syncDesc: {
    fontSize: 12,
    color: Colors.textSecondary,
  },
  filterScroll: {
    paddingHorizontal: Spacing.md,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.full,
    backgroundColor: Colors.bgElevated,
    borderWidth: 1,
    borderColor: Colors.border,
    marginRight: Spacing.sm,
  },
  filterChipActive: {
    backgroundColor: Colors.textPrimary,
    borderColor: Colors.textPrimary,
  },
  filterChipActiveUrgent: {
    backgroundColor: Colors.accentPrimary,
    borderColor: Colors.accentPrimary,
  },
  filterText: {
    fontSize: 13,
    color: Colors.textSecondary,
    fontWeight: '600',
  },
  filterTextActive: {
    color: Colors.bgBase, // Dark Text on Light Chip
  },
  listContent: {
    paddingBottom: Spacing.xl,
  },
  sectionHeader: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    marginTop: Spacing.sm,
  },
  emptyContainer: {
    padding: Spacing.xl,
    alignItems: 'center',
  },
  emptyTitle: {
    marginTop: Spacing.md,
    marginBottom: Spacing.xs,
    color: Colors.textPrimary,
  },
  emptyText: {
    color: Colors.textMuted,
    textAlign: 'center',
  },
});
