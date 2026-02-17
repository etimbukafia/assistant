import React from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Alert, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { formatDistanceToNow, parseISO, format } from 'date-fns';
import { useChat } from '@/src/context/ChatContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    fetchTask,
    approveTask,
    dismissTask,
    completeTask,
    snoozeTask,
    Task
} from '@/src/services/tasks';

export default function TaskDetailScreen() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const router = useRouter();
    const { openChat } = useChat();
    const queryClient = useQueryClient();

    // Fetch task from API
    const { data: task, isLoading, error } = useQuery({
        queryKey: ['task', id],
        queryFn: () => fetchTask(parseInt(id as string)),
        enabled: !!id,
    });

    // Mutations
    const approveMutation = useMutation({
        mutationFn: () => approveTask(parseInt(id as string)),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['task', id] });
            queryClient.invalidateQueries({ queryKey: ['tasks'] });
            Alert.alert('Task Approved', 'This task has been added to your active list.');
        },
        onError: () => Alert.alert('Error', 'Failed to approve task'),
    });

    const dismissMutation = useMutation({
        mutationFn: () => dismissTask(parseInt(id as string)),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['tasks'] });
            Alert.alert('Task Dismissed', 'This task has been removed.');
            router.back();
        },
        onError: () => Alert.alert('Error', 'Failed to dismiss task'),
    });

    const completeMutation = useMutation({
        mutationFn: () => completeTask(parseInt(id as string)),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['task', id] });
            queryClient.invalidateQueries({ queryKey: ['tasks'] });
            Alert.alert('Task Completed', 'Great job!');
        },
        onError: () => Alert.alert('Error', 'Failed to complete task'),
    });

    const snoozeMutation = useMutation({
        mutationFn: () => {
            // Snooze for 24 hours
            const snoozeUntil = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
            return snoozeTask(parseInt(id as string), snoozeUntil);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['task', id] });
            queryClient.invalidateQueries({ queryKey: ['tasks'] });
            Alert.alert('Task Snoozed', "We'll remind you in 24 hours.");
        },
        onError: () => Alert.alert('Error', 'Failed to snooze task'),
    });

    const isActionLoading = approveMutation.isPending || dismissMutation.isPending ||
        completeMutation.isPending || snoozeMutation.isPending;

    // Loading state
    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                </View>
            </SafeAreaView>
        );
    }

    // Error/Not found state
    if (error || !task) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                </View>
                <View style={styles.errorContainer}>
                    <Ionicons name="alert-circle-outline" size={48} color={Colors.textMuted} />
                    <DonnaText style={styles.errorText}>Task not found</DonnaText>
                </View>
            </SafeAreaView>
        );
    }

    const getPriorityColor = (priority: string) => {
        switch (priority) {
            case 'urgent': return Colors.error;
            case 'high': return Colors.accentPrimary;
            case 'normal': return Colors.accentPrecision;
            case 'low': return Colors.textMuted;
            default: return Colors.textMuted;
        }
    };

    const getStatusInfo = (status: string) => {
        switch (status) {
            case 'completed': return { label: 'Completed', color: Colors.success, icon: 'checkmark-circle' };
            case 'pending_approval': return { label: 'Pending Approval', color: Colors.accentSecondary, icon: 'sparkles' };
            case 'waiting_for': return { label: 'Waiting For Response', color: Colors.accentPrecision, icon: 'hourglass' };
            case 'dismissed': return { label: 'Dismissed', color: Colors.textMuted, icon: 'close-circle' };
            default: return { label: 'Active', color: Colors.textPrimary, icon: 'ellipse-outline' };
        }
    };

    const statusInfo = getStatusInfo(task.status);
    const priorityColor = getPriorityColor(task.priority);

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <View style={styles.headerActions}>
                    <TouchableOpacity style={styles.actionButton} onPress={openChat}>
                        <Ionicons name="sparkles" size={22} color={Colors.accentSecondary} />
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Priority Badge */}
                <View style={[styles.priorityBadge, { backgroundColor: priorityColor + '15' }]}>
                    <View style={[styles.priorityDot, { backgroundColor: priorityColor }]} />
                    <DonnaText style={[styles.priorityText, { color: priorityColor }]}>
                        {task.priority.toUpperCase()} PRIORITY
                    </DonnaText>
                </View>

                {/* Title */}
                <DonnaText variant="h2" style={styles.title}>{task.title}</DonnaText>

                {/* Status Chip */}
                <View style={[styles.statusChip, { backgroundColor: statusInfo.color + '12' }]}>
                    <Ionicons name={statusInfo.icon as any} size={16} color={statusInfo.color} />
                    <DonnaText style={[styles.statusText, { color: statusInfo.color }]}>
                        {statusInfo.label}
                    </DonnaText>
                </View>

                {/* Description */}
                {task.description && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>DESCRIPTION</DonnaText>
                        <DonnaText style={styles.descriptionText}>{task.description}</DonnaText>
                    </View>
                )}

                {/* Deadline */}
                {task.deadline_at && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>DEADLINE</DonnaText>
                        <View style={styles.deadlineRow}>
                            <Ionicons name="calendar-outline" size={18} color={Colors.textSecondary} />
                            <DonnaText style={styles.deadlineText}>
                                {format(parseISO(task.deadline_at), 'EEEE, MMMM d, yyyy')}
                            </DonnaText>
                        </View>
                        <DonnaText style={styles.deadlineRelative}>
                            {formatDistanceToNow(parseISO(task.deadline_at), { addSuffix: true })}
                        </DonnaText>
                    </View>
                )}

                {/* Source Message */}
                {task.message_id && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>EXTRACTED FROM</DonnaText>
                        <TouchableOpacity
                            style={styles.sourceCard}
                            onPress={() => router.push(`/inbox/${task.message_id}` as any)}
                        >
                            <Ionicons name="mail-outline" size={20} color={Colors.accentSecondary} />
                            <View style={styles.sourceTextContainer}>
                                <DonnaText style={styles.sourceTitle}>View Original Email</DonnaText>
                                <DonnaText style={styles.sourceSubtitle}>Tap to see the message this task came from</DonnaText>
                            </View>
                            <Ionicons name="chevron-forward" size={20} color={Colors.textMuted} />
                        </TouchableOpacity>
                    </View>
                )}

                {/* AI Suggested Indicator */}
                {task.status === 'pending_approval' && (
                    <View style={styles.aiSuggestionCard}>
                        <Ionicons name="sparkles" size={20} color={Colors.accentSecondary} />
                        <View style={styles.aiSuggestionText}>
                            <DonnaText style={styles.aiSuggestionTitle}>Suggested by TEEKS</DonnaText>
                            <DonnaText style={styles.aiSuggestionSubtitle}>
                                TEEKS detected this task in your email. Approve to add it to your list.
                            </DonnaText>
                        </View>
                    </View>
                )}
            </ScrollView>

            {/* Action Bar */}
            <View style={styles.actionBar}>
                {task.status === 'pending_approval' ? (
                    <>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.dismissBtn]}
                            onPress={() => dismissMutation.mutate()}
                            disabled={isActionLoading}
                        >
                            <Ionicons name="close" size={20} color={Colors.textSecondary} />
                            <DonnaText style={styles.dismissText}>Dismiss</DonnaText>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.approveBtn]}
                            onPress={() => approveMutation.mutate()}
                            disabled={isActionLoading}
                        >
                            {approveMutation.isPending ? (
                                <ActivityIndicator size="small" color="#FFF" />
                            ) : (
                                <>
                                    <Ionicons name="checkmark" size={20} color="#FFF" />
                                    <DonnaText style={styles.approveText}>Approve</DonnaText>
                                </>
                            )}
                        </TouchableOpacity>
                    </>
                ) : task.status !== 'completed' && task.status !== 'dismissed' ? (
                    <>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.snoozeBtn]}
                            onPress={() => snoozeMutation.mutate()}
                            disabled={isActionLoading}
                        >
                            <Ionicons name="moon-outline" size={18} color={Colors.textSecondary} />
                            <DonnaText style={styles.snoozeText}>Snooze</DonnaText>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.completeBtn]}
                            onPress={() => completeMutation.mutate()}
                            disabled={isActionLoading}
                        >
                            {completeMutation.isPending ? (
                                <ActivityIndicator size="small" color="#FFF" />
                            ) : (
                                <>
                                    <Ionicons name="checkmark-circle" size={20} color="#FFF" />
                                    <DonnaText style={styles.completeText}>Complete</DonnaText>
                                </>
                            )}
                        </TouchableOpacity>
                    </>
                ) : (
                    <View style={styles.completedBanner}>
                        <Ionicons name={task.status === 'completed' ? 'checkmark-circle' : 'close-circle'} size={24} color={task.status === 'completed' ? Colors.success : Colors.textMuted} />
                        <DonnaText style={[styles.completedText, { color: task.status === 'completed' ? Colors.success : Colors.textMuted }]}>
                            {task.status === 'completed' ? 'Task Completed' : 'Task Dismissed'}
                        </DonnaText>
                    </View>
                )}
            </View>
        </SafeAreaView>
    );
}

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
    errorContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        gap: Spacing.md,
    },
    errorText: {
        fontSize: 16,
        color: Colors.textMuted,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    backButton: {
        padding: Spacing.xs,
    },
    headerActions: {
        flexDirection: 'row',
        gap: Spacing.md,
    },
    actionButton: {
        padding: Spacing.xs,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 120,
    },
    priorityBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        alignSelf: 'flex-start',
        gap: 6,
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: Radius.full,
        marginBottom: Spacing.md,
    },
    priorityDot: {
        width: 6,
        height: 6,
        borderRadius: 3,
    },
    priorityText: {
        fontSize: 11,
        fontWeight: '700',
        letterSpacing: 0.5,
    },
    title: {
        marginBottom: Spacing.md,
    },
    statusChip: {
        flexDirection: 'row',
        alignItems: 'center',
        alignSelf: 'flex-start',
        gap: 6,
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: Radius.full,
        marginBottom: Spacing.xl,
    },
    statusText: {
        fontSize: 13,
        fontWeight: '600',
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
    },
    descriptionText: {
        fontSize: 16,
        color: Colors.textPrimary,
        lineHeight: 24,
    },
    deadlineRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
    },
    deadlineText: {
        fontSize: 16,
        color: Colors.textPrimary,
    },
    deadlineRelative: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 4,
        marginLeft: 26,
    },
    sourceCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    sourceTextContainer: {
        flex: 1,
    },
    sourceTitle: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    sourceSubtitle: {
        fontSize: 13,
        color: Colors.textMuted,
    },
    aiSuggestionCard: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: 'rgba(217, 119, 69, 0.08)',
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
        borderStyle: 'dashed',
    },
    aiSuggestionText: {
        flex: 1,
    },
    aiSuggestionTitle: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.accentSecondary,
    },
    aiSuggestionSubtitle: {
        fontSize: 13,
        color: Colors.textSecondary,
        marginTop: 2,
    },
    actionBar: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        flexDirection: 'row',
        gap: Spacing.md,
        padding: Spacing.md,
        paddingBottom: Spacing.xl,
        backgroundColor: Colors.bgElevated,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    actionBtn: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        paddingVertical: 14,
        borderRadius: Radius.full,
    },
    dismissBtn: {
        backgroundColor: Colors.bgBase,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    dismissText: {
        color: Colors.textSecondary,
        fontWeight: '600',
    },
    approveBtn: {
        backgroundColor: Colors.accentSecondary,
    },
    approveText: {
        color: '#FFF',
        fontWeight: '600',
    },
    snoozeBtn: {
        backgroundColor: Colors.bgBase,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    snoozeText: {
        color: Colors.textSecondary,
        fontWeight: '600',
    },
    completeBtn: {
        backgroundColor: Colors.success,
    },
    completeText: {
        color: '#FFF',
        fontWeight: '600',
    },
    completedBanner: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        paddingVertical: 14,
    },
    completedText: {
        fontSize: 16,
        fontWeight: '600',
    },
});
