import React from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Alert, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { format, parseISO } from 'date-fns';
import { useChat } from '@/src/context/ChatContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchCalendarEvent, generateFollowUps, CalendarEvent } from '@/src/services/calendar';

export default function EventDetailScreen() {
    const { id } = useLocalSearchParams<{ id: string }>();
    const router = useRouter();
    const { openChat } = useChat();
    const queryClient = useQueryClient();

    // Fetch event from API
    const { data: event, isLoading, error } = useQuery({
        queryKey: ['calendarEvent', id],
        queryFn: () => fetchCalendarEvent(parseInt(id as string)),
        enabled: !!id,
    });

    // Generate follow-ups mutation
    const followUpsMutation = useMutation({
        mutationFn: () => generateFollowUps(parseInt(id as string)),
        onSuccess: (data) => {
            const count = data.follow_ups?.length || 0;
            Alert.alert(
                'Follow-ups Generated',
                `Donna has created ${count} follow-up item${count !== 1 ? 's' : ''} based on this meeting.`,
                [{ text: 'View Tasks', onPress: () => router.push('/(tabs)/focus' as any) }]
            );
            queryClient.invalidateQueries({ queryKey: ['tasks'] });
        },
        onError: () => Alert.alert('Error', 'Failed to generate follow-ups'),
    });

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
    if (error || !event) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <DonnaText style={styles.headerTitle}>Event</DonnaText>
                    <View style={styles.headerPlaceholder} />
                </View>
                <View style={styles.errorContainer}>
                    <Ionicons name="calendar-outline" size={48} color={Colors.textMuted} />
                    <DonnaText style={styles.errorText}>Event not found</DonnaText>
                </View>
            </SafeAreaView>
        );
    }

    const startTime = parseISO(event.start_time);
    const endTime = parseISO(event.end_time);
    const briefing = event.briefing;

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Event</DonnaText>
                <TouchableOpacity style={styles.actionButton} onPress={openChat}>
                    <Ionicons name="sparkles" size={22} color={Colors.accentSecondary} />
                </TouchableOpacity>
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Event Title */}
                <DonnaText variant="h2" style={styles.title}>{event.title}</DonnaText>

                {/* Time & Location */}
                <View style={styles.metaCard}>
                    <View style={styles.metaRow}>
                        <Ionicons name="time-outline" size={20} color={Colors.accentSecondary} />
                        <View>
                            <DonnaText style={styles.metaDate}>
                                {format(startTime, 'EEEE, MMMM d, yyyy')}
                            </DonnaText>
                            <DonnaText style={styles.metaTime}>
                                {format(startTime, 'h:mm a')} - {format(endTime, 'h:mm a')}
                            </DonnaText>
                        </View>
                    </View>

                    {event.location && (
                        <View style={styles.metaRow}>
                            <Ionicons name="location-outline" size={20} color={Colors.accentPrecision} />
                            <DonnaText style={styles.metaLocation}>{event.location}</DonnaText>
                        </View>
                    )}
                </View>

                {/* Description */}
                {event.description && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>DESCRIPTION</DonnaText>
                        <DonnaText style={styles.descriptionText}>{event.description}</DonnaText>
                    </View>
                )}

                {/* Participants */}
                {event.participants && event.participants.length > 0 && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>PARTICIPANTS</DonnaText>
                        <View style={styles.participantsList}>
                            {event.participants.map((email, idx) => (
                                <View key={idx} style={styles.participantRow}>
                                    <View style={styles.participantAvatar}>
                                        <DonnaText style={styles.avatarText}>
                                            {email[0]?.toUpperCase() || '?'}
                                        </DonnaText>
                                    </View>
                                    <DonnaText style={styles.participantEmail}>{email}</DonnaText>
                                </View>
                            ))}
                        </View>
                    </View>
                )}

                {/* AI Briefing */}
                {briefing && (
                    <View style={styles.briefingSection}>
                        <View style={styles.briefingHeader}>
                            <Ionicons name="sparkles" size={18} color={Colors.accentSecondary} />
                            <DonnaText style={styles.briefingTitle}>AI BRIEFING</DonnaText>
                        </View>

                        {/* Agenda */}
                        {briefing.agenda && (
                            <View style={styles.briefingCard}>
                                <DonnaText style={styles.briefingCardTitle}>Agenda</DonnaText>
                                <DonnaText style={styles.agendaText}>{briefing.agenda}</DonnaText>
                            </View>
                        )}

                        {/* Prep Warnings */}
                        {briefing.prep_warnings && briefing.prep_warnings.length > 0 && (
                            <View style={[styles.briefingCard, styles.warningCard]}>
                                <DonnaText style={styles.briefingCardTitle}>Prep Notes</DonnaText>
                                {briefing.prep_warnings.map((warning, idx) => (
                                    <View key={idx} style={styles.warningItem}>
                                        <Ionicons
                                            name={warning.severity === 'high' ? 'warning' : 'information-circle'}
                                            size={16}
                                            color={warning.severity === 'high' ? Colors.error : Colors.accentSecondary}
                                        />
                                        <View style={styles.warningContent}>
                                            <DonnaText style={styles.warningMessage}>{warning.message}</DonnaText>
                                            {warning.suggestion && (
                                                <DonnaText style={styles.warningSuggestion}>{warning.suggestion}</DonnaText>
                                            )}
                                        </View>
                                    </View>
                                ))}
                            </View>
                        )}

                        {/* Open Tasks */}
                        {briefing.open_tasks && briefing.open_tasks.length > 0 && (
                            <View style={styles.briefingCard}>
                                <DonnaText style={styles.briefingCardTitle}>Related Tasks</DonnaText>
                                {briefing.open_tasks.map((task, idx) => (
                                    <TouchableOpacity
                                        key={idx}
                                        style={styles.taskItem}
                                        onPress={() => router.push(`/details/task?id=${task.id}` as any)}
                                    >
                                        <Ionicons name="checkbox-outline" size={16} color={Colors.accentPrecision} />
                                        <DonnaText style={styles.taskTitle} numberOfLines={1}>{task.title}</DonnaText>
                                        <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
                                    </TouchableOpacity>
                                ))}
                            </View>
                        )}
                    </View>
                )}

                {/* Related Emails */}
                {briefing?.related_emails && briefing.related_emails.length > 0 && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>RELATED EMAILS</DonnaText>
                        {briefing.related_emails.map((email, idx) => (
                            <TouchableOpacity
                                key={idx}
                                style={styles.emailCard}
                                onPress={() => router.push(`/inbox/${email.id}` as any)}
                            >
                                <Ionicons name="mail-outline" size={18} color={Colors.textMuted} />
                                <View style={styles.emailInfo}>
                                    <DonnaText style={styles.emailSubject} numberOfLines={1}>{email.subject}</DonnaText>
                                    <DonnaText style={styles.emailMeta}>{email.sender}</DonnaText>
                                </View>
                                <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
                            </TouchableOpacity>
                        ))}
                    </View>
                )}

                {/* Source Message Link */}
                {event.source_message_id && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>SOURCE</DonnaText>
                        <TouchableOpacity
                            style={styles.emailCard}
                            onPress={() => router.push(`/inbox/${event.source_message_id}` as any)}
                        >
                            <Ionicons name="mail-outline" size={18} color={Colors.accentSecondary} />
                            <View style={styles.emailInfo}>
                                <DonnaText style={styles.emailSubject}>View Original Email</DonnaText>
                                <DonnaText style={styles.emailMeta}>This event was created from an email</DonnaText>
                            </View>
                            <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
                        </TouchableOpacity>
                    </View>
                )}
            </ScrollView>

            {/* Bottom Action */}
            <View style={styles.actionBar}>
                <TouchableOpacity
                    style={[styles.followUpButton, followUpsMutation.isPending && styles.buttonDisabled]}
                    onPress={() => followUpsMutation.mutate()}
                    disabled={followUpsMutation.isPending}
                >
                    {followUpsMutation.isPending ? (
                        <ActivityIndicator size="small" color="#FFF" />
                    ) : (
                        <>
                            <Ionicons name="sparkles" size={20} color="#FFF" />
                            <DonnaText style={styles.followUpText}>Generate Follow-ups</DonnaText>
                        </>
                    )}
                </TouchableOpacity>
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
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    backButton: {
        padding: Spacing.xs,
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    headerPlaceholder: {
        width: 32,
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
    title: {
        marginBottom: Spacing.lg,
    },
    metaCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        gap: Spacing.md,
        marginBottom: Spacing.xl,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    metaRow: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: Spacing.md,
    },
    metaDate: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    metaTime: {
        fontSize: 14,
        color: Colors.textSecondary,
        marginTop: 2,
    },
    metaLocation: {
        fontSize: 15,
        color: Colors.textPrimary,
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
        fontSize: 15,
        color: Colors.textSecondary,
        lineHeight: 22,
    },
    participantsList: {
        gap: Spacing.sm,
    },
    participantRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.sm,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.component,
    },
    participantAvatar: {
        width: 36,
        height: 36,
        borderRadius: 18,
        backgroundColor: Colors.accentPrecision,
        justifyContent: 'center',
        alignItems: 'center',
    },
    avatarText: {
        color: '#FFF',
        fontSize: 14,
        fontWeight: '600',
    },
    participantEmail: {
        flex: 1,
        fontSize: 14,
        color: Colors.textPrimary,
    },
    briefingSection: {
        marginBottom: Spacing.xl,
    },
    briefingHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        marginBottom: Spacing.md,
    },
    briefingTitle: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.accentSecondary,
        letterSpacing: 1,
    },
    briefingCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    warningCard: {
        backgroundColor: 'rgba(217, 119, 69, 0.06)',
        borderColor: Colors.accentSecondary,
    },
    briefingCardTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    agendaText: {
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 20,
    },
    warningItem: {
        flexDirection: 'row',
        gap: Spacing.sm,
        marginBottom: Spacing.sm,
    },
    warningContent: {
        flex: 1,
    },
    warningMessage: {
        fontSize: 14,
        color: Colors.textPrimary,
        lineHeight: 20,
    },
    warningSuggestion: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 2,
        fontStyle: 'italic',
    },
    taskItem: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        paddingVertical: Spacing.xs,
    },
    taskTitle: {
        flex: 1,
        fontSize: 14,
        color: Colors.textPrimary,
    },
    emailCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.component,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    emailInfo: {
        flex: 1,
    },
    emailSubject: {
        fontSize: 14,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    emailMeta: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 2,
    },
    actionBar: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: Spacing.md,
        paddingBottom: Spacing.xl,
        backgroundColor: Colors.bgElevated,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    followUpButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        backgroundColor: Colors.accentSecondary,
        paddingVertical: 14,
        borderRadius: Radius.full,
    },
    buttonDisabled: {
        opacity: 0.7,
    },
    followUpText: {
        color: '#FFF',
        fontSize: 16,
        fontWeight: '600',
    },
});
