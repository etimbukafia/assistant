import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Switch, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import DateTimePicker from '@react-native-community/datetimepicker';

interface DigestConfig {
    enabled: boolean;
    time: Date;
}

export default function DigestsScreen() {
    const router = useRouter();

    const [morningBriefing, setMorningBriefing] = useState<DigestConfig>({
        enabled: true,
        time: new Date(2026, 0, 1, 7, 30),
    });
    const [endOfDay, setEndOfDay] = useState<DigestConfig>({
        enabled: true,
        time: new Date(2026, 0, 1, 17, 0),
    });
    const [weeklyReview, setWeeklyReview] = useState<DigestConfig>({
        enabled: false,
        time: new Date(2026, 0, 1, 9, 0),
    });

    const [activePicker, setActivePicker] = useState<'morning' | 'eod' | 'weekly' | null>(null);

    const renderDigestCard = (
        title: string,
        description: string,
        icon: string,
        iconColor: string,
        config: DigestConfig,
        setConfig: (c: DigestConfig) => void,
        pickerKey: 'morning' | 'eod' | 'weekly'
    ) => (
        <View style={styles.digestCard}>
            <View style={styles.digestHeader}>
                <View style={[styles.iconContainer, { backgroundColor: iconColor + '15' }]}>
                    <Ionicons name={icon as any} size={22} color={iconColor} />
                </View>
                <View style={styles.digestInfo}>
                    <DonnaText style={styles.digestTitle}>{title}</DonnaText>
                    <DonnaText style={styles.digestDescription}>{description}</DonnaText>
                </View>
                <Switch
                    value={config.enabled}
                    onValueChange={(enabled) => setConfig({ ...config, enabled })}
                    trackColor={{ true: Colors.success }}
                    thumbColor="#FFF"
                />
            </View>

            {config.enabled && (
                <TouchableOpacity
                    style={styles.timeButton}
                    onPress={() => setActivePicker(pickerKey)}
                >
                    <Ionicons name="time-outline" size={18} color={Colors.textSecondary} />
                    <DonnaText style={styles.timeText}>
                        {config.time.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}
                    </DonnaText>
                    <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
                </TouchableOpacity>
            )}
        </View>
    );

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Digests</DonnaText>
                <View style={styles.placeholder} />
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Explanation */}
                <View style={styles.explanationCard}>
                    <Ionicons name="mail-unread-outline" size={24} color={Colors.accentSecondary} />
                    <DonnaText style={styles.explanationText}>
                        Digests are email summaries Donna sends to keep you informed without needing to open the app.
                    </DonnaText>
                </View>

                {/* Morning Briefing */}
                {renderDigestCard(
                    'Morning Briefing',
                    'Start your day with a summary of what\'s ahead',
                    'sunny-outline',
                    Colors.accentSecondary,
                    morningBriefing,
                    setMorningBriefing,
                    'morning'
                )}

                {/* End of Day Summary */}
                {renderDigestCard(
                    'End of Day Summary',
                    'Recap of today\'s accomplishments and tomorrow\'s priorities',
                    'moon-outline',
                    Colors.accentPrecision,
                    endOfDay,
                    setEndOfDay,
                    'eod'
                )}

                {/* Weekly Review */}
                {renderDigestCard(
                    'Weekly Review',
                    'Sunday summary of the week ahead and pending items',
                    'calendar-outline',
                    Colors.success,
                    weeklyReview,
                    setWeeklyReview,
                    'weekly'
                )}

                {/* Preview Card */}
                <View style={styles.previewSection}>
                    <DonnaText style={styles.sectionLabel}>PREVIEW</DonnaText>
                    <View style={styles.previewCard}>
                        <DonnaText style={styles.previewTitle}>📬 Your Morning Briefing</DonnaText>
                        <DonnaText style={styles.previewBody}>
                            Good morning! Here's what's on deck:{'\n\n'}
                            • 3 meetings today (first at 10 AM){'\n'}
                            • 2 emails need your reply{'\n'}
                            • 1 task due today
                        </DonnaText>
                    </View>
                </View>
            </ScrollView>

            {/* Time Pickers */}
            {activePicker && (
                <DateTimePicker
                    value={
                        activePicker === 'morning' ? morningBriefing.time :
                            activePicker === 'eod' ? endOfDay.time : weeklyReview.time
                    }
                    mode="time"
                    display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                    onChange={(e, date) => {
                        if (Platform.OS !== 'ios') setActivePicker(null);
                        if (date) {
                            if (activePicker === 'morning') setMorningBriefing(prev => ({ ...prev, time: date }));
                            else if (activePicker === 'eod') setEndOfDay(prev => ({ ...prev, time: date }));
                            else setWeeklyReview(prev => ({ ...prev, time: date }));
                        }
                    }}
                />
            )}
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
        alignItems: 'center',
        justifyContent: 'space-between',
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
    placeholder: {
        width: 44,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 60,
    },
    explanationCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: 'rgba(217, 119, 69, 0.06)',
        borderRadius: Radius.lg,
        marginBottom: Spacing.xl,
    },
    explanationText: {
        flex: 1,
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 20,
    },
    digestCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        marginBottom: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    digestHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
    },
    iconContainer: {
        width: 44,
        height: 44,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
    },
    digestInfo: {
        flex: 1,
    },
    digestTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    digestDescription: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 2,
    },
    timeButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        marginTop: Spacing.md,
        paddingTop: Spacing.md,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    timeText: {
        flex: 1,
        fontSize: 15,
        color: Colors.textPrimary,
    },
    previewSection: {
        marginTop: Spacing.xl,
    },
    sectionLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
        marginLeft: Spacing.xs,
    },
    previewCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    previewTitle: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    previewBody: {
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 20,
    },
});
