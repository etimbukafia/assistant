import React, { useMemo, useState } from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { format, parseISO } from 'date-fns';
import { useChat } from '@/src/context/ChatContext';

// Mock event data (since demo_state.json may not have calendar events)
const MOCK_EVENT = {
    id: 1,
    title: 'Q4 Planning Review',
    start_time: '2026-01-17T14:00:00Z',
    end_time: '2026-01-17T15:30:00Z',
    location: 'Conference Room A / Zoom',
    participants: [
        { name: 'Sarah Johnson', email: 'sarah@company.com', organizer: true },
        { name: 'Mike Chen', email: 'mike@company.com' },
        { name: 'Emily Davis', email: 'emily@company.com' },
    ],
    briefing: {
        agenda: [
            'Review Q3 performance metrics',
            'Discuss Q4 OKRs and key initiatives',
            'Budget allocation for new projects',
            'Team capacity planning',
        ],
        key_context: 'Last quarter we exceeded revenue targets by 12%. Sarah mentioned concerns about engineering bandwidth in the last 1:1.',
        suggested_prep: 'Review the Q3 dashboard before the meeting. Prepare 2-3 talking points on resource optimization.',
    },
    related_emails: [
        { id: 101, subject: 'Q4 Planning - Pre-Read Materials', sender: 'Sarah Johnson', date: '2026-01-15' },
        { id: 102, subject: 'Re: Budget Discussion', sender: 'Mike Chen', date: '2026-01-16' },
    ],
};

export default function EventDetailScreen() {
    const { id } = useLocalSearchParams();
    const router = useRouter();
    const { openChat } = useChat();

    // In real app, fetch event by ID
    const event = MOCK_EVENT;

    const [isGeneratingFollowUps, setIsGeneratingFollowUps] = useState(false);

    const handleGenerateFollowUps = () => {
        setIsGeneratingFollowUps(true);
        // Mock delay
        setTimeout(() => {
            setIsGeneratingFollowUps(false);
            Alert.alert(
                'Follow-ups Generated',
                'Donna has created 3 follow-up tasks based on this meeting:\n\n• Send meeting notes to team\n• Schedule 1:1 with Sarah\n• Draft Q4 budget proposal',
                [{ text: 'View Tasks', onPress: () => router.push('/(tabs)/focus' as any) }]
            );
        }, 1500);
    };

    const startTime = parseISO(event.start_time);
    const endTime = parseISO(event.end_time);

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

                {/* Participants */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>PARTICIPANTS</DonnaText>
                    <View style={styles.participantsList}>
                        {event.participants.map((p, idx) => (
                            <View key={idx} style={styles.participantRow}>
                                <View style={styles.participantAvatar}>
                                    <DonnaText style={styles.avatarText}>{p.name[0]}</DonnaText>
                                </View>
                                <View style={styles.participantInfo}>
                                    <DonnaText style={styles.participantName}>{p.name}</DonnaText>
                                    <DonnaText style={styles.participantEmail}>{p.email}</DonnaText>
                                </View>
                                {p.organizer && (
                                    <View style={styles.organizerBadge}>
                                        <DonnaText style={styles.organizerText}>Organizer</DonnaText>
                                    </View>
                                )}
                            </View>
                        ))}
                    </View>
                </View>

                {/* AI Briefing */}
                {event.briefing && (
                    <View style={styles.briefingSection}>
                        <View style={styles.briefingHeader}>
                            <Ionicons name="sparkles" size={18} color={Colors.accentSecondary} />
                            <DonnaText style={styles.briefingTitle}>AI BRIEFING</DonnaText>
                        </View>

                        {/* Agenda */}
                        <View style={styles.briefingCard}>
                            <DonnaText style={styles.briefingCardTitle}>📋 Agenda</DonnaText>
                            {event.briefing.agenda.map((item, idx) => (
                                <View key={idx} style={styles.agendaItem}>
                                    <DonnaText style={styles.agendaBullet}>•</DonnaText>
                                    <DonnaText style={styles.agendaText}>{item}</DonnaText>
                                </View>
                            ))}
                        </View>

                        {/* Key Context */}
                        <View style={styles.briefingCard}>
                            <DonnaText style={styles.briefingCardTitle}>💡 Key Context</DonnaText>
                            <DonnaText style={styles.contextText}>{event.briefing.key_context}</DonnaText>
                        </View>

                        {/* Suggested Prep */}
                        <View style={[styles.briefingCard, styles.prepCard]}>
                            <DonnaText style={styles.briefingCardTitle}>✅ Suggested Prep</DonnaText>
                            <DonnaText style={styles.prepText}>{event.briefing.suggested_prep}</DonnaText>
                        </View>
                    </View>
                )}

                {/* Related Emails */}
                {event.related_emails && event.related_emails.length > 0 && (
                    <View style={styles.section}>
                        <DonnaText style={styles.sectionLabel}>RELATED EMAILS</DonnaText>
                        {event.related_emails.map((email, idx) => (
                            <TouchableOpacity
                                key={idx}
                                style={styles.emailCard}
                                onPress={() => router.push(`/inbox/${email.id}` as any)}
                            >
                                <Ionicons name="mail-outline" size={18} color={Colors.textMuted} />
                                <View style={styles.emailInfo}>
                                    <DonnaText style={styles.emailSubject} numberOfLines={1}>{email.subject}</DonnaText>
                                    <DonnaText style={styles.emailMeta}>{email.sender} · {email.date}</DonnaText>
                                </View>
                                <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
                            </TouchableOpacity>
                        ))}
                    </View>
                )}
            </ScrollView>

            {/* Bottom Action */}
            <View style={styles.actionBar}>
                <TouchableOpacity
                    style={styles.followUpButton}
                    onPress={handleGenerateFollowUps}
                    disabled={isGeneratingFollowUps}
                >
                    <Ionicons
                        name={isGeneratingFollowUps ? "hourglass-outline" : "sparkles"}
                        size={20}
                        color="#FFF"
                    />
                    <DonnaText style={styles.followUpText}>
                        {isGeneratingFollowUps ? 'Generating...' : 'Generate Follow-ups'}
                    </DonnaText>
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
    participantInfo: {
        flex: 1,
    },
    participantName: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    participantEmail: {
        fontSize: 13,
        color: Colors.textMuted,
    },
    organizerBadge: {
        backgroundColor: Colors.accentSecondary + '15',
        paddingHorizontal: 8,
        paddingVertical: 3,
        borderRadius: Radius.full,
    },
    organizerText: {
        fontSize: 11,
        color: Colors.accentSecondary,
        fontWeight: '600',
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
    briefingCardTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    agendaItem: {
        flexDirection: 'row',
        gap: Spacing.sm,
        marginBottom: 4,
    },
    agendaBullet: {
        color: Colors.textMuted,
    },
    agendaText: {
        flex: 1,
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 20,
    },
    contextText: {
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 20,
        fontStyle: 'italic',
    },
    prepCard: {
        backgroundColor: 'rgba(138, 154, 91, 0.08)',
        borderColor: Colors.success,
    },
    prepText: {
        fontSize: 14,
        color: Colors.textPrimary,
        lineHeight: 20,
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
    followUpText: {
        color: '#FFF',
        fontSize: 16,
        fontWeight: '600',
    },
});
