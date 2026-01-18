import React, { useMemo, useState } from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import demoData from '@/src/data/demo_state.json';
import { Task } from '@/src/types/api';
import { formatDistanceToNow, parseISO, format } from 'date-fns';
import { useChat } from '@/src/context/ChatContext';

export default function TaskDetailScreen() {
    const { id } = useLocalSearchParams();
    const router = useRouter();
    const { openChat } = useChat();

    // Mock Data Fetch
    const task = useMemo(() => {
        const tasks = demoData.tasks as unknown as Task[];
        return tasks.find(t => t.id.toString() === id);
    }, [id]);

    const [currentStatus, setCurrentStatus] = useState(task?.status || 'pending');

    if (!task) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.errorContainer}>
                    <DonnaText>Task not found</DonnaText>
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
            case 'snoozed': return { label: 'Snoozed', color: Colors.textMuted, icon: 'moon' };
            default: return { label: 'Active', color: Colors.textPrimary, icon: 'ellipse-outline' };
        }
    };

    const statusInfo = getStatusInfo(currentStatus);
    const priorityColor = getPriorityColor(task.priority);

    const handleAction = (action: 'approve' | 'dismiss' | 'complete' | 'snooze') => {
        // Mock actions
        switch (action) {
            case 'approve':
                setCurrentStatus('pending');
                Alert.alert('Task Approved', 'This task has been added to your active list.');
                break;
            case 'dismiss':
                Alert.alert('Task Dismissed', 'This task has been removed.');
                router.back();
                break;
            case 'complete':
                setCurrentStatus('completed');
                Alert.alert('Task Completed', 'Great job!');
                break;
            case 'snooze':
                setCurrentStatus('snoozed');
                Alert.alert('Task Snoozed', 'We\'ll remind you later.');
                break;
        }
    };

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
                    <TouchableOpacity style={styles.actionButton}>
                        <Ionicons name="pencil-outline" size={22} color={Colors.textPrimary} />
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
                {task.deadline && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>DEADLINE</DonnaText>
                        <View style={styles.deadlineRow}>
                            <Ionicons name="calendar-outline" size={18} color={Colors.textSecondary} />
                            <DonnaText style={styles.deadlineText}>
                                {format(parseISO(task.deadline), 'EEEE, MMMM d, yyyy')}
                            </DonnaText>
                        </View>
                        <DonnaText style={styles.deadlineRelative}>
                            {formatDistanceToNow(parseISO(task.deadline), { addSuffix: true })}
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
                {currentStatus === 'pending_approval' && (
                    <View style={styles.aiSuggestionCard}>
                        <Ionicons name="sparkles" size={20} color={Colors.accentSecondary} />
                        <View style={styles.aiSuggestionText}>
                            <DonnaText style={styles.aiSuggestionTitle}>Suggested by AI</DonnaText>
                            <DonnaText style={styles.aiSuggestionSubtitle}>
                                Donna detected this task in your email. Approve to add it to your list.
                            </DonnaText>
                        </View>
                    </View>
                )}
            </ScrollView>

            {/* Action Bar */}
            <View style={styles.actionBar}>
                {currentStatus === 'pending_approval' ? (
                    <>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.dismissBtn]}
                            onPress={() => handleAction('dismiss')}
                        >
                            <Ionicons name="close" size={20} color={Colors.textSecondary} />
                            <DonnaText style={styles.dismissText}>Dismiss</DonnaText>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.approveBtn]}
                            onPress={() => handleAction('approve')}
                        >
                            <Ionicons name="checkmark" size={20} color="#FFF" />
                            <DonnaText style={styles.approveText}>Approve</DonnaText>
                        </TouchableOpacity>
                    </>
                ) : currentStatus !== 'completed' ? (
                    <>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.snoozeBtn]}
                            onPress={() => handleAction('snooze')}
                        >
                            <Ionicons name="moon-outline" size={18} color={Colors.textSecondary} />
                            <DonnaText style={styles.snoozeText}>Snooze</DonnaText>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.completeBtn]}
                            onPress={() => handleAction('complete')}
                        >
                            <Ionicons name="checkmark-circle" size={20} color="#FFF" />
                            <DonnaText style={styles.completeText}>Complete</DonnaText>
                        </TouchableOpacity>
                    </>
                ) : (
                    <View style={styles.completedBanner}>
                        <Ionicons name="checkmark-circle" size={24} color={Colors.success} />
                        <DonnaText style={styles.completedText}>Task Completed</DonnaText>
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
    errorContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
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
        color: Colors.success,
        fontSize: 16,
        fontWeight: '600',
    },
});
