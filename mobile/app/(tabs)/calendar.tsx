import React, { useState, useCallback, useMemo } from 'react';
import { StyleSheet, View, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { FlashList } from '@shopify/flash-list';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { format, parseISO, isToday } from 'date-fns';
import { CalendarEvent, CalendarBriefing } from '../../src/services/calendar';
import { useCalendarEvents, useCalendarMutations } from '../../src/hooks/useCalendar';
import { useAuth } from '../../src/context/AuthContext';
import { ConnectIntegrationCTA } from '../../src/components/ui/ConnectIntegrationCTA';
import { SubscriptionExpiredCTA } from '../../src/components/ui/SubscriptionExpiredCTA';

// Extracted EventCard component for better FlashList performance
const EventCard = React.memo(({
    event,
    isSelected,
    onSelect,
    formatTime,
    formatDateBadge
}: {
    event: CalendarEvent;
    isSelected: boolean;
    onSelect: () => void;
    formatTime: (iso: string) => string;
    formatDateBadge: (iso: string) => string;
}) => (
    <View style={styles.eventSection}>
        <TouchableOpacity
            style={[styles.eventCard, isSelected && styles.eventCardSelected]}
            onPress={onSelect}
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
                    name={isSelected ? "chevron-up" : "chevron-forward"}
                    size={18}
                    color={isSelected ? Colors.accentPrecision : Colors.textMuted}
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
        {isSelected && event.briefing && (
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
));

export default function CalendarScreen() {
    const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
    const { isActive, subscriptionTier, calendarConnected } = useAuth();

    // Fetch events from backend
    const { data: eventsResponse, isLoading, isRefetching, refetch } = useCalendarEvents(
        undefined, // no status filter
        { enabled: calendarConnected }
    );

    // Calendar mutations
    const { sync, isSyncing, generateFollowUps, isGeneratingFollowUps } = useCalendarMutations();

    // Use API response
    const events = useMemo(() => {
        return eventsResponse?.events || [];
    }, [eventsResponse]);

    const onRefresh = useCallback(() => {
        refetch();
    }, [refetch]);

    const handleSync = () => {
        sync(7);
    };

    const formatTime = useCallback((isoString: string) => {
        return format(parseISO(isoString), 'h:mm a');
    }, []);

    const formatDateBadge = useCallback((isoString: string) => {
        const date = parseISO(isoString);
        if (isToday(date)) return 'Today';
        return format(date, 'MMM d');
    }, []);

    const renderEvent = useCallback(({ item }: { item: CalendarEvent }) => (
        <EventCard
            event={item}
            isSelected={selectedEventId === item.id}
            onSelect={() => setSelectedEventId(selectedEventId === item.id ? null : item.id)}
            formatTime={formatTime}
            formatDateBadge={formatDateBadge}
        />
    ), [selectedEventId, formatTime, formatDateBadge]);

    const ListHeader = useCallback(() => (
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
    ), [isSyncing]);

    const ListEmpty = useCallback(() => {
        // State 1: Subscription expired - show resubscribe CTA
        if (!isActive) {
            return (
                <View style={styles.emptyContainer}>
                    <Ionicons name="calendar-outline" size={48} color={Colors.textMuted} />
                    <DonnaText variant="h2" style={styles.emptyTitle}>Calendar Sync Paused</DonnaText>
                    <DonnaText variant="caption" style={styles.emptyText}>Your subscription has expired. Resubscribe to sync new calendar events.</DonnaText>
                    <View style={{ marginTop: Spacing.md, width: '100%' }}>
                        <SubscriptionExpiredCTA tier={subscriptionTier as 'trial' | 'pro'} />
                    </View>
                </View>
            );
        }

        // State 3: Active but calendar not connected
        if (!calendarConnected) {
            return (
                <View style={styles.emptyContainer}>
                    <Ionicons name="calendar-outline" size={48} color={Colors.textMuted} />
                    <DonnaText variant="h2" style={styles.emptyTitle}>Connect Your Calendar</DonnaText>
                    <DonnaText variant="caption" style={styles.emptyText}>Link Google Calendar to see your meetings and get AI-powered briefings.</DonnaText>
                    <View style={{ marginTop: Spacing.md, width: '100%' }}>
                        <ConnectIntegrationCTA integration="calendar" />
                    </View>
                </View>
            );
        }

        // State 4: Calendar connected but no events
        return (
            <View style={styles.emptyContainer}>
                <Ionicons name="calendar-outline" size={48} color={Colors.textMuted} />
                <DonnaText variant="h2" style={styles.emptyTitle}>No meetings found</DonnaText>
                <DonnaText variant="caption" style={styles.emptyText}>Your calendar looks clear for the next few days.</DonnaText>
                <TouchableOpacity style={styles.syncButtonLarge} onPress={handleSync} disabled={isSyncing}>
                    <DonnaText style={styles.syncButtonText}>
                        {isSyncing ? 'Syncing...' : 'Sync Calendar'}
                    </DonnaText>
                </TouchableOpacity>
            </View>
        );
    }, [isActive, subscriptionTier, calendarConnected, isSyncing]);

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentPrimary} />
                    <DonnaText variant="caption" style={styles.loadingText}>Loading your schedule...</DonnaText>
                </View>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <FlashList
                data={events}
                renderItem={renderEvent}
                keyExtractor={(item: CalendarEvent) => item.id.toString()}
                ListHeaderComponent={ListHeader}
                ListEmptyComponent={ListEmpty}
                contentContainerStyle={styles.listContent}
                refreshControl={
                    <RefreshControl refreshing={isRefetching} onRefresh={onRefresh} tintColor={Colors.accentPrimary} />
                }
            />
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
