import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, RefreshControl } from 'react-native';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import demoData from '../../src/data/demo_state.json';
import { Ionicons } from '@expo/vector-icons';
import { format, parseISO, isToday } from 'date-fns';

interface CalendarEvent {
    id: number;
    title: string;
    start_time: string;
    end_time: string;
    location?: string;
    status: 'upcoming' | 'completed';
    briefing?: {
        agenda?: string;
        prep_complete?: boolean;
        prep_warnings?: { message: string; severity: string; suggestion: string }[];
        attendees?: { name: string; email: string }[];
        related_emails?: { id: number; subject: string; sender: string }[];
        open_tasks?: { id: number; title: string; priority: string }[];
    } | null;
}

export default function CalendarScreen() {
    const [refreshing, setRefreshing] = useState(false);
    const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
    const [isSyncing, setIsSyncing] = useState(false);

    const events = demoData.calendar as CalendarEvent[];

    const onRefresh = React.useCallback(() => {
        setRefreshing(true);
        setTimeout(() => setRefreshing(false), 1000);
    }, []);

    const handleSync = () => {
        setIsSyncing(true);
        setTimeout(() => setIsSyncing(false), 2000);
    };

    const formatTime = (isoString: string) => {
        return format(parseISO(isoString), 'h:mm a');
    };

    const formatDateBadge = (isoString: string) => {
        const date = parseISO(isoString);
        if (isToday(date)) return 'Today';
        return format(date, 'MMM d');
    };

    return (
        <View style={styles.container}>
            <StatusBar style="dark" />
            <ScrollView
                refreshControl={
                    <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accentPrimary} />
                }
                contentContainerStyle={styles.listContent}
            >
                {/* Header */}
                <View style={styles.header}>
                    <View>
                        <DonnaText variant="h1" style={styles.title}>Meetings</DonnaText>
                        <DonnaText variant="caption" style={styles.subtitle}>Upcoming briefings and follow-ups</DonnaText>
                    </View>
                    <TouchableOpacity
                        onPress={handleSync}
                        style={[styles.syncButton, isSyncing && styles.syncButtonDisabled]}
                        disabled={isSyncing}
                    >
                        <Ionicons name="refresh" size={20} color={isSyncing ? Colors.textMuted : Colors.accentPrecision} />
                    </TouchableOpacity>
                </View>

                {/* Events List */}
                {events.length === 0 ? (
                    <View style={styles.emptyContainer}>
                        <Ionicons name="calendar-outline" size={48} color={Colors.textMuted} />
                        <DonnaText variant="h2" style={styles.emptyTitle}>No meetings found</DonnaText>
                        <DonnaText variant="caption" style={styles.emptyText}>Your calendar looks clear for the next few days.</DonnaText>
                        <TouchableOpacity style={styles.syncButtonLarge} onPress={handleSync}>
                            <DonnaText style={styles.syncButtonText}>Sync Calendar</DonnaText>
                        </TouchableOpacity>
                    </View>
                ) : (
                    events.map(event => (
                        <View key={event.id} style={styles.eventSection}>
                            <TouchableOpacity
                                style={[
                                    styles.eventCard,
                                    selectedEventId === event.id && styles.eventCardSelected
                                ]}
                                onPress={() => setSelectedEventId(selectedEventId === event.id ? null : event.id)}
                            >
                                <View style={styles.eventHeader}>
                                    <View style={styles.eventBadges}>
                                        <View style={[
                                            styles.statusBadge,
                                            event.status === 'completed' ? styles.statusBadgePast : styles.statusBadgeUpcoming
                                        ]}>
                                            <DonnaText style={[
                                                styles.statusBadgeText,
                                                event.status === 'completed' ? styles.statusBadgeTextPast : styles.statusBadgeTextUpcoming
                                            ]}>
                                                {event.status === 'completed' ? 'Past' : formatDateBadge(event.start_time)}
                                            </DonnaText>
                                        </View>
                                        {event.briefing && !event.briefing.prep_complete && (
                                            <View style={styles.prepBadge}>
                                                <Ionicons name="sparkles" size={10} color="#D97706" />
                                                <DonnaText style={styles.prepBadgeText}>Prep Needed</DonnaText>
                                            </View>
                                        )}
                                    </View>
                                    <Ionicons
                                        name={selectedEventId === event.id ? "chevron-up" : "chevron-forward"}
                                        size={18}
                                        color={selectedEventId === event.id ? Colors.accentPrecision : Colors.textMuted}
                                    />
                                </View>
                                <DonnaText variant="bodyLarge" style={styles.eventTitle}>{event.title}</DonnaText>
                                <View style={styles.eventMeta}>
                                    <View style={styles.eventMetaItem}>
                                        <Ionicons name="time-outline" size={14} color={Colors.textMuted} />
                                        <DonnaText variant="caption">{formatTime(event.start_time)} – {formatTime(event.end_time)}</DonnaText>
                                    </View>
                                    {event.location && (
                                        <View style={styles.eventMetaItem}>
                                            <Ionicons name="location-outline" size={14} color={Colors.textMuted} />
                                            <DonnaText variant="caption">{event.location}</DonnaText>
                                        </View>
                                    )}
                                </View>
                            </TouchableOpacity>

                            {/* Expanded Briefing */}
                            {selectedEventId === event.id && event.briefing && (
                                <View style={styles.briefingCard}>
                                    {/* Prep Status Header */}
                                    <View style={[
                                        styles.prepHeader,
                                        event.briefing.prep_complete ? styles.prepHeaderComplete : styles.prepHeaderNeeded
                                    ]}>
                                        <View style={styles.prepHeaderContent}>
                                            <Ionicons
                                                name={event.briefing.prep_complete ? "checkmark-circle" : "alert-circle"}
                                                size={18}
                                                color={event.briefing.prep_complete ? "#16A34A" : "#D97706"}
                                            />
                                            <DonnaText style={[
                                                styles.prepHeaderText,
                                                event.briefing.prep_complete ? styles.prepHeaderTextComplete : styles.prepHeaderTextNeeded
                                            ]}>
                                                {event.briefing.prep_complete ? 'Prep Complete' : 'Needs Preparation'}
                                            </DonnaText>
                                        </View>
                                        {!event.briefing.prep_complete && event.briefing.prep_warnings && (
                                            <View style={styles.warningCountBadge}>
                                                <DonnaText style={styles.warningCountText}>
                                                    {event.briefing.prep_warnings.length} Warning{event.briefing.prep_warnings.length !== 1 ? 's' : ''}
                                                </DonnaText>
                                            </View>
                                        )}
                                    </View>

                                    {/* Agenda */}
                                    {event.briefing.agenda && (
                                        <View style={styles.briefingSection}>
                                            <View style={styles.briefingSectionHeader}>
                                                <Ionicons name="information-circle-outline" size={12} color={Colors.textMuted} />
                                                <DonnaText style={styles.briefingSectionTitle}>AGENDA</DonnaText>
                                            </View>
                                            <DonnaText variant="bodyBase" style={styles.agendaText}>{event.briefing.agenda}</DonnaText>
                                        </View>
                                    )}

                                    {/* Prep Warnings */}
                                    {event.briefing.prep_warnings && event.briefing.prep_warnings.length > 0 && (
                                        <View style={styles.briefingSection}>
                                            <View style={styles.briefingSectionHeader}>
                                                <Ionicons name="alert-circle-outline" size={12} color={Colors.textMuted} />
                                                <DonnaText style={styles.briefingSectionTitle}>PREP WARNINGS</DonnaText>
                                            </View>
                                            {event.briefing.prep_warnings.map((warning, idx) => (
                                                <View key={idx} style={styles.warningItem}>
                                                    <View style={[
                                                        styles.warningIcon,
                                                        warning.severity === 'high' ? styles.warningIconHigh : styles.warningIconMedium
                                                    ]}>
                                                        <Ionicons name="alert-circle" size={14} color={warning.severity === 'high' ? '#DC2626' : '#D97706'} />
                                                    </View>
                                                    <View style={styles.warningContent}>
                                                        <DonnaText variant="bodyBase" style={styles.warningMessage}>{warning.message}</DonnaText>
                                                        <DonnaText variant="caption" style={styles.warningSuggestion}>{warning.suggestion}</DonnaText>
                                                    </View>
                                                </View>
                                            ))}
                                        </View>
                                    )}

                                    {/* Attendees */}
                                    {event.briefing.attendees && event.briefing.attendees.length > 0 && (
                                        <View style={styles.briefingSection}>
                                            <View style={styles.briefingSectionHeader}>
                                                <Ionicons name="people-outline" size={12} color={Colors.textMuted} />
                                                <DonnaText style={styles.briefingSectionTitle}>KEY PARTICIPANTS</DonnaText>
                                            </View>
                                            <View style={styles.attendeesList}>
                                                {event.briefing.attendees.map((person, idx) => (
                                                    <View key={idx} style={styles.attendeeChip}>
                                                        <View style={styles.attendeeAvatar}>
                                                            <DonnaText style={styles.attendeeInitial}>
                                                                {(person.name || person.email || '?')[0].toUpperCase()}
                                                            </DonnaText>
                                                        </View>
                                                        <DonnaText style={styles.attendeeName}>{person.name || person.email}</DonnaText>
                                                    </View>
                                                ))}
                                            </View>
                                        </View>
                                    )}
                                </View>
                            )}
                        </View>
                    ))
                )}
            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    listContent: {
        paddingBottom: Spacing.xl,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        paddingHorizontal: Spacing.md,
        paddingTop: Spacing.xl,
        paddingBottom: Spacing.md,
        backgroundColor: Colors.bgBase,
    },
    title: {
        marginBottom: Spacing.xs,
    },
    subtitle: {
        color: Colors.textMuted,
    },
    syncButton: {
        padding: Spacing.sm,
        backgroundColor: 'rgba(30, 58, 138, 0.1)',
        borderRadius: Radius.full,
    },
    syncButtonDisabled: {
        backgroundColor: Colors.border,
    },
    emptyContainer: {
        alignItems: 'center',
        padding: Spacing.xl,
        marginHorizontal: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        borderWidth: 2,
        borderColor: Colors.border,
        borderStyle: 'dashed',
    },
    emptyTitle: {
        marginTop: Spacing.md,
        marginBottom: Spacing.xs,
    },
    emptyText: {
        color: Colors.textMuted,
        marginBottom: Spacing.lg,
        textAlign: 'center',
    },
    syncButtonLarge: {
        backgroundColor: Colors.accentPrecision,
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.md,
        borderRadius: Radius.full,
    },
    syncButtonText: {
        color: '#FFFFFF',
        fontWeight: '600',
    },
    eventSection: {
        marginHorizontal: Spacing.md,
        marginBottom: Spacing.md,
    },
    eventCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    eventCardSelected: {
        borderColor: Colors.accentPrecision,
        shadowColor: Colors.accentPrecision,
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 8,
    },
    eventHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: Spacing.xs,
    },
    eventBadges: {
        flexDirection: 'row',
        gap: Spacing.xs,
    },
    statusBadge: {
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
    },
    statusBadgeUpcoming: {
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
    },
    statusBadgePast: {
        backgroundColor: Colors.border,
    },
    statusBadgeText: {
        fontSize: 10,
        fontWeight: '700',
        textTransform: 'uppercase',
        letterSpacing: 0.5,
    },
    statusBadgeTextUpcoming: {
        color: '#16A34A',
    },
    statusBadgeTextPast: {
        color: Colors.textMuted,
    },
    prepBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        borderWidth: 1,
        borderColor: 'rgba(245, 158, 11, 0.2)',
    },
    prepBadgeText: {
        fontSize: 10,
        fontWeight: '700',
        color: '#D97706',
        textTransform: 'uppercase',
    },
    eventTitle: {
        fontWeight: '700',
        marginBottom: Spacing.sm,
    },
    eventMeta: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: Spacing.md,
    },
    eventMetaItem: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
    },
    briefingCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        marginTop: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
        overflow: 'hidden',
    },
    prepHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
    },
    prepHeaderComplete: {
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
    },
    prepHeaderNeeded: {
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
    },
    prepHeaderContent: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
    },
    prepHeaderText: {
        fontSize: 13,
        fontWeight: '600',
    },
    prepHeaderTextComplete: {
        color: '#16A34A',
    },
    prepHeaderTextNeeded: {
        color: '#D97706',
    },
    warningCountBadge: {
        backgroundColor: 'rgba(245, 158, 11, 0.2)',
        paddingHorizontal: 8,
        paddingVertical: 2,
        borderRadius: Radius.full,
    },
    warningCountText: {
        fontSize: 11,
        fontWeight: '600',
        color: '#92400E',
    },
    briefingSection: {
        padding: Spacing.md,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    briefingSectionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        marginBottom: Spacing.sm,
    },
    briefingSectionTitle: {
        fontSize: 11,
        fontWeight: '700',
        color: Colors.textMuted,
        letterSpacing: 0.5,
    },
    agendaText: {
        color: Colors.textPrimary,
        lineHeight: 22,
    },
    warningItem: {
        flexDirection: 'row',
        gap: Spacing.sm,
        padding: Spacing.sm,
        backgroundColor: 'rgba(239, 68, 68, 0.05)',
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.1)',
        marginBottom: Spacing.xs,
    },
    warningIcon: {
        padding: 4,
        borderRadius: Radius.full,
    },
    warningIconHigh: {
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
    },
    warningIconMedium: {
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
    },
    warningContent: {
        flex: 1,
    },
    warningMessage: {
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    warningSuggestion: {
        color: Colors.textMuted,
        marginTop: 2,
    },
    attendeesList: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: Spacing.sm,
    },
    attendeeChip: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        paddingVertical: 4,
        paddingLeft: 4,
        paddingRight: Spacing.sm,
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    attendeeAvatar: {
        width: 24,
        height: 24,
        borderRadius: 12,
        backgroundColor: 'rgba(30, 58, 138, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    attendeeInitial: {
        fontSize: 10,
        fontWeight: '700',
        color: Colors.accentPrecision,
    },
    attendeeName: {
        fontSize: 12,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
});
