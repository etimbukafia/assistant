import React, { useState } from 'react';
import { StyleSheet, View, TouchableOpacity, ActivityIndicator, Modal, Linking, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from './DonnaText';
import { Ionicons } from '@expo/vector-icons';
import { format, parseISO } from 'date-fns';

export interface TimeSlot {
    start_time: string;
    end_time: string;
    has_conflict: boolean;
    conflict_details?: string;
}

export interface SchedulingSuggestionProps {
    title: string;
    duration_minutes: number;
    attendees: string[];
    time_slots: TimeSlot[];
    draft_message?: string;
    onSelectSlot: (slotIndex: number) => void;
    onDismiss?: () => void;
    isLoading?: boolean;
    isSlotsLoading?: boolean;
    error?: string | null;
}

interface ConfirmationState {
    visible: boolean;
    slotIndex: number;
    slot: TimeSlot | null;
}

// Skeleton loader for time slots
function TimeSlotSkeleton() {
    return (
        <View style={styles.skeletonContainer}>
            {[0, 1, 2].map((i) => (
                <View key={i} style={styles.skeletonSlot}>
                    <View style={styles.skeletonContent}>
                        <View style={styles.skeletonDate} />
                        <View style={styles.skeletonTime} />
                    </View>
                    <View style={styles.skeletonChevron} />
                </View>
            ))}
        </View>
    );
}

export function SchedulingSuggestionCard({
    title,
    duration_minutes,
    attendees,
    time_slots,
    draft_message,
    onSelectSlot,
    onDismiss,
    isLoading,
    isSlotsLoading,
    error,
}: SchedulingSuggestionProps) {
    const [confirmation, setConfirmation] = useState<ConfirmationState>({
        visible: false,
        slotIndex: -1,
        slot: null,
    });

    const formatSlotTime = (slot: TimeSlot) => {
        const start = parseISO(slot.start_time);
        const end = parseISO(slot.end_time);
        return {
            date: format(start, 'EEE, MMM d'),
            time: `${format(start, 'h:mm a')} - ${format(end, 'h:mm a')}`,
            fullDate: format(start, 'yyyy-MM-dd'),
        };
    };

    const handleSlotPress = (index: number) => {
        setConfirmation({
            visible: true,
            slotIndex: index,
            slot: time_slots[index],
        });
    };

    const handleConfirm = () => {
        if (confirmation.slotIndex >= 0) {
            onSelectSlot(confirmation.slotIndex);
        }
        setConfirmation({ visible: false, slotIndex: -1, slot: null });
    };

    const handleCancel = () => {
        setConfirmation({ visible: false, slotIndex: -1, slot: null });
    };

    // Open calendar app to specific date
    const openCalendarApp = (date?: string) => {
        if (Platform.OS === 'ios') {
            // iOS: calshow:// opens Calendar app
            // Adding a timestamp opens to that date
            if (date) {
                const targetDate = parseISO(date);
                const timestamp = Math.floor(targetDate.getTime() / 1000);
                Linking.openURL(`calshow:${timestamp}`);
            } else {
                Linking.openURL('calshow://');
            }
        } else {
            // Android: content://com.android.calendar/time/
            if (date) {
                const targetDate = parseISO(date);
                Linking.openURL(`content://com.android.calendar/time/${targetDate.getTime()}`);
            } else {
                Linking.openURL('content://com.android.calendar/time/');
            }
        }
    };

    return (
        <View style={styles.container}>
            {/* Header */}
            <View style={styles.header}>
                <View style={styles.headerIcon}>
                    <Ionicons name="calendar" size={20} color={Colors.accentSecondary} />
                </View>
                <View style={styles.headerContent}>
                    <DonnaText style={styles.headerTitle}>Schedule Meeting</DonnaText>
                    <DonnaText variant="caption" style={styles.headerSubtitle}>
                        {title} • {duration_minutes} min
                    </DonnaText>
                </View>
                {onDismiss && (
                    <TouchableOpacity onPress={onDismiss} style={styles.dismissButton}>
                        <Ionicons name="close" size={20} color={Colors.textMuted} />
                    </TouchableOpacity>
                )}
            </View>

            {/* Attendees */}
            {attendees.length > 0 && (
                <View style={styles.attendeesRow}>
                    <Ionicons name="people-outline" size={14} color={Colors.textMuted} />
                    <DonnaText variant="caption" style={styles.attendeesText}>
                        {attendees.slice(0, 2).join(', ')}
                        {attendees.length > 2 && ` +${attendees.length - 2} more`}
                    </DonnaText>
                </View>
            )}

            {/* Time Slots */}
            <View style={styles.slotsContainer}>
                <DonnaText style={styles.slotsLabel}>SUGGESTED TIMES</DonnaText>

                {/* Error State */}
                {error && (
                    <View style={styles.errorContainer}>
                        <Ionicons name="alert-circle-outline" size={24} color={Colors.error} />
                        <DonnaText style={styles.errorText}>{error}</DonnaText>
                        <TouchableOpacity style={styles.retryButton}>
                            <DonnaText style={styles.retryButtonText}>Retry</DonnaText>
                        </TouchableOpacity>
                    </View>
                )}

                {/* Skeleton Loading */}
                {isSlotsLoading && !error && <TimeSlotSkeleton />}

                {/* Actual Slots */}
                {!isSlotsLoading && !error && time_slots.map((slot, index) => {
                    const { date, time } = formatSlotTime(slot);
                    return (
                        <TouchableOpacity
                            key={index}
                            style={[
                                styles.slotButton,
                                slot.has_conflict && styles.slotButtonConflict,
                            ]}
                            onPress={() => handleSlotPress(index)}
                            disabled={isLoading}
                        >
                            <View style={styles.slotContent}>
                                <DonnaText style={styles.slotDate}>{date}</DonnaText>
                                <DonnaText style={styles.slotTime}>{time}</DonnaText>
                                {slot.has_conflict && (
                                    <View style={styles.conflictBadge}>
                                        <Ionicons name="warning" size={10} color="#D97706" />
                                        <DonnaText style={styles.conflictText}>
                                            {slot.conflict_details || 'Conflict'}
                                        </DonnaText>
                                    </View>
                                )}
                            </View>
                            <Ionicons
                                name="chevron-forward"
                                size={18}
                                color={slot.has_conflict ? Colors.textMuted : Colors.accentSecondary}
                            />
                        </TouchableOpacity>
                    );
                })}
            </View>

            {/* Loading Overlay */}
            {isLoading && (
                <View style={styles.loadingOverlay}>
                    <ActivityIndicator size="small" color={Colors.accentPrimary} />
                    <DonnaText variant="caption" style={styles.loadingText}>Creating event...</DonnaText>
                </View>
            )}

            {/* Confirmation Modal */}
            <Modal
                visible={confirmation.visible}
                transparent
                animationType="fade"
                onRequestClose={handleCancel}
            >
                <View style={styles.modalBackdrop}>
                    <View style={styles.modalContent}>
                        <View style={styles.modalIcon}>
                            <Ionicons name="calendar-outline" size={32} color={Colors.accentSecondary} />
                        </View>
                        <DonnaText style={styles.modalTitle}>Confirm Meeting</DonnaText>
                        {confirmation.slot && (
                            <>
                                <DonnaText style={styles.modalEventTitle}>{title}</DonnaText>
                                <DonnaText style={styles.modalEventTime}>
                                    {formatSlotTime(confirmation.slot).date}
                                </DonnaText>
                                <DonnaText style={styles.modalEventTime}>
                                    {formatSlotTime(confirmation.slot).time}
                                </DonnaText>
                                {attendees.length > 0 && (
                                    <DonnaText style={styles.modalAttendees}>
                                        With: {attendees.join(', ')}
                                    </DonnaText>
                                )}
                            </>
                        )}
                        <View style={styles.modalButtons}>
                            <TouchableOpacity style={styles.modalCancelButton} onPress={handleCancel}>
                                <DonnaText style={styles.modalCancelText}>Cancel</DonnaText>
                            </TouchableOpacity>
                            <TouchableOpacity style={styles.modalConfirmButton} onPress={handleConfirm}>
                                <Ionicons name="checkmark" size={18} color="#FFF" />
                                <DonnaText style={styles.modalConfirmText}>Create Event</DonnaText>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </Modal>
        </View>
    );
}

// Export helper for opening calendar after event creation
export function openCalendarToDate(dateString: string) {
    const targetDate = parseISO(dateString);
    if (Platform.OS === 'ios') {
        const timestamp = Math.floor(targetDate.getTime() / 1000);
        Linking.openURL(`calshow:${timestamp}`);
    } else {
        Linking.openURL(`content://com.android.calendar/time/${targetDate.getTime()}`);
    }
}

const styles = StyleSheet.create({
    container: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        borderWidth: 1,
        borderColor: 'rgba(59, 130, 246, 0.2)',
        marginBottom: Spacing.lg,
        overflow: 'hidden',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: Spacing.md,
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(59, 130, 246, 0.1)',
    },
    headerIcon: {
        width: 36,
        height: 36,
        borderRadius: 18,
        backgroundColor: 'rgba(59, 130, 246, 0.15)',
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.sm,
    },
    headerContent: {
        flex: 1,
    },
    headerTitle: {
        fontWeight: '600',
        fontSize: 15,
        color: Colors.textPrimary,
    },
    headerSubtitle: {
        color: Colors.textMuted,
        marginTop: 2,
    },
    dismissButton: {
        padding: Spacing.xs,
    },
    attendeesRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    attendeesText: {
        color: Colors.textMuted,
    },
    slotsContainer: {
        padding: Spacing.md,
    },
    slotsLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 0.5,
        marginBottom: Spacing.sm,
    },
    slotButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: Spacing.md,
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
        marginBottom: Spacing.xs,
    },
    slotButtonConflict: {
        borderColor: 'rgba(245, 158, 11, 0.3)',
        backgroundColor: 'rgba(245, 158, 11, 0.05)',
    },
    slotContent: {
        flex: 1,
    },
    slotDate: {
        fontSize: 13,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    slotTime: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 2,
    },
    conflictBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        marginTop: 4,
    },
    conflictText: {
        fontSize: 11,
        color: '#D97706',
    },
    loadingOverlay: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingText: {
        marginTop: Spacing.xs,
        color: Colors.textMuted,
    },
    // Skeleton styles
    skeletonContainer: {
        gap: Spacing.xs,
    },
    skeletonSlot: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: Spacing.md,
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    skeletonContent: {
        flex: 1,
    },
    skeletonDate: {
        height: 14,
        width: 100,
        backgroundColor: Colors.border,
        borderRadius: 4,
        marginBottom: 6,
    },
    skeletonTime: {
        height: 12,
        width: 150,
        backgroundColor: Colors.border,
        borderRadius: 4,
    },
    skeletonChevron: {
        width: 18,
        height: 18,
        backgroundColor: Colors.border,
        borderRadius: 4,
    },
    // Error styles
    errorContainer: {
        alignItems: 'center',
        padding: Spacing.lg,
    },
    errorText: {
        color: Colors.error,
        marginTop: Spacing.sm,
        textAlign: 'center',
    },
    retryButton: {
        marginTop: Spacing.md,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    retryButtonText: {
        color: Colors.accentPrimary,
        fontWeight: '600',
    },
    // Confirmation modal styles
    modalBackdrop: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.lg,
    },
    modalContent: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        padding: Spacing.lg,
        width: '100%',
        maxWidth: 320,
        alignItems: 'center',
    },
    modalIcon: {
        width: 56,
        height: 56,
        borderRadius: 28,
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.md,
    },
    modalTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    modalEventTitle: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
        textAlign: 'center',
    },
    modalEventTime: {
        fontSize: 14,
        color: Colors.textMuted,
        marginTop: 2,
    },
    modalAttendees: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: Spacing.sm,
        textAlign: 'center',
    },
    modalButtons: {
        flexDirection: 'row',
        gap: Spacing.sm,
        marginTop: Spacing.lg,
        width: '100%',
    },
    modalCancelButton: {
        flex: 1,
        paddingVertical: Spacing.md,
        borderRadius: Radius.full,
        backgroundColor: Colors.bgBase,
        borderWidth: 1,
        borderColor: Colors.border,
        alignItems: 'center',
    },
    modalCancelText: {
        color: Colors.textPrimary,
        fontWeight: '500',
    },
    modalConfirmButton: {
        flex: 1,
        flexDirection: 'row',
        paddingVertical: Spacing.md,
        borderRadius: Radius.full,
        backgroundColor: Colors.accentSecondary,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
    },
    modalConfirmText: {
        color: '#FFF',
        fontWeight: '600',
    },
});
