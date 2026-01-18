import React, { useState } from 'react';
import { StyleSheet, View, TextInput, TouchableOpacity, Dimensions, ScrollView } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from '../ui/DonnaText';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withTiming,
} from 'react-native-reanimated';
import { format, addDays, setHours, setMinutes } from 'date-fns';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

interface TimeSlot {
    id: string;
    date: Date;
    startTime: string;
    endTime: string;
}

interface SchedulingSheetProps {
    isVisible: boolean;
    onClose: () => void;
    onSend: (selectedSlots: TimeSlot[], message: string) => void;
    recipientName?: string;
    subject?: string;
}

// Mock suggested time slots
const generateMockSlots = (): TimeSlot[] => {
    const today = new Date();
    return [
        { id: '1', date: addDays(today, 1), startTime: '10:00 AM', endTime: '10:30 AM' },
        { id: '2', date: addDays(today, 1), startTime: '2:00 PM', endTime: '2:30 PM' },
        { id: '3', date: addDays(today, 2), startTime: '11:00 AM', endTime: '11:30 AM' },
        { id: '4', date: addDays(today, 2), startTime: '3:00 PM', endTime: '3:30 PM' },
        { id: '5', date: addDays(today, 3), startTime: '9:00 AM', endTime: '9:30 AM' },
        { id: '6', date: addDays(today, 3), startTime: '4:00 PM', endTime: '4:30 PM' },
    ];
};

export const SchedulingSheet: React.FC<SchedulingSheetProps> = ({
    isVisible,
    onClose,
    onSend,
    recipientName = 'Recipient',
    subject = 'Meeting Request',
}) => {
    const [selectedSlots, setSelectedSlots] = useState<string[]>([]);
    const [message, setMessage] = useState(
        `Hi ${recipientName},\n\nI'd like to schedule a meeting to discuss "${subject}". Here are some times that work for me:\n\n[Selected times will appear here]\n\nLet me know what works best for you.\n\nBest regards`
    );
    const slots = generateMockSlots();

    // Animation
    const translateY = useSharedValue(SCREEN_HEIGHT);
    const opacity = useSharedValue(0);

    React.useEffect(() => {
        if (isVisible) {
            translateY.value = withSpring(0, { damping: 20, stiffness: 90 });
            opacity.value = withTiming(1, { duration: 250 });
        } else {
            translateY.value = withSpring(SCREEN_HEIGHT, { damping: 25, stiffness: 120 });
            opacity.value = withTiming(0, { duration: 200 });
        }
    }, [isVisible]);

    const animatedSheetStyle = useAnimatedStyle(() => ({
        transform: [{ translateY: translateY.value }],
    }));

    const backdropStyle = useAnimatedStyle(() => ({
        opacity: opacity.value,
    }));

    const toggleSlot = (slotId: string) => {
        setSelectedSlots(prev =>
            prev.includes(slotId)
                ? prev.filter(id => id !== slotId)
                : [...prev, slotId]
        );
    };

    const handleSend = () => {
        const selected = slots.filter(s => selectedSlots.includes(s.id));
        onSend(selected, message);
        onClose();
    };

    // Group slots by date
    const slotsByDate = slots.reduce((acc, slot) => {
        const dateKey = format(slot.date, 'yyyy-MM-dd');
        if (!acc[dateKey]) {
            acc[dateKey] = { date: slot.date, slots: [] };
        }
        acc[dateKey].slots.push(slot);
        return acc;
    }, {} as Record<string, { date: Date; slots: TimeSlot[] }>);

    if (!isVisible && translateY.value >= SCREEN_HEIGHT) {
        return null;
    }

    return (
        <>
            {/* Backdrop */}
            <Animated.View style={[styles.backdrop, backdropStyle]} pointerEvents={isVisible ? 'auto' : 'none'}>
                <TouchableOpacity style={styles.backdropTouch} onPress={onClose} activeOpacity={1} />
            </Animated.View>

            {/* Sheet */}
            <Animated.View style={[styles.sheet, animatedSheetStyle]}>
                <BlurView intensity={95} tint="light" style={styles.blurView}>
                    {/* Handle */}
                    <View style={styles.handle}>
                        <View style={styles.handleBar} />
                    </View>

                    {/* Header */}
                    <View style={styles.header}>
                        <TouchableOpacity onPress={onClose}>
                            <DonnaText style={styles.cancelText}>Cancel</DonnaText>
                        </TouchableOpacity>
                        <DonnaText style={styles.title}>Schedule Meeting</DonnaText>
                        <TouchableOpacity onPress={handleSend} disabled={selectedSlots.length === 0}>
                            <DonnaText style={[styles.sendText, selectedSlots.length === 0 && styles.sendDisabled]}>
                                Send
                            </DonnaText>
                        </TouchableOpacity>
                    </View>

                    <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
                        {/* Time Slots Section */}
                        <View style={styles.section}>
                            <View style={styles.sectionHeader}>
                                <Ionicons name="calendar-outline" size={18} color={Colors.accentSecondary} />
                                <DonnaText style={styles.sectionTitle}>SUGGESTED TIMES</DonnaText>
                            </View>
                            <DonnaText style={styles.sectionSubtitle}>
                                Select times that work for you (tap to select)
                            </DonnaText>

                            {Object.values(slotsByDate).map(({ date, slots: dateSlots }) => (
                                <View key={format(date, 'yyyy-MM-dd')} style={styles.dateGroup}>
                                    <DonnaText style={styles.dateLabel}>
                                        {format(date, 'EEEE, MMM d')}
                                    </DonnaText>
                                    <View style={styles.slotsRow}>
                                        {dateSlots.map(slot => {
                                            const isSelected = selectedSlots.includes(slot.id);
                                            return (
                                                <TouchableOpacity
                                                    key={slot.id}
                                                    style={[
                                                        styles.slotChip,
                                                        isSelected && styles.slotChipSelected
                                                    ]}
                                                    onPress={() => toggleSlot(slot.id)}
                                                >
                                                    {isSelected && (
                                                        <Ionicons name="checkmark" size={14} color="#FFF" />
                                                    )}
                                                    <DonnaText style={[
                                                        styles.slotText,
                                                        isSelected && styles.slotTextSelected
                                                    ]}>
                                                        {slot.startTime}
                                                    </DonnaText>
                                                </TouchableOpacity>
                                            );
                                        })}
                                    </View>
                                </View>
                            ))}
                        </View>

                        {/* Message Section */}
                        <View style={styles.section}>
                            <View style={styles.sectionHeader}>
                                <Ionicons name="mail-outline" size={18} color={Colors.accentPrecision} />
                                <DonnaText style={styles.sectionTitle}>MESSAGE</DonnaText>
                            </View>
                            <TextInput
                                style={styles.messageInput}
                                value={message}
                                onChangeText={setMessage}
                                multiline
                                textAlignVertical="top"
                            />
                        </View>

                        {/* Selected Summary */}
                        {selectedSlots.length > 0 && (
                            <View style={styles.summaryCard}>
                                <Ionicons name="checkmark-circle" size={20} color={Colors.success} />
                                <DonnaText style={styles.summaryText}>
                                    {selectedSlots.length} time{selectedSlots.length > 1 ? 's' : ''} selected
                                </DonnaText>
                            </View>
                        )}
                    </ScrollView>
                </BlurView>
            </Animated.View>
        </>
    );
};

