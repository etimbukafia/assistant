import React, { useState, useMemo } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, ActivityIndicator, Modal, TextInput, Alert, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { InlineTaskItem } from '@/src/components/ui/InlineTaskItem';
import { SchedulingSuggestionCard, openCalendarToDate } from '@/src/components/ui/SchedulingSuggestionCard';
import { useChat } from '@/src/context/ChatContext';
import { useAuth } from '@/src/context/AuthContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    fetchMessage,
    archiveMessage,
    deleteMessage,
    generateDraftReply,
    getSchedulingSuggestions,
    sendSchedulingReply,
    dismissSchedulingSuggestion,
    Message,
    SchedulingSuggestion
} from '@/src/services/messages';
import { approveTask, dismissTask, completeTask, startTask, updateTask, createTask, Task } from '@/src/services/tasks';
import { createCalendarEvent } from '@/src/services/calendar';
import demoData from '@/src/data/demo_state.json';

export default function MessageDetailScreen() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const router = useRouter();
    const { openChat } = useChat();
    const { isSandbox } = useAuth();
    const queryClient = useQueryClient();

    // Local state
    const [showDraftModal, setShowDraftModal] = useState(false);
    const [draftText, setDraftText] = useState('');
    const [loadSchedulingSuggestions, setLoadSchedulingSuggestions] = useState(false);

    // Get demo message for sandbox mode with dynamic dates
    const demoMessage = useMemo(() => {
        if (!isSandbox) return null;
        const allMessages = demoData.messages as unknown as Message[];
        const msgIndex = allMessages.findIndex(m => m.id === parseInt(id as string));
        if (msgIndex === -1) return null;
        const msg = allMessages[msgIndex];
        // Apply same date transformation as inbox list
        const now = new Date();
        const date = new Date(now);
        if (msgIndex < 2) {
            date.setHours(now.getHours() - 2 - msgIndex * 2, 0, 0, 0);
        } else {
            date.setDate(date.getDate() - 1);
            date.setHours(14, 0, 0, 0);
        }
        return { ...msg, received_at: date.toISOString() };
    }, [isSandbox, id]);

    // Fetch message from API - disabled in sandbox mode
    // Use placeholderData from the messages list cache for instant display
    const { data: apiMessage, isLoading, error } = useQuery({
        queryKey: ['message', id],
        queryFn: () => fetchMessage(parseInt(id as string)),
        enabled: !!id && !isSandbox,
        placeholderData: () => {
            // Try to get the message from the messages list cache
            const cachedMessages = queryClient.getQueryData<{ messages: Message[] }>(['messages']);
            return cachedMessages?.messages?.find(m => m.id === parseInt(id as string));
        },
        staleTime: 1000 * 60 * 5, // 5 minutes
    });

    // Use demo data in sandbox mode, API data otherwise
    const message = isSandbox ? demoMessage : apiMessage;

    // Task mutations
    const approveMutation = useMutation({
        mutationFn: (taskId: number) => approveTask(taskId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['message', id] });
            queryClient.invalidateQueries({ queryKey: ['messages'] });
        },
    });

    const dismissMutation = useMutation({
        mutationFn: (taskId: number) => dismissTask(taskId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['message', id] });
        },
    });

    const completeMutation = useMutation({
        mutationFn: (taskId: number) => completeTask(taskId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['message', id] });
        },
    });

    const startMutation = useMutation({
        mutationFn: (taskId: number) => startTask(taskId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['message', id] });
        },
    });

    const updateMutation = useMutation({
        mutationFn: ({ taskId, data }: { taskId: number; data: Parameters<typeof updateTask>[1] }) =>
            updateTask(taskId, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['message', id] });
        },
    });

    // Create task from extracted suggestion
    const createTaskMutation = useMutation({
        mutationFn: (data: { title: string; priority?: string }) =>
            createTask({
                message_id: parseInt(id as string),
                title: data.title,
                priority: (data.priority as any) || 'normal',
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['message', id] });
        },
    });

    // Message actions
    const archiveMutation = useMutation({
        mutationFn: () => archiveMessage(parseInt(id as string)),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['messages'] });
            router.back();
        },
    });

    const deleteMutation = useMutation({
        mutationFn: () => deleteMessage(parseInt(id as string)),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['messages'] });
            router.back();
        },
    });

    // Fetch scheduling suggestions for this message - only when user requests it
    const { data: schedulingData, isLoading: isLoadingSuggestions } = useQuery({
        queryKey: ['scheduling-suggestions', id],
        queryFn: () => getSchedulingSuggestions(parseInt(id as string)),
        enabled: !!id && loadSchedulingSuggestions && !isSandbox,
    });

    const schedulingSuggestion = schedulingData?.suggestions?.[0];

    // Draft reply mutation
    const draftReplyMutation = useMutation({
        mutationFn: () => generateDraftReply(parseInt(id as string)),
        onSuccess: (data) => {
            setDraftText(data.draft);
            setShowDraftModal(true);
        },
        onError: () => {
            Alert.alert('Error', 'Failed to generate draft reply');
        },
    });

    // Scheduling mutations
    const sendSchedulingMutation = useMutation({
        mutationFn: (suggestionId: number) => sendSchedulingReply(suggestionId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['scheduling-suggestions', id] });
            queryClient.invalidateQueries({ queryKey: ['message', id] });
            Alert.alert('Sent', 'Your availability reply has been sent!');
        },
    });

    const dismissSchedulingMutation = useMutation({
        mutationFn: (suggestionId: number) => dismissSchedulingSuggestion(suggestionId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['scheduling-suggestions', id] });
        },
    });

    // Create calendar event mutation
    const createEventMutation = useMutation({
        mutationFn: ({ suggestionId, slotIndex }: { suggestionId: number; slotIndex: number }) =>
            createCalendarEvent({
                suggestion_id: suggestionId,
                selected_slot_index: slotIndex,
            }),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['scheduling-suggestions', id] });
            queryClient.invalidateQueries({ queryKey: ['calendar-events'] });

            // Get the selected slot for deep linking
            const selectedSlot = schedulingSuggestion?.time_slots?.[variables.slotIndex];

            Alert.alert(
                'Event Created!',
                'Your calendar event has been created successfully.',
                [
                    { text: 'Done', style: 'cancel' },
                    {
                        text: 'View in Calendar',
                        onPress: () => {
                            if (selectedSlot?.start_time) {
                                openCalendarToDate(selectedSlot.start_time);
                            }
                        },
                    },
                ]
            );
        },
        onError: (error: any) => {
            const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to create event';
            Alert.alert('Error', errorMessage);
        },
    });

    // Task handlers - show demo message in sandbox mode
    const handleApproveTask = (taskId: number) => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Task actions are disabled in demo mode. Connect your email to enable.');
            return;
        }
        approveMutation.mutate(taskId);
    };
    const handleCompleteTask = (taskId: number) => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Task actions are disabled in demo mode. Connect your email to enable.');
            return;
        }
        completeMutation.mutate(taskId);
    };
    const handleStartTask = (taskId: number) => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Task actions are disabled in demo mode. Connect your email to enable.');
            return;
        }
        startMutation.mutate(taskId);
    };
    const handleDismissTask = (taskId: number) => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Task actions are disabled in demo mode. Connect your email to enable.');
            return;
        }
        dismissMutation.mutate(taskId);
    };

    const handleApproveExtractedTask = (extractedTask: { title: string; priority?: string }) => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Task actions are disabled in demo mode. Connect your email to enable.');
            return;
        }
        createTaskMutation.mutate(extractedTask);
    };

    // Filter tasks for inline display
    const inlineTasks = (message?.tasks || []).filter(task =>
        task.status === 'pending_approval' ||
        task.status === 'approved' ||
        task.status === 'in_progress'
    );

    // Show extracted tasks only if no structured tasks exist
    const hasStructuredTasks = (message?.tasks || []).length > 0;
    const showExtractedTasks = !hasStructuredTasks && (message?.extracted_tasks || []).length > 0;

    // Show error state
    if (error) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                </View>
                <View style={styles.errorContainer}>
                    <Ionicons name="alert-circle-outline" size={48} color={Colors.error} />
                    <DonnaText style={styles.errorText}>Message not found</DonnaText>
                </View>
            </SafeAreaView>
        );
    }

    // Show minimal UI while waiting for data (should be very brief with placeholderData)
    if (!message) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                </View>
            </SafeAreaView>
        );
    }

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
                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => {
                            if (isSandbox) {
                                Alert.alert('Demo Mode', 'Archive is disabled in demo mode.');
                                return;
                            }
                            archiveMutation.mutate();
                        }}
                        disabled={archiveMutation.isPending}
                    >
                        <Ionicons name="archive-outline" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => {
                            if (isSandbox) {
                                Alert.alert('Demo Mode', 'Delete is disabled in demo mode.');
                                return;
                            }
                            deleteMutation.mutate();
                        }}
                        disabled={deleteMutation.isPending}
                    >
                        <Ionicons name="trash-outline" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView contentContainerStyle={styles.content}>
                {/* Subject & Meta */}
                <DonnaText variant="h2" style={styles.subject}>{message.subject}</DonnaText>

                <View style={styles.metaContainer}>
                    <View style={styles.senderAvatar}>
                        <DonnaText style={styles.avatarText}>{message.sender[0].toUpperCase()}</DonnaText>
                    </View>
                    <View>
                        <DonnaText variant="labelSmall" color={Colors.textPrimary}>{message.sender}</DonnaText>
                        <DonnaText variant="caption">
                            {formatDistanceToNow(parseISO(message.received_at), { addSuffix: true })} • to me
                        </DonnaText>
                    </View>
                </View>

                {/* AI Summary */}
                {message.summary && (
                    <View style={styles.summaryBox}>
                        <View style={styles.summaryHeader}>
                            <Ionicons name="sparkles" size={16} color={Colors.accentPrecision} />
                            <DonnaText variant="labelSmall" color={Colors.accentPrecision} style={styles.summaryLabel}>
                                CORTA'S SUMMARY
                            </DonnaText>
                        </View>
                        <DonnaText variant="bodyBase" style={styles.summaryText}>
                            {message.summary}
                        </DonnaText>
                    </View>
                )}

                {/* Extracted Task Suggestions (only if no structured tasks) */}
                {showExtractedTasks && (
                    <View style={styles.tasksContainer}>
                        <DonnaText variant="overline" style={styles.sectionTitle}>AI-DETECTED TASKS</DonnaText>
                        {message.extracted_tasks!.map((task, index) => (
                            <View key={index} style={styles.extractedTaskCard}>
                                <View style={styles.extractedTaskContent}>
                                    <DonnaText style={styles.extractedTaskTitle}>{task.title}</DonnaText>
                                    {task.deadline_text && (
                                        <DonnaText variant="caption" style={styles.extractedTaskDeadline}>
                                            {task.deadline_text}
                                        </DonnaText>
                                    )}
                                </View>
                                <TouchableOpacity
                                    style={styles.approveButton}
                                    onPress={() => handleApproveExtractedTask(task)}
                                    disabled={createTaskMutation.isPending}
                                >
                                    <Ionicons name="checkmark" size={18} color="#FFF" />
                                    <DonnaText style={styles.approveButtonText}>Approve</DonnaText>
                                </TouchableOpacity>
                            </View>
                        ))}
                    </View>
                )}

                {/* Inline Tasks */}
                {inlineTasks.length > 0 && (
                    <View style={styles.tasksContainer}>
                        <DonnaText variant="overline" style={styles.sectionTitle}>ACTIONS & INTELLIGENCE</DonnaText>
                        {inlineTasks.map(task => (
                            <InlineTaskItem
                                key={task.id}
                                task={task}
                                onApprove={handleApproveTask}
                                onComplete={handleCompleteTask}
                                onStart={handleStartTask}
                                onDismiss={handleDismissTask}
                            />
                        ))}
                    </View>
                )}

                {/* Scheduling Suggestion Card - only load on user request */}
                {message.scheduling_intent?.detected && !loadSchedulingSuggestions && (
                    <TouchableOpacity
                        style={styles.loadSuggestionsButton}
                        onPress={() => {
                            if (isSandbox) {
                                Alert.alert('Demo Mode', 'Scheduling suggestions are disabled in demo mode.');
                                return;
                            }
                            setLoadSchedulingSuggestions(true);
                        }}
                    >
                        <Ionicons name="calendar-outline" size={20} color={Colors.accentSecondary} />
                        <DonnaText style={styles.loadSuggestionsText}>Load Suggested Times</DonnaText>
                        <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
                    </TouchableOpacity>
                )}
                {message.scheduling_intent?.detected && loadSchedulingSuggestions && (
                    <SchedulingSuggestionCard
                        title={schedulingSuggestion?.suggested_title || 'Meeting'}
                        duration_minutes={schedulingSuggestion?.suggested_duration_minutes || 30}
                        attendees={schedulingSuggestion?.suggested_attendees || []}
                        time_slots={schedulingSuggestion?.time_slots || []}
                        draft_message={schedulingSuggestion?.draft_message}
                        onSelectSlot={(slotIndex) => {
                            if (schedulingSuggestion) {
                                createEventMutation.mutate({ suggestionId: schedulingSuggestion.id, slotIndex });
                            }
                        }}
                        onDismiss={schedulingSuggestion ? () => dismissSchedulingMutation.mutate(schedulingSuggestion.id) : undefined}
                        isLoading={createEventMutation.isPending}
                        isSlotsLoading={isLoadingSuggestions || !schedulingSuggestion}
                        error={null}
                    />
                )}

                {/* Body */}
                <View style={styles.bodyContainer}>
                    <DonnaText variant="bodyBase" style={styles.bodyText}>
                        {message.body}
                    </DonnaText>
                </View>
            </ScrollView>

            {/* Bottom Action Bar */}
            <View style={styles.bottomBar}>
                <TouchableOpacity
                    style={styles.replyButton}
                    onPress={() => {
                        if (isSandbox) {
                            Alert.alert('Demo Mode', 'Reply drafting is disabled in demo mode. Connect your email to enable.');
                            return;
                        }
                        draftReplyMutation.mutate();
                    }}
                    disabled={draftReplyMutation.isPending}
                >
                    {draftReplyMutation.isPending ? (
                        <ActivityIndicator size="small" color="#FFF" />
                    ) : (
                        <Ionicons name="return-up-back" size={20} color="#FFF" />
                    )}
                    <DonnaText style={styles.replyButtonText}>
                        {draftReplyMutation.isPending ? 'Drafting...' : 'Reply'}
                    </DonnaText>
                </TouchableOpacity>
                {message.scheduling_intent?.detected && (
                    <TouchableOpacity
                        style={[styles.replyButton, styles.scheduleButton]}
                        onPress={() => {
                            if (isSandbox) {
                                Alert.alert('Demo Mode', 'Scheduling is disabled in demo mode. Connect your email to enable.');
                            }
                        }}
                    >
                        <Ionicons name="calendar" size={20} color="#FFF" />
                        <DonnaText style={styles.replyButtonText}>Schedule</DonnaText>
                    </TouchableOpacity>
                )}
            </View>

            {/* Draft Reply Modal */}
            <Modal
                visible={showDraftModal}
                animationType="slide"
                presentationStyle="pageSheet"
                onRequestClose={() => setShowDraftModal(false)}
            >
                <KeyboardAvoidingView
                    behavior={Platform.OS === "ios" ? "padding" : "height"}
                    style={styles.modalContainer}
                >
                    <View style={styles.modalHeader}>
                        <TouchableOpacity onPress={() => setShowDraftModal(false)} style={styles.modalButton}>
                            <DonnaText style={styles.modalButtonText}>Cancel</DonnaText>
                        </TouchableOpacity>
                        <DonnaText style={styles.modalTitle}>Draft Reply</DonnaText>
                        <TouchableOpacity
                            style={styles.modalButton}
                            onPress={() => {
                                // In a real app, this would call sendReplyMutation
                                setShowDraftModal(false);
                                Alert.alert('Sent', 'Reply sent successfully');
                            }}
                        >
                            <DonnaText style={[styles.modalButtonText, { fontWeight: '600', color: Colors.accentSecondary }]}>Send</DonnaText>
                        </TouchableOpacity>
                    </View>
                    <View style={styles.modalContent}>
                        <TextInput
                            style={styles.draftInput}
                            multiline
                            value={draftText}
                            onChangeText={setDraftText}
                            placeholder="Type a reply..."
                            textAlignVertical="top"
                            autoFocus
                        />
                    </View>
                </KeyboardAvoidingView>
            </Modal>
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
    loadingText: {
        marginTop: Spacing.md,
        color: Colors.textMuted,
    },
    errorContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    errorText: {
        marginTop: Spacing.md,
        color: Colors.error,
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
    content: {
        padding: Spacing.md,
        paddingBottom: 100,
    },
    subject: {
        marginBottom: Spacing.md,
    },
    metaContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: Spacing.lg,
    },
    senderAvatar: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: Colors.border,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.sm,
    },
    avatarText: {
        fontSize: 18,
        fontWeight: 'bold',
        color: Colors.textSecondary,
    },
    summaryBox: {
        backgroundColor: 'rgba(30, 58, 138, 0.05)',
        padding: Spacing.md,
        borderRadius: Radius.surface,
        marginBottom: Spacing.lg,
        borderLeftWidth: 3,
        borderLeftColor: Colors.accentPrecision,
    },
    summaryHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        marginBottom: Spacing.xs,
    },
    summaryLabel: {
        fontWeight: 'bold',
    },
    summaryText: {
        fontStyle: 'italic',
        lineHeight: 24,
    },
    tasksContainer: {
        marginBottom: Spacing.lg,
    },
    sectionTitle: {
        marginBottom: Spacing.sm,
        marginLeft: Spacing.xs,
    },
    extractedTaskCard: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        padding: Spacing.md,
        borderRadius: Radius.component,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: 'rgba(245, 158, 11, 0.2)',
    },
    extractedTaskContent: {
        flex: 1,
        marginRight: Spacing.md,
    },
    extractedTaskTitle: {
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    extractedTaskDeadline: {
        color: Colors.textMuted,
        marginTop: 2,
    },
    approveButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        backgroundColor: Colors.accentSecondary,
        paddingVertical: 6,
        paddingHorizontal: 12,
        borderRadius: Radius.full,
    },
    approveButtonText: {
        color: '#FFF',
        fontWeight: '600',
        fontSize: 13,
    },
    loadSuggestionsButton: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: Spacing.md,
        marginTop: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        gap: Spacing.sm,
    },
    loadSuggestionsText: {
        flex: 1,
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    bodyContainer: {
        paddingTop: Spacing.md,
    },
    bodyText: {
        lineHeight: 24,
        color: Colors.textPrimary,
    },
    bottomBar: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: Colors.bgElevated,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        padding: Spacing.md,
        paddingBottom: Spacing.xl,
        flexDirection: 'row',
        gap: Spacing.md,
    },
    replyButton: {
        flex: 1,
        backgroundColor: Colors.textPrimary,
        borderRadius: Radius.full,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        paddingVertical: Spacing.md,
        gap: Spacing.sm,
    },
    scheduleButton: {
        backgroundColor: Colors.accentSecondary,
    },
    replyButtonText: {
        color: '#FFFFFF',
        fontWeight: '600',
        fontSize: 16,
    },
    modalContainer: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    modalTitle: {
        fontSize: 16,
        fontWeight: '600',
    },
    modalButton: {
        padding: Spacing.sm,
    },
    modalButtonText: {
        fontSize: 16,
        color: Colors.accentPrimary,
    },
    modalContent: {
        flex: 1,
        padding: Spacing.md,
    },
    draftInput: {
        flex: 1,
        fontSize: 16,
        lineHeight: 24,
        color: Colors.textPrimary,
        paddingTop: Spacing.sm,
    },
});
