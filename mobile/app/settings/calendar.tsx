import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Switch, Platform, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useCalendarSettings, useUserCalendars, useCalendarMutations } from '@/src/hooks/useCalendar';
import { CalendarSettingsUpdate } from '@/src/services/calendar';

interface TimePickerButtonProps {
    label: string;
    time: string;
    onPress: () => void;
}

const TimePickerButton: React.FC<TimePickerButtonProps> = ({ label, time, onPress }) => (
    <TouchableOpacity style={styles.timePickerButton} onPress={onPress}>
        <DonnaText style={styles.timeLabel}>{label}</DonnaText>
        <DonnaText style={styles.timeValue}>{time}</DonnaText>
    </TouchableOpacity>
);

export default function CalendarSettingsScreen() {
    const router = useRouter();

    // Local state for pickers
    const [showStartPicker, setShowStartPicker] = useState(false);
    const [showEndPicker, setShowEndPicker] = useState(false);
    const [tempStartTime, setTempStartTime] = useState<Date | null>(null);
    const [tempEndTime, setTempEndTime] = useState<Date | null>(null);

    const DURATIONS = [15, 25, 30, 45, 60];
    const BUFFERS = [0, 5, 10, 15];

    // Fetch settings and calendars using hooks
    const { data: settings, isLoading, error } = useCalendarSettings();
    const { data: calendarsData, isLoading: calendarsLoading } = useUserCalendars();
    const { updateSettings, isUpdatingSettings } = useCalendarMutations();

    const calendars = calendarsData?.calendars || [];

    // Toggle calendar selection
    const handleCalendarToggle = (calendarId: string) => {
        const currentIds = settings?.calendar_ids || [];
        const newIds = currentIds.includes(calendarId)
            ? currentIds.filter(id => id !== calendarId)
            : [...currentIds, calendarId];
        handleSettingChange('calendar_ids', newIds);
    };

    // Parse time string to Date for picker
    const parseTimeToDate = (timeStr: string): Date => {
        const [hours, minutes] = timeStr.split(':').map(Number);
        const date = new Date();
        date.setHours(hours, minutes, 0, 0);
        return date;
    };

    // Format Date to time string (HH:MM)
    const formatTimeToString = (date: Date): string => {
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    };

    // Format for display (12h format)
    const formatTimeForDisplay = (timeStr: string): string => {
        const date = parseTimeToDate(timeStr);
        return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    };

    const handleSettingChange = (key: keyof CalendarSettingsUpdate, value: any) => {
        updateSettings({ [key]: value });
    };

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <DonnaText style={styles.headerTitle}>Calendar Settings</DonnaText>
                    <View style={styles.placeholder} />
                </View>
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentPrimary} />
                </View>
            </SafeAreaView>
        );
    }

    if (error || !settings) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <DonnaText style={styles.headerTitle}>Calendar Settings</DonnaText>
                    <View style={styles.placeholder} />
                </View>
                <View style={styles.errorContainer}>
                    <Ionicons name="alert-circle-outline" size={48} color={Colors.error} />
                    <DonnaText style={styles.errorText}>Failed to load settings</DonnaText>
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
                <DonnaText style={styles.headerTitle}>Calendar Settings</DonnaText>
                <View style={styles.placeholder} />
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Working Hours Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>WORKING HOURS</DonnaText>
                    <View style={styles.sectionCard}>
                        <View style={styles.timeRow}>
                            <TimePickerButton
                                label="Start"
                                time={formatTimeForDisplay(settings.working_hours_start)}
                                onPress={() => {
                                    setTempStartTime(parseTimeToDate(settings.working_hours_start));
                                    setShowStartPicker(true);
                                }}
                            />
                            <DonnaText style={styles.timeSeparator}>to</DonnaText>
                            <TimePickerButton
                                label="End"
                                time={formatTimeForDisplay(settings.working_hours_end)}
                                onPress={() => {
                                    setTempEndTime(parseTimeToDate(settings.working_hours_end));
                                    setShowEndPicker(true);
                                }}
                            />
                        </View>
                    </View>
                </View>

                {/* Meeting Defaults Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>MEETING DEFAULTS</DonnaText>
                    <View style={styles.sectionCard}>
                        <View style={styles.settingBlock}>
                            <DonnaText style={styles.settingTitle}>Default Duration</DonnaText>
                            <View style={styles.chipRow}>
                                {DURATIONS.map(d => (
                                    <TouchableOpacity
                                        key={d}
                                        style={[styles.chip, settings.default_meeting_duration === d && styles.chipActive]}
                                        onPress={() => handleSettingChange('default_meeting_duration', d)}
                                    >
                                        <DonnaText style={[
                                            styles.chipText,
                                            settings.default_meeting_duration === d && styles.chipTextActive
                                        ]}>
                                            {d} min
                                        </DonnaText>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>

                        <View style={[styles.settingBlock, styles.settingBlockBorder]}>
                            <DonnaText style={styles.settingTitle}>Buffer Between Meetings</DonnaText>
                            <DonnaText style={styles.settingSubtitle}>
                                Time to prep before and decompress after
                            </DonnaText>
                            <View style={styles.chipRow}>
                                {BUFFERS.map(b => (
                                    <TouchableOpacity
                                        key={b}
                                        style={[styles.chip, settings.buffer_minutes === b && styles.chipActive]}
                                        onPress={() => handleSettingChange('buffer_minutes', b)}
                                    >
                                        <DonnaText style={[
                                            styles.chipText,
                                            settings.buffer_minutes === b && styles.chipTextActive
                                        ]}>
                                            {b === 0 ? 'None' : `${b} min`}
                                        </DonnaText>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>

                        <View style={[styles.settingBlock, styles.settingBlockBorder]}>
                            <DonnaText style={styles.settingTitle}>Preferred Meeting Times</DonnaText>
                            <View style={styles.chipRow}>
                                {['morning', 'afternoon', 'any'].map(time => (
                                    <TouchableOpacity
                                        key={time}
                                        style={[styles.chip, settings.preferred_meeting_times === time && styles.chipActive]}
                                        onPress={() => handleSettingChange('preferred_meeting_times', time)}
                                    >
                                        <DonnaText style={[
                                            styles.chipText,
                                            settings.preferred_meeting_times === time && styles.chipTextActive
                                        ]}>
                                            {time.charAt(0).toUpperCase() + time.slice(1)}
                                        </DonnaText>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>
                    </View>
                </View>

                {/* Calendar Selection Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>CALENDARS TO SYNC</DonnaText>
                    <View style={styles.sectionCard}>
                        {calendarsLoading ? (
                            <View style={styles.calendarLoadingContainer}>
                                <ActivityIndicator size="small" color={Colors.accentPrimary} />
                                <DonnaText style={styles.calendarLoadingText}>Loading calendars...</DonnaText>
                            </View>
                        ) : calendars.length === 0 ? (
                            <View style={styles.calendarEmptyContainer}>
                                <Ionicons name="calendar-outline" size={24} color={Colors.textMuted} />
                                <DonnaText style={styles.calendarEmptyText}>No calendars found</DonnaText>
                            </View>
                        ) : (
                            calendars.map((calendar, index) => (
                                <TouchableOpacity
                                    key={calendar.id}
                                    style={[
                                        styles.calendarRow,
                                        index > 0 && styles.calendarRowBorder
                                    ]}
                                    onPress={() => handleCalendarToggle(calendar.id)}
                                >
                                    <View style={styles.calendarInfo}>
                                        <View style={styles.calendarNameRow}>
                                            <DonnaText style={styles.calendarName}>{calendar.summary}</DonnaText>
                                            {calendar.primary && (
                                                <View style={styles.primaryBadge}>
                                                    <DonnaText style={styles.primaryBadgeText}>Primary</DonnaText>
                                                </View>
                                            )}
                                        </View>
                                        <DonnaText style={styles.calendarRole}>
                                            {calendar.access_role === 'owner' ? 'Owner' : 'Shared'}
                                        </DonnaText>
                                    </View>
                                    <View style={[
                                        styles.calendarCheckbox,
                                        (settings?.calendar_ids || []).includes(calendar.id) && styles.calendarCheckboxActive
                                    ]}>
                                        {(settings?.calendar_ids || []).includes(calendar.id) && (
                                            <Ionicons name="checkmark" size={16} color="#FFF" />
                                        )}
                                    </View>
                                </TouchableOpacity>
                            ))
                        )}
                    </View>
                    <DonnaText style={styles.calendarHelpText}>
                        Select which calendars Teeks should consider for availability and scheduling
                    </DonnaText>
                </View>

                {/* Timezone */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>TIMEZONE</DonnaText>
                    <View style={styles.timezoneRow}>
                        <Ionicons name="globe-outline" size={20} color={Colors.accentPrecision} />
                        <View style={styles.timezoneInfo}>
                            <DonnaText style={styles.timezoneValue}>{settings.default_timezone}</DonnaText>
                            <DonnaText style={styles.timezoneNote}>From your account settings</DonnaText>
                        </View>
                    </View>
                </View>

                {/* Saving indicator */}
                {isUpdatingSettings && (
                    <View style={styles.savingIndicator}>
                        <ActivityIndicator size="small" color={Colors.accentPrimary} />
                        <DonnaText style={styles.savingText}>Saving...</DonnaText>
                    </View>
                )}
            </ScrollView>

            {/* Time Pickers */}
            {showStartPicker && tempStartTime && (
                <DateTimePicker
                    value={tempStartTime}
                    mode="time"
                    display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                    onChange={(e, date) => {
                        setShowStartPicker(Platform.OS === 'ios');
                        if (date) {
                            setTempStartTime(date);
                            handleSettingChange('working_hours_start', formatTimeToString(date));
                        }
                    }}
                />
            )}
            {showEndPicker && tempEndTime && (
                <DateTimePicker
                    value={tempEndTime}
                    mode="time"
                    display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                    onChange={(e, date) => {
                        setShowEndPicker(Platform.OS === 'ios');
                        if (date) {
                            setTempEndTime(date);
                            handleSettingChange('working_hours_end', formatTimeToString(date));
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
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 60,
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
        marginLeft: Spacing.xs,
    },
    sectionCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: Colors.border,
    },
    settingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: Spacing.md,
    },
    settingInfo: {
        flex: 1,
        marginRight: Spacing.md,
    },
    settingTitle: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    settingSubtitle: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 2,
    },
    settingBlock: {
        padding: Spacing.md,
    },
    settingBlockBorder: {
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    timeRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
    },
    timePickerButton: {
        flex: 1,
        alignItems: 'center',
        padding: Spacing.md,
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    timeLabel: {
        fontSize: 11,
        color: Colors.textMuted,
        marginBottom: 4,
    },
    timeValue: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    timeSeparator: {
        fontSize: 14,
        color: Colors.textMuted,
    },
    chipRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: Spacing.sm,
        marginTop: Spacing.md,
    },
    chip: {
        paddingVertical: 8,
        paddingHorizontal: 14,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.bgBase,
    },
    chipActive: {
        backgroundColor: Colors.accentSecondary,
        borderColor: Colors.accentSecondary,
    },
    chipText: {
        fontSize: 14,
        color: Colors.textSecondary,
    },
    chipTextActive: {
        color: '#FFF',
        fontWeight: '600',
    },
    timezoneRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    timezoneInfo: {
        flex: 1,
    },
    timezoneValue: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    timezoneNote: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 2,
    },
    savingIndicator: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        paddingVertical: Spacing.sm,
    },
    savingText: {
        fontSize: 13,
        color: Colors.textMuted,
    },
    // Calendar selector styles
    calendarLoadingContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        padding: Spacing.lg,
    },
    calendarLoadingText: {
        fontSize: 14,
        color: Colors.textMuted,
    },
    calendarEmptyContainer: {
        alignItems: 'center',
        padding: Spacing.lg,
        gap: Spacing.sm,
    },
    calendarEmptyText: {
        fontSize: 14,
        color: Colors.textMuted,
    },
    calendarRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: Spacing.md,
    },
    calendarRowBorder: {
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    calendarInfo: {
        flex: 1,
    },
    calendarNameRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
    },
    calendarName: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    primaryBadge: {
        backgroundColor: 'rgba(30, 58, 138, 0.1)',
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
    },
    primaryBadgeText: {
        fontSize: 10,
        fontWeight: '600',
        color: Colors.accentPrecision,
        textTransform: 'uppercase',
    },
    calendarRole: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 2,
    },
    calendarCheckbox: {
        width: 24,
        height: 24,
        borderRadius: 6,
        borderWidth: 2,
        borderColor: Colors.border,
        alignItems: 'center',
        justifyContent: 'center',
    },
    calendarCheckboxActive: {
        backgroundColor: Colors.accentSecondary,
        borderColor: Colors.accentSecondary,
    },
    calendarHelpText: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: Spacing.sm,
        marginHorizontal: Spacing.xs,
    },
});
