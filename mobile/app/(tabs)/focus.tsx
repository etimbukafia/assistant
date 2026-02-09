import React, { useState, useMemo } from 'react';
import { StyleSheet, View, SectionList, TouchableOpacity, RefreshControl, ScrollView, ActivityIndicator } from 'react-native';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Task } from '../../src/types/api';
import { InlineTaskItem } from '../../src/components/ui/InlineTaskItem';
import { Ionicons } from '@expo/vector-icons';
import { useTasks, useTaskMutations } from '../../src/hooks/useTasks';

type TabView = 'all' | 'pending' | 'active' | 'waiting';

export default function FocusScreen() {
    const [activeTab, setActiveTab] = useState<TabView>('all');
    const [showCompleted, setShowCompleted] = useState(false);

    // Task mutations
    const { approve, complete, start, dismiss, isAnyPending } = useTaskMutations();

    // Fetch tasks
    const { data: tasksResponse, isLoading, isRefetching, refetch } = useTasks({});

    // Use API response
    const allTasks = useMemo(() => {
        return tasksResponse?.tasks || [];
    }, [tasksResponse]);

    // Task categories (matching frontend TaskHub.jsx)
    const pendingApprovalTasks = allTasks.filter(t => t.status === 'pending_approval');
    const activeTasks = allTasks.filter(t => t.status === 'approved' || t.status === 'in_progress');
    const waitingTasks = allTasks.filter(t => t.status === 'waiting_for');
    const completedTasks = allTasks.filter(t => t.status === 'completed');
    const urgentTasks = activeTasks.filter(t => t.priority === 'urgent');

    const getFilteredTasks = () => {
        switch (activeTab) {
            case 'pending':
                return { pending: pendingApprovalTasks, active: [], waiting: [] };
            case 'active':
                return { pending: [], active: activeTasks, waiting: [] };
            case 'waiting':
                return { pending: [], active: [], waiting: waitingTasks };
            case 'all':
            default:
                return { pending: pendingApprovalTasks, active: activeTasks, waiting: waitingTasks };
        }
    };

    const filtered = getFilteredTasks();
    const totalActionable = pendingApprovalTasks.length + activeTasks.length + waitingTasks.length;

    const onRefresh = React.useCallback(() => {
        refetch();
    }, [refetch]);

    const renderHeader = () => (
        <View style={styles.header}>
            <DonnaText variant="h1" style={styles.title}>Focus Mode</DonnaText>

            {/* Filter Chips (matching frontend TaskHub.jsx) */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
                <TouchableOpacity
                    style={[styles.filterChip, activeTab === 'all' && styles.filterChipActive]}
                    onPress={() => setActiveTab('all')}
                >
                    <DonnaText style={[styles.filterChipText, activeTab === 'all' && styles.filterChipTextActive]}>
                        All ({totalActionable})
                    </DonnaText>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.filterChip, activeTab === 'pending' && styles.filterChipActiveAmber]}
                    onPress={() => setActiveTab('pending')}
                >
                    <DonnaText style={[styles.filterChipText, activeTab === 'pending' && styles.filterChipTextActive]}>
                        Suggested ({pendingApprovalTasks.length})
                    </DonnaText>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.filterChip, activeTab === 'active' && styles.filterChipActive]}
                    onPress={() => setActiveTab('active')}
                >
                    <DonnaText style={[styles.filterChipText, activeTab === 'active' && styles.filterChipTextActive]}>
                        Active ({activeTasks.length})
                    </DonnaText>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.filterChip, activeTab === 'waiting' && styles.filterChipActivePurple]}
                    onPress={() => setActiveTab('waiting')}
                >
                    <DonnaText style={[styles.filterChipText, activeTab === 'waiting' && styles.filterChipTextActive]}>
                        Waiting ({waitingTasks.length})
                    </DonnaText>
                </TouchableOpacity>
            </ScrollView>

            {/* Stats Summary (matching frontend TaskHub.jsx) */}
            <View style={styles.statsRow}>
                <View style={[styles.statBadge, { backgroundColor: 'rgba(128, 0, 32, 0.1)', borderColor: 'rgba(128, 0, 32, 0.2)' }]}>
                    <Ionicons name="alert-circle" size={12} color={Colors.error} />
                    <DonnaText style={[styles.statText, { color: Colors.error }]}>Urgent ({urgentTasks.length})</DonnaText>
                </View>
                <View style={[styles.statBadge, { backgroundColor: 'rgba(217, 119, 69, 0.1)', borderColor: 'rgba(217, 119, 69, 0.2)' }]}>
                    <Ionicons name="sparkles" size={12} color={Colors.accentSecondary} />
                    <DonnaText style={[styles.statText, { color: Colors.accentSecondary }]}>Pending ({pendingApprovalTasks.length})</DonnaText>
                </View>
                <View style={[styles.statBadge, { backgroundColor: 'rgba(138, 154, 91, 0.1)', borderColor: 'rgba(138, 154, 91, 0.2)' }]}>
                    <Ionicons name="checkmark-circle" size={12} color={Colors.success} />
                    <DonnaText style={[styles.statText, { color: Colors.success }]}>Done today ({completedTasks.length})</DonnaText>
                </View>
            </View>
        </View>
    );

    return (
        <View style={styles.container}>
            <StatusBar style="dark" />
            <ScrollView
                refreshControl={
                    <RefreshControl refreshing={isRefetching} onRefresh={onRefresh} tintColor={Colors.accentPrimary} />
                }
                contentContainerStyle={styles.listContent}
            >
                {renderHeader()}

                {/* Pending Approval - "Suggested by AI" */}
                {filtered.pending.length > 0 && (
                    <View style={styles.section}>
                        <View style={styles.sectionHeader}>
                            <Ionicons name="sparkles" size={14} color={Colors.accentSecondary} />
                            <DonnaText style={[styles.sectionTitle, { color: Colors.accentSecondary }]}>SUGGESTED BY AI</DonnaText>
                        </View>
                        {filtered.pending.map(task => (
                            <View key={task.id} style={styles.taskContainer}>
                                <InlineTaskItem
                                            task={task}
                                            onApprove={approve}
                                            onComplete={complete}
                                            onStart={start}
                                            onDismiss={dismiss}
                                        />
                            </View>
                        ))}
                    </View>
                )}

                {/* Active - "Do Now" for Urgent */}
                {urgentTasks.length > 0 && (activeTab === 'all' || activeTab === 'active') && (
                    <View style={styles.section}>
                        <View style={styles.sectionHeader}>
                            <Ionicons name="alert-circle" size={14} color={Colors.error} />
                            <DonnaText style={[styles.sectionTitle, { color: Colors.error }]}>DO NOW</DonnaText>
                        </View>
                        {urgentTasks.map(task => (
                            <View key={task.id} style={styles.taskContainer}>
                                <InlineTaskItem
                                            task={task}
                                            onApprove={approve}
                                            onComplete={complete}
                                            onStart={start}
                                            onDismiss={dismiss}
                                        />
                            </View>
                        ))}
                    </View>
                )}

                {/* Active - Other */}
                {filtered.active.filter(t => t.priority !== 'urgent').length > 0 && (
                    <View style={styles.section}>
                        <View style={styles.sectionHeader}>
                            <Ionicons name="flash" size={14} color={Colors.accentPrecision} />
                            <DonnaText style={[styles.sectionTitle, { color: Colors.accentPrecision }]}>UPCOMING</DonnaText>
                        </View>
                        {filtered.active.filter(t => t.priority !== 'urgent').map(task => (
                            <View key={task.id} style={styles.taskContainer}>
                                <InlineTaskItem
                                            task={task}
                                            onApprove={approve}
                                            onComplete={complete}
                                            onStart={start}
                                            onDismiss={dismiss}
                                        />
                            </View>
                        ))}
                    </View>
                )}

                {/* Waiting */}
                {filtered.waiting.length > 0 && (
                    <View style={styles.section}>
                        <View style={styles.sectionHeader}>
                            <Ionicons name="time" size={14} color={Colors.accentPrecision} />
                            <DonnaText style={[styles.sectionTitle, { color: Colors.accentPrecision }]}>WAITING FOR</DonnaText>
                        </View>
                        {filtered.waiting.map(task => (
                            <View key={task.id} style={styles.taskContainer}>
                                <InlineTaskItem
                                            task={task}
                                            onApprove={approve}
                                            onComplete={complete}
                                            onStart={start}
                                            onDismiss={dismiss}
                                        />
                            </View>
                        ))}
                    </View>
                )}

                {/* Empty State */}
                {filtered.pending.length === 0 && filtered.active.length === 0 && filtered.waiting.length === 0 && (
                    <View style={styles.emptyContainer}>
                        <DonnaText style={styles.emptyText}>Nothing here yet.</DonnaText>
                    </View>
                )}

                {/* Completed Section (Collapsible) */}
                {completedTasks.length > 0 && (
                    <TouchableOpacity
                        style={styles.completedHeader}
                        onPress={() => setShowCompleted(!showCompleted)}
                    >
                        <DonnaText style={styles.completedTitle}>Completed (last 24h)</DonnaText>
                        <Ionicons name={showCompleted ? "chevron-up" : "chevron-down"} size={18} color={Colors.textMuted} />
                    </TouchableOpacity>
                )}
                {showCompleted && completedTasks.map(task => (
                    <View key={task.id} style={styles.taskContainer}>
                        <InlineTaskItem
                                            task={task}
                                            onApprove={approve}
                                            onComplete={complete}
                                            onStart={start}
                                            onDismiss={dismiss}
                                        />
                    </View>
                ))}
            </ScrollView>
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
        paddingHorizontal: Spacing.md,
        backgroundColor: Colors.bgBase,
        paddingBottom: Spacing.sm,
    },
    title: {
        marginBottom: Spacing.md,
    },
    filterScroll: {
        marginBottom: Spacing.md,
    },
    filterChip: {
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderRadius: Radius.full,
        backgroundColor: Colors.bgSurface,
        borderWidth: 1,
        borderColor: Colors.border,
        marginRight: Spacing.sm,
    },
    filterChipActive: {
        backgroundColor: Colors.accentPrecision,
        borderColor: Colors.accentPrecision,
    },
    filterChipActiveAmber: {
        backgroundColor: Colors.accentSecondary,
        borderColor: Colors.accentSecondary,
    },
    filterChipActivePurple: {
        backgroundColor: Colors.accentPrecision,
        borderColor: Colors.accentPrecision,
    },
    filterChipText: {
        fontSize: 13,
        fontWeight: '600',
        color: Colors.textSecondary,
    },
    filterChipTextActive: {
        color: '#FFFFFF',
    },
    statsRow: {
        flexDirection: 'row',
        gap: Spacing.sm,
        flexWrap: 'wrap',
    },
    statBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        paddingHorizontal: Spacing.sm,
        paddingVertical: 4,
        borderRadius: Radius.full,
        borderWidth: 1,
    },
    statText: {
        fontSize: 11,
        fontWeight: '700',
    },
    listContent: {
        paddingBottom: Spacing.xl,
    },
    section: {
        paddingHorizontal: Spacing.md,
        marginBottom: Spacing.lg,
    },
    sectionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        marginBottom: Spacing.sm,
    },
    sectionTitle: {
        fontSize: 11,
        fontWeight: '700',
        letterSpacing: 1,
        textTransform: 'uppercase',
    },
    taskContainer: {
        marginBottom: Spacing.sm,
    },
    emptyContainer: {
        padding: Spacing.xl,
        alignItems: 'center',
    },
    emptyText: {
        color: Colors.textMuted,
        marginTop: Spacing.lg,
    },
    completedHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.md,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        marginTop: Spacing.md,
    },
    completedTitle: {
        color: Colors.textMuted,
        fontWeight: '600',
    },
});
