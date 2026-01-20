import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Switch, Platform, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    fetchDigestPreferences,
    updateDigestPreferences,
    DigestPreferences,
} from '@/src/services/digests';

// ================================
// Time Helpers
// ================================

const timeStringToDate = (timeStr: string, fallbackHour: number, fallbackMinute: number): Date => {
    if (!timeStr) return new Date(2026, 0, 1, fallbackHour, fallbackMinute);
    const [hours, minutes] = timeStr.split(':').map(Number);
    return new Date(2026, 0, 1, hours || fallbackHour, minutes || fallbackMinute);
};

const dateToTimeString = (date: Date): string => {
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
};

// ================================
// Component
// ================================

export default function DigestsScreen() {
    const router = useRouter();
    const queryClient = useQueryClient();

    const [activePicker, setActivePicker] = useState<'morning' | 'eod' | 'weekly' | null>(null);

    // Fetch preferences with TanStack Query
    const { data: preferences, isLoading, error } = useQuery({
        queryKey: ['digest-preferences'],
        queryFn: fetchDigestPreferences,
    });

    // Update mutation
    const updateMutation = useMutation({
        mutationFn: updateDigestPreferences,
        onSuccess: (data) => {
            queryClient.setQueryData(['digest-preferences'], data);
        },
        onError: () => {
            Alert.alert('Error', 'Failed to save preferences. Please try again.');
        },
    });

    // Derived state from server data
    const morningBriefing = preferences?.morning_briefing ?? { enabled: true, time: '07:30' };
    const endOfDay = preferences?.end_of_day ?? { enabled: true, time: '17:00' };
    const weeklyReview = preferences?.weekly_review ?? { enabled: false, time: '09:00', day: 'monday' };

    // Handle preference updates
    const handleUpdate = (updates: Partial<DigestPreferences>) => {
        const newPrefs: DigestPreferences = {
            enabled: (updates.morning_briefing?.enabled ?? morningBriefing.enabled) ||
                (updates.end_of_day?.enabled ?? endOfDay.enabled) ||
                (updates.weekly_review?.enabled ?? weeklyReview.enabled),
            morning_briefing: updates.morning_briefing ?? morningBriefing,
            end_of_day: updates.end_of_day ?? endOfDay,
            weekly_review: updates.weekly_review ?? weeklyReview,
            delivery_channel: 'email',
        };
        updateMutation.mutate(newPrefs);
    };

    const renderDigestCard = (
        title: string,
        description: string,
        icon: string,
        iconColor: string,
        enabled: boolean,
        time: string,
        onToggle: (enabled: boolean) => void,
        onTimeChange: (date: Date) => void,
        pickerKey: 'morning' | 'eod' | 'weekly'
    ) => {
        const displayTime = timeStringToDate(time, 8, 0);

        return (
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
                        value={enabled}
                        onValueChange={onToggle}
                        trackColor={{ true: Colors.success }}
                        thumbColor="#FFF"
                        disabled={updateMutation.isPending}
                    />
                </View>

                {enabled && (
                    <TouchableOpacity
                        style={styles.timeButton}
                        onPress={() => setActivePicker(pickerKey)}
                        disabled={updateMutation.isPending}
                    >
                        <Ionicons name="time-outline" size={18} color={Colors.textSecondary} />
                        <DonnaText style={styles.timeText}>
                            {displayTime.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}
                        </DonnaText>
                        <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
                    </TouchableOpacity>
                )}
            </View>
        );
    };

    // Loading state
    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <DonnaText style={styles.headerTitle}>Digests</DonnaText>
                    <View style={styles.placeholder} />
                </View>
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                </View>
            </SafeAreaView>
        );
    }

    // Error state
    if (error) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <DonnaText style={styles.headerTitle}>Digests</DonnaText>
                    <View style={styles.placeholder} />
                </View>
                <View style={styles.errorContainer}>
                    <Ionicons name="alert-circle-outline" size={48} color={Colors.error} />
                    <DonnaText style={styles.errorText}>Failed to load preferences</DonnaText>
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
                <DonnaText style={styles.headerTitle}>Digests</DonnaText>
                <View style={styles.placeholder}>
                    {updateMutation.isPending && <ActivityIndicator size="small" color={Colors.textMuted} />}
                </View>
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
                    morningBriefing.enabled,
                    morningBriefing.time,
                    (enabled) => handleUpdate({
                        morning_briefing: { ...morningBriefing, enabled }
                    }),
                    (date) => handleUpdate({
                        morning_briefing: { ...morningBriefing, time: dateToTimeString(date) }
                    }),
                    'morning'
                )}

                {/* End of Day Summary */}
                {renderDigestCard(
                    'End of Day Summary',
                    'Recap of today\'s accomplishments and tomorrow\'s priorities',
                    'moon-outline',
                    Colors.accentPrecision,
                    endOfDay.enabled,
                    endOfDay.time,
                    (enabled) => handleUpdate({
                        end_of_day: { ...endOfDay, enabled }
                    }),
                    (date) => handleUpdate({
                        end_of_day: { ...endOfDay, time: dateToTimeString(date) }
                    }),
                    'eod'
                )}

                {/* Weekly Review */}
                {renderDigestCard(
                    'Weekly Review',
                    'Sunday summary of the week ahead and pending items',
                    'calendar-outline',
                    Colors.success,
                    weeklyReview.enabled,
                    weeklyReview.time,
                    (enabled) => handleUpdate({
                        weekly_review: { ...weeklyReview, enabled }
                    }),
                    (date) => handleUpdate({
                        weekly_review: { ...weeklyReview, time: dateToTimeString(date) }
                    }),
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
                        activePicker === 'morning' ? timeStringToDate(morningBriefing.time, 7, 30) :
                            activePicker === 'eod' ? timeStringToDate(endOfDay.time, 17, 0) :
                                timeStringToDate(weeklyReview.time, 9, 0)
                    }
                    mode="time"
                    display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                    onChange={(e, date) => {
                        if (Platform.OS !== 'ios') setActivePicker(null);
                        if (date) {
                            const timeStr = dateToTimeString(date);
                            if (activePicker === 'morning') {
                                handleUpdate({ morning_briefing: { ...morningBriefing, time: timeStr } });
                            } else if (activePicker === 'eod') {
                                handleUpdate({ end_of_day: { ...endOfDay, time: timeStr } });
                            } else {
                                handleUpdate({ weekly_review: { ...weeklyReview, time: timeStr } });
                            }
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
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    errorContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.xl,
    },
    errorText: {
        marginTop: Spacing.md,
        color: Colors.error,
        textAlign: 'center',
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
        alignItems: 'center',
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
