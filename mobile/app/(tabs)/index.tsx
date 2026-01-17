import React, { useState, useMemo } from 'react';
import { StyleSheet, View, SectionList, TouchableOpacity, RefreshControl, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { DonnaCard } from '../../src/components/ui/DonnaCard';
import { StatusBar } from 'expo-status-bar';
import demoData from '../../src/data/demo_state.json';
import { Message } from '../../src/types/api';
import { parseISO, formatDistanceToNow, isToday, isYesterday } from 'date-fns';
import { Ionicons } from '@expo/vector-icons';

type FilterType = 'all' | 'needs_reply' | 'today';

export default function DashboardScreen() {
  const router = useRouter();
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [focusMode, setFocusMode] = useState(false);

  // Cast mock data to typed interface
  const messages = demoData.messages as unknown as Message[];

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

  const onRefresh = React.useCallback(() => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1000);
  }, []);

  const renderHeader = () => (
    <View style={styles.header}>
      {/* Title Row with Actions */}
      <View style={styles.titleRow}>
        <DonnaText variant="h1" style={styles.greeting}>Inbox</DonnaText>
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

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.id.toString()}
        ListHeaderComponent={renderHeader}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accentPrimary} />
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
            snippet={item.body}
            time={formatDistanceToNow(parseISO(item.received_at), { addSuffix: true })}
            insight={item.summary}
            type={item.needs_reply ? 'urgent' : item.scheduling_intent ? 'insight' : 'fyi'}
            suggestedAction={item.needs_reply ? 'Draft Reply' : item.scheduling_intent ? 'Schedule' : undefined}
            onPress={() => router.push(`/inbox/${item.id}` as any)}
            onActionPress={() => router.push(`/inbox/${item.id}` as any)}
          />
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="mail-open-outline" size={48} color={Colors.textMuted} />
            <DonnaText variant="h2" style={styles.emptyTitle}>Inbox Zero!</DonnaText>
            <DonnaText style={styles.emptyText}>Nothing needs your attention right now.</DonnaText>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgBase,
  },
  header: {
    paddingTop: Spacing.xl,
    backgroundColor: Colors.bgBase,
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
  },
  headerActions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  actionButton: {
    padding: Spacing.sm,
    backgroundColor: Colors.bgSurface,
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
  focusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    backgroundColor: 'rgba(217, 119, 69, 0.1)', // Natural Copper at 10%
    borderRadius: Radius.component,
    borderWidth: 1,
    borderColor: 'rgba(217, 119, 69, 0.2)', // Natural Copper at 20%
  },
  focusBannerText: {
    fontSize: 12,
    color: Colors.accentSecondary,
    fontWeight: '500',
  },
  filterScroll: {
    paddingHorizontal: Spacing.md,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.full,
    backgroundColor: Colors.bgSurface,
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
    color: '#FFFFFF',
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
  },
  emptyText: {
    color: Colors.textMuted,
    textAlign: 'center',
  },
});
