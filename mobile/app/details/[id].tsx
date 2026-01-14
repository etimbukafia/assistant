import React, { useState } from 'react';
import { View, StyleSheet, SafeAreaView, ScrollView, Pressable } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { DonnaButton } from '../../src/components/ui/DonnaButton';
import { StatusBar } from 'expo-status-bar';
import demoData from '../../src/data/demo_state.json';
import FontAwesome from '@expo/vector-icons/FontAwesome';
import Animated, { FadeIn, FadeOut, Layout } from 'react-native-reanimated';

export default function DetailsScreen() {
    const { id } = useLocalSearchParams();
    const router = useRouter();
    const message = demoData.messages.find(m => m.id === id) || demoData.messages[0];

    const [selectedSlots, setSelectedSlots] = useState<string[]>([]);
    const [isSent, setIsSent] = useState(false);

    const slots = [
        { id: 's1', time: 'Monday, 2:00 PM', label: 'Primary choice' },
        { id: 's2', time: 'Tuesday, 10:30 AM', label: 'Backup' },
    ];

    const toggleSlot = (slotId: string) => {
        setSelectedSlots(prev =>
            prev.includes(slotId) ? prev.filter(s => s !== slotId) : [...prev, slotId]
        );
    };

    const handleSend = () => {
        setIsSent(true);
        setTimeout(() => {
            router.back();
        }, 2000);
    };

    if (isSent) {
        return (
            <View style={[styles.container, styles.center]}>
                <Animated.View entering={FadeIn} style={styles.bloomContainer}>
                    <View style={styles.bloomCircle} />
                    <DonnaText variant="h2" color={Colors.success}>Handled.</DonnaText>
                    <DonnaText variant="bodyBase" color={Colors.textMuted}>Donna is taking care of the rest.</DonnaText>
                </Animated.View>
            </View>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="light" />
            <View style={styles.header}>
                <Pressable onPress={() => router.back()} style={styles.backButton}>
                    <FontAwesome name="chevron-left" size={20} color={Colors.textPrimary} />
                </Pressable>
                <DonnaText variant="h2">Briefing</DonnaText>
                <View style={{ width: 40 }} />
            </View>

            <ScrollView contentContainerStyle={styles.scrollContent}>
                <View style={styles.messageSection}>
                    <DonnaText variant="labelSmall" color={Colors.textMuted}>{message.sender} • {message.time}</DonnaText>
                    <DonnaText variant="h1" style={styles.title}>{message.title}</DonnaText>
                    <DonnaText variant="bodyLarge" style={styles.snippet}>{message.snippet}</DonnaText>
                </View>

                <View style={styles.insightBox}>
                    <DonnaText variant="labelSmall" color={Colors.accentPrecision}>CERULEAN INSIGHT</DonnaText>
                    <DonnaText variant="bodyBase" style={styles.insightText}>{message.insight}</DonnaText>
                </View>

                <View style={styles.suggestionSection}>
                    <DonnaText variant="h2" style={styles.sectionTitle}>Donna's Suggestions</DonnaText>
                    {slots.map(slot => (
                        <Pressable
                            key={slot.id}
                            onPress={() => toggleSlot(slot.id)}
                            style={[
                                styles.slotCard,
                                selectedSlots.includes(slot.id) && styles.slotSelected
                            ]}
                        >
                            <View>
                                <DonnaText variant="labelSmall" color={Colors.accentPrecision}>{slot.label}</DonnaText>
                                <DonnaText variant="bodyBase">{slot.time}</DonnaText>
                            </View>
                            <View style={[
                                styles.checkbox,
                                selectedSlots.includes(slot.id) && styles.checkboxChecked
                            ]}>
                                {selectedSlots.includes(slot.id) && <FontAwesome name="check" size={10} color={Colors.textPrimary} />}
                            </View>
                        </Pressable>
                    ))}
                </View>
            </ScrollView>

            <View style={styles.footer}>
                <DonnaButton
                    title={`Send ${selectedSlots.length > 0 ? selectedSlots.length : ''} Options`}
                    onPress={handleSend}
                    fullWidth
                />
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    center: {
        justifyContent: 'center',
        alignItems: 'center',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: Spacing.md,
    },
    backButton: {
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
    },
    scrollContent: {
        padding: Spacing.md,
    },
    messageSection: {
        marginBottom: Spacing.xl,
    },
    title: {
        marginTop: Spacing.xs,
        marginBottom: Spacing.md,
    },
    snippet: {
        lineHeight: 28,
    },
    insightBox: {
        backgroundColor: Colors.bgElevated,
        padding: Spacing.md,
        borderRadius: Radius.surface,
        borderLeftWidth: 4,
        borderLeftColor: Colors.accentPrecision,
        marginBottom: Spacing.xl,
    },
    insightText: {
        marginTop: Spacing.xs,
        fontStyle: 'italic',
    },
    suggestionSection: {
        marginBottom: Spacing.xl,
    },
    sectionTitle: {
        marginBottom: Spacing.md,
    },
    slotCard: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: Colors.bgElevated,
        padding: Spacing.md,
        borderRadius: Radius.component,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    slotSelected: {
        borderColor: Colors.accentPrecision,
        backgroundColor: 'rgba(0, 123, 167, 0.05)',
    },
    checkbox: {
        width: 18,
        height: 18,
        borderRadius: 9,
        borderWidth: 1,
        borderColor: Colors.textMuted,
        alignItems: 'center',
        justifyContent: 'center',
    },
    checkboxChecked: {
        backgroundColor: Colors.accentPrecision,
        borderColor: Colors.accentPrecision,
    },
    footer: {
        padding: Spacing.md,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
    },
    bloomContainer: {
        alignItems: 'center',
    },
    bloomCircle: {
        width: 80,
        height: 80,
        borderRadius: 40,
        backgroundColor: Colors.success,
        opacity: 0.1,
        position: 'absolute',
        transform: [{ scale: 2 }],
    },
});
