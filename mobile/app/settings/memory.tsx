import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';

interface Preference {
    id: string;
    context_type: 'communication' | 'scheduling' | 'tasks' | 'general';
    content: string;
    source: 'user' | 'learned';
    created_at: string;
}

// Mock preferences
const MOCK_PREFERENCES: Preference[] = [
    {
        id: '1',
        context_type: 'communication',
        content: 'Prefers formal tone in work emails',
        source: 'user',
        created_at: '2026-01-10',
    },
    {
        id: '2',
        context_type: 'scheduling',
        content: 'No meetings before 10 AM',
        source: 'user',
        created_at: '2026-01-08',
    },
    {
        id: '3',
        context_type: 'tasks',
        content: 'Likes to batch similar tasks together',
        source: 'learned',
        created_at: '2026-01-15',
    },
    {
        id: '4',
        context_type: 'communication',
        content: 'Signs off emails with "Best regards" for external contacts',
        source: 'learned',
        created_at: '2026-01-12',
    },
    {
        id: '5',
        context_type: 'scheduling',
        content: 'Prefers 25-minute meetings over 30-minute ones',
        source: 'learned',
        created_at: '2026-01-14',
    },
];

const CONTEXT_ICONS: Record<string, { icon: string; color: string }> = {
    communication: { icon: 'chatbubbles-outline', color: Colors.accentSecondary },
    scheduling: { icon: 'calendar-outline', color: Colors.accentPrecision },
    tasks: { icon: 'checkbox-outline', color: Colors.success },
    general: { icon: 'settings-outline', color: Colors.textSecondary },
};

export default function MemoryScreen() {
    const router = useRouter();
    const [preferences, setPreferences] = useState(MOCK_PREFERENCES);

    const handleDelete = (id: string) => {
        Alert.alert(
            'Remove Preference',
            'Are you sure you want to remove this preference?',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Remove', style: 'destructive', onPress: () => {
                        setPreferences(prev => prev.filter(p => p.id !== id));
                    }
                },
            ]
        );
    };

    const handleAddPreference = () => {
        Alert.prompt(
            'Add Preference',
            'Tell Donna something about your work style:',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Add', onPress: (text: string | undefined) => {
                        if (text?.trim()) {
                            const newPref: Preference = {
                                id: Date.now().toString(),
                                context_type: 'general',
                                content: text.trim(),
                                source: 'user',
                                created_at: new Date().toISOString().split('T')[0],
                            };
                            setPreferences(prev => [newPref, ...prev]);
                        }
                    }
                },
            ],
            'plain-text'
        );
    };

    // Group by context type
    const groupedPreferences = preferences.reduce((acc, pref) => {
        if (!acc[pref.context_type]) acc[pref.context_type] = [];
        acc[pref.context_type].push(pref);
        return acc;
    }, {} as Record<string, Preference[]>);

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Memory & Preferences</DonnaText>
                <TouchableOpacity onPress={handleAddPreference} style={styles.addButton}>
                    <Ionicons name="add" size={24} color={Colors.accentSecondary} />
                </TouchableOpacity>
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Explanation Card */}
                <View style={styles.explanationCard}>
                    <Ionicons name="bulb-outline" size={24} color={Colors.accentSecondary} />
                    <View style={styles.explanationText}>
                        <DonnaText style={styles.explanationTitle}>How Donna Learns</DonnaText>
                        <DonnaText style={styles.explanationBody}>
                            Donna remembers your preferences and work patterns to give better suggestions.
                            Items marked with ✨ were learned automatically.
                        </DonnaText>
                    </View>
                </View>

                {/* Grouped Preferences */}
                {Object.entries(groupedPreferences).map(([contextType, prefs]) => {
                    const { icon, color } = CONTEXT_ICONS[contextType] || CONTEXT_ICONS.general;
                    return (
                        <View key={contextType} style={styles.section}>
                            <View style={styles.sectionHeader}>
                                <Ionicons name={icon as any} size={16} color={color} />
                                <DonnaText style={styles.sectionLabel}>
                                    {contextType.toUpperCase()}
                                </DonnaText>
                            </View>
                            {prefs.map(pref => (
                                <View key={pref.id} style={styles.prefCard}>
                                    <View style={styles.prefContent}>
                                        {pref.source === 'learned' && (
                                            <DonnaText style={styles.learnedBadge}>✨ LEARNED</DonnaText>
                                        )}
                                        <DonnaText style={styles.prefText}>{pref.content}</DonnaText>
                                        <DonnaText style={styles.prefDate}>
                                            Added {pref.created_at}
                                        </DonnaText>
                                    </View>
                                    <TouchableOpacity
                                        onPress={() => handleDelete(pref.id)}
                                        style={styles.deleteButton}
                                    >
                                        <Ionicons name="trash-outline" size={18} color={Colors.error} />
                                    </TouchableOpacity>
                                </View>
                            ))}
                        </View>
                    );
                })}

                {preferences.length === 0 && (
                    <View style={styles.emptyState}>
                        <Ionicons name="bulb-outline" size={48} color={Colors.textMuted} />
                        <DonnaText style={styles.emptyText}>No preferences yet</DonnaText>
                        <DonnaText style={styles.emptySubtext}>
                            Tap + to add your first preference
                        </DonnaText>
                    </View>
                )}
            </ScrollView>
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
    addButton: {
        padding: Spacing.xs,
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
        alignItems: 'flex-start',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: 'rgba(217, 119, 69, 0.06)',
        borderRadius: Radius.lg,
        marginBottom: Spacing.xl,
    },
    explanationText: {
        flex: 1,
    },
    explanationTitle: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: 4,
    },
    explanationBody: {
        fontSize: 13,
        color: Colors.textSecondary,
        lineHeight: 18,
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        marginBottom: Spacing.sm,
    },
    sectionLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
    },
    prefCard: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        padding: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    prefContent: {
        flex: 1,
    },
    learnedBadge: {
        fontSize: 9,
        fontWeight: '700',
        color: Colors.accentSecondary,
        letterSpacing: 0.5,
        marginBottom: 4,
    },
    prefText: {
        fontSize: 15,
        color: Colors.textPrimary,
        lineHeight: 20,
    },
    prefDate: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 4,
    },
    deleteButton: {
        padding: Spacing.xs,
    },
    emptyState: {
        alignItems: 'center',
        paddingVertical: 60,
    },
    emptyText: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textSecondary,
        marginTop: Spacing.md,
    },
    emptySubtext: {
        fontSize: 14,
        color: Colors.textMuted,
        marginTop: 4,
    },
});
