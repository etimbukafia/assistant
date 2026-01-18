import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Switch, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import DateTimePicker from '@react-native-community/datetimepicker';

interface TimePickerButtonProps {
    label: string;
    time: Date;
    onPress: () => void;
}

const TimePickerButton: React.FC<TimePickerButtonProps> = ({ label, time, onPress }) => (
    <TouchableOpacity style={styles.timePickerButton} onPress={onPress}>
        <DonnaText style={styles.timeLabel}>{label}</DonnaText>
        <DonnaText style={styles.timeValue}>
            {time.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}
        </DonnaText>
    </TouchableOpacity>
);

export default function CalendarSettingsScreen() {
    const router = useRouter();

    // Settings state
    const [workingHoursStart, setWorkingHoursStart] = useState(new Date(2026, 0, 1, 9, 0));
    const [workingHoursEnd, setWorkingHoursEnd] = useState(new Date(2026, 0, 1, 17, 0));
    const [defaultDuration, setDefaultDuration] = useState(30);
    const [bufferMinutes, setBufferMinutes] = useState(5);
    const [respectWorkingHours, setRespectWorkingHours] = useState(true);
    const [autoDeclineConflicts, setAutoDeclineConflicts] = useState(false);

    // Time picker state
    const [showStartPicker, setShowStartPicker] = useState(false);
    const [showEndPicker, setShowEndPicker] = useState(false);

    const DURATIONS = [15, 25, 30, 45, 60];
    const BUFFERS = [0, 5, 10, 15];

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
                        <View style={styles.settingRow}>
                            <View style={styles.settingInfo}>
                                <DonnaText style={styles.settingTitle}>Respect Working Hours</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Only suggest meeting times within these hours
                                </DonnaText>
                            </View>
                            <Switch
                                value={respectWorkingHours}
                                onValueChange={setRespectWorkingHours}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                            />
                        </View>

                        {respectWorkingHours && (
                            <View style={styles.timeRow}>
                                <TimePickerButton
                                    label="Start"
                                    time={workingHoursStart}
                                    onPress={() => setShowStartPicker(true)}
                                />
                                <DonnaText style={styles.timeSeparator}>to</DonnaText>
                                <TimePickerButton
                                    label="End"
                                    time={workingHoursEnd}
                                    onPress={() => setShowEndPicker(true)}
                                />
                            </View>
                        )}
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
                                        style={[styles.chip, defaultDuration === d && styles.chipActive]}
                                        onPress={() => setDefaultDuration(d)}
                                    >
                                        <DonnaText style={[
                                            styles.chipText,
                                            defaultDuration === d && styles.chipTextActive
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
                                        style={[styles.chip, bufferMinutes === b && styles.chipActive]}
                                        onPress={() => setBufferMinutes(b)}
                                    >
                                        <DonnaText style={[
                                            styles.chipText,
                                            bufferMinutes === b && styles.chipTextActive
                                        ]}>
                                            {b === 0 ? 'None' : `${b} min`}
                                        </DonnaText>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>
                    </View>
                </View>

                {/* Automation Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>AUTOMATION</DonnaText>
                    <View style={styles.sectionCard}>
                        <View style={styles.settingRow}>
                            <View style={styles.settingInfo}>
                                <DonnaText style={styles.settingTitle}>Auto-Decline Conflicts</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Automatically decline invites that conflict with existing events
                                </DonnaText>
                            </View>
                            <Switch
                                value={autoDeclineConflicts}
                                onValueChange={setAutoDeclineConflicts}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                            />
                        </View>
                    </View>
                </View>

                {/* Timezone */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>TIMEZONE</DonnaText>
                    <TouchableOpacity style={styles.timezoneRow}>
                        <Ionicons name="globe-outline" size={20} color={Colors.accentPrecision} />
                        <View style={styles.timezoneInfo}>
                            <DonnaText style={styles.timezoneValue}>Europe/Paris (GMT+1)</DonnaText>
                            <DonnaText style={styles.timezoneNote}>Auto-detected from device</DonnaText>
                        </View>
                        <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
                    </TouchableOpacity>
                </View>
            </ScrollView>

            {/* Time Pickers */}
            {showStartPicker && (
                <DateTimePicker
                    value={workingHoursStart}
                    mode="time"
                    display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                    onChange={(e, date) => {
                        setShowStartPicker(Platform.OS === 'ios');
                        if (date) setWorkingHoursStart(date);
                    }}
                />
            )}
            {showEndPicker && (
                <DateTimePicker
                    value={workingHoursEnd}
                    mode="time"
                    display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                    onChange={(e, date) => {
                        setShowEndPicker(Platform.OS === 'ios');
                        if (date) setWorkingHoursEnd(date);
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
        paddingHorizontal: Spacing.md,
        paddingBottom: Spacing.md,
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
});