const styles = StyleSheet.create({
    backdrop: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'rgba(0,0,0,0.3)',
        zIndex: 900,
    },
    backdropTouch: {
        flex: 1,
    },
    sheet: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        maxHeight: SCREEN_HEIGHT * 0.9,
        borderTopLeftRadius: Radius.xl,
        borderTopRightRadius: Radius.xl,
        overflow: 'hidden',
        zIndex: 901,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: -5 },
        shadowOpacity: 0.15,
        shadowRadius: 20,
        elevation: 15,
    },
    blurView: {
        backgroundColor: 'rgba(255, 255, 255, 0.92)',
    },
    handle: {
        alignItems: 'center',
        paddingVertical: Spacing.sm,
    },
    handleBar: {
        width: 36,
        height: 4,
        borderRadius: 2,
        backgroundColor: 'rgba(0,0,0,0.15)',
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingBottom: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(0,0,0,0.05)',
    },
    cancelText: {
        color: Colors.textSecondary,
        fontSize: 16,
    },
    title: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    sendText: {
        color: Colors.accentSecondary,
        fontSize: 16,
        fontWeight: '600',
    },
    sendDisabled: {
        opacity: 0.4,
    },
    scrollView: {
        maxHeight: SCREEN_HEIGHT * 0.7,
    },
    scrollContent: {
        padding: Spacing.md,
        paddingBottom: 40,
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        marginBottom: Spacing.xs,
    },
    sectionTitle: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
    },
    sectionSubtitle: {
        fontSize: 13,
        color: Colors.textSecondary,
        marginBottom: Spacing.md,
    },
    dateGroup: {
        marginBottom: Spacing.md,
    },
    dateLabel: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    slotsRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: Spacing.sm,
    },
    slotChip: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        paddingVertical: 8,
        paddingHorizontal: 14,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.bgSurface,
    },
    slotChipSelected: {
        backgroundColor: Colors.accentSecondary,
        borderColor: Colors.accentSecondary,
    },
    slotText: {
        fontSize: 14,
        color: Colors.textSecondary,
    },
    slotTextSelected: {
        color: '#FFF',
        fontWeight: '600',
    },
    messageInput: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        color: Colors.textPrimary,
        minHeight: 150,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
        lineHeight: 22,
    },
    summaryCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        padding: Spacing.md,
        backgroundColor: 'rgba(138, 154, 91, 0.1)',
        borderRadius: Radius.lg,
    },
    summaryText: {
        fontSize: 14,
        color: Colors.success,
        fontWeight: '500',
    },
});

export default SchedulingSheet;
