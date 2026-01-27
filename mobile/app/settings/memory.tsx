import React, { useState } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Alert, ActivityIndicator, TextInput, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { usePreferencesWithMutations } from '@/src/hooks/usePreferences';
import { PrincipalMemory } from '@/src/services/memory';

const CONTEXT_ICONS: Record<string, { icon: string; color: string }> = {
    communication: { icon: 'chatbubbles-outline', color: Colors.accentSecondary },
    drafting: { icon: 'create-outline', color: Colors.accentSecondary },
    scheduling: { icon: 'calendar-outline', color: Colors.accentPrecision },
    task_review: { icon: 'checkbox-outline', color: Colors.success },
    tasks: { icon: 'checkbox-outline', color: Colors.success },
    general: { icon: 'settings-outline', color: Colors.textSecondary },
};

const CONTEXT_TYPE_OPTIONS = [
    { value: 'communication', label: 'Communication' },
    { value: 'scheduling', label: 'Scheduling' },
    { value: 'task_review', label: 'Tasks' },
    { value: 'general', label: 'General' },
];

export default function MemoryScreen() {
    const router = useRouter();

    // Modal state for adding preferences
    const [showAddModal, setShowAddModal] = useState(false);
    const [newPrefValue, setNewPrefValue] = useState('');
    const [newPrefContext, setNewPrefContext] = useState('general');

    // Fetch preferences and mutations using hook
    const {
        preferences,
        isLoading,
        error,
        create,
        isCreating,
        delete: deletePreference,
        isDeleting,
        isSandbox,
    } = usePreferencesWithMutations();

    const handleDelete = (pref: PrincipalMemory) => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Preference management is disabled in demo mode. Connect your email to enable.');
            return;
        }
        Alert.alert(
            'Remove Preference',
            'Are you sure you want to remove this preference?',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Remove',
                    style: 'destructive',
                    onPress: () => deletePreference(pref.id),
                },
            ]
        );
    };

    const handleAddPreference = () => {
        if (isSandbox) {
            Alert.alert('Demo Mode', 'Preference management is disabled in demo mode. Connect your email to enable.');
            return;
        }
        if (!newPrefValue.trim()) {
            Alert.alert('Error', 'Please enter a preference');
            return;
        }
        create(
            {
                key: `pref_${Date.now()}`,
                value: newPrefValue.trim(),
                context_type: newPrefContext,
                source: 'manual',
            },
            {
                onSuccess: () => {
                    setShowAddModal(false);
                    setNewPrefValue('');
                    setNewPrefContext('general');
                },
            }
        );
    };

    // Group preferences by context type
    const groupedPreferences = preferences.reduce((acc, pref) => {
        const type = pref.context_type || 'general';
        if (!acc[type]) acc[type] = [];
        acc[type].push(pref);
        return acc;
    }, {} as Record<string, PrincipalMemory[]>);

    // Loading state
    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <DonnaText style={styles.headerTitle}>Memory & Preferences</DonnaText>
                    <View style={styles.headerPlaceholder} />
                </View>
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
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
                <DonnaText style={styles.headerTitle}>Memory & Preferences</DonnaText>
                <TouchableOpacity onPress={() => setShowAddModal(true)} style={styles.addButton}>
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
                            Items marked with "LEARNED" were discovered automatically.
                        </DonnaText>
                    </View>
                </View>

                {/* Error state */}
                {error && (
                    <View style={styles.errorCard}>
                        <Ionicons name="warning-outline" size={20} color={Colors.error} />
                        <DonnaText style={styles.errorText}>Failed to load preferences</DonnaText>
                    </View>
                )}

                {/* Grouped Preferences */}
                {Object.entries(groupedPreferences).map(([contextType, prefs]) => {
                    const { icon, color } = CONTEXT_ICONS[contextType] || CONTEXT_ICONS.general;
                    const displayName = contextType.replace('_', ' ').toUpperCase();

                    return (
                        <View key={contextType} style={styles.section}>
                            <View style={styles.sectionHeader}>
                                <Ionicons name={icon as any} size={16} color={color} />
                                <DonnaText style={styles.sectionLabel}>{displayName}</DonnaText>
                            </View>
                            {prefs.map((pref) => (
                                <View key={pref.id} style={styles.prefCard}>
                                    <View style={styles.prefContent}>
                                        {pref.source === 'approved_suggestion' && (
                                            <DonnaText style={styles.learnedBadge}>LEARNED</DonnaText>
                                        )}
                                        <DonnaText style={styles.prefText}>{pref.value}</DonnaText>
                                        <DonnaText style={styles.prefDate}>
                                            Added {new Date(pref.created_at).toLocaleDateString()}
                                        </DonnaText>
                                    </View>
                                    <TouchableOpacity
                                        onPress={() => handleDelete(pref)}
                                        style={styles.deleteButton}
                                        disabled={isDeleting}
                                    >
                                        {isDeleting ? (
                                            <ActivityIndicator size="small" color={Colors.error} />
                                        ) : (
                                            <Ionicons name="trash-outline" size={18} color={Colors.error} />
                                        )}
                                    </TouchableOpacity>
                                </View>
                            ))}
                        </View>
                    );
                })}

                {/* Empty State */}
                {preferences.length === 0 && !error && (
                    <View style={styles.emptyState}>
                        <Ionicons name="bulb-outline" size={48} color={Colors.textMuted} />
                        <DonnaText style={styles.emptyText}>No preferences yet</DonnaText>
                        <DonnaText style={styles.emptySubtext}>
                            Tap + to add your first preference
                        </DonnaText>
                    </View>
                )}
            </ScrollView>

            {/* Add Preference Modal */}
            <Modal
                visible={showAddModal}
                animationType="slide"
                transparent={true}
                onRequestClose={() => setShowAddModal(false)}
            >
                <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                        <View style={styles.modalHeader}>
                            <DonnaText style={styles.modalTitle}>Add Preference</DonnaText>
                            <TouchableOpacity onPress={() => setShowAddModal(false)}>
                                <Ionicons name="close" size={24} color={Colors.textPrimary} />
                            </TouchableOpacity>
                        </View>

                        <DonnaText style={styles.modalLabel}>Category</DonnaText>
                        <View style={styles.contextPicker}>
                            {CONTEXT_TYPE_OPTIONS.map((option) => (
                                <TouchableOpacity
                                    key={option.value}
                                    style={[
                                        styles.contextOption,
                                        newPrefContext === option.value && styles.contextOptionActive,
                                    ]}
                                    onPress={() => setNewPrefContext(option.value)}
                                >
                                    <DonnaText
                                        style={[
                                            styles.contextOptionText,
                                            newPrefContext === option.value && styles.contextOptionTextActive,
                                        ]}
                                    >
                                        {option.label}
                                    </DonnaText>
                                </TouchableOpacity>
                            ))}
                        </View>

                        <DonnaText style={styles.modalLabel}>Preference</DonnaText>
                        <TextInput
                            style={styles.input}
                            placeholder="Tell Donna something about your work style..."
                            placeholderTextColor={Colors.textMuted}
                            value={newPrefValue}
                            onChangeText={setNewPrefValue}
                            multiline
                            numberOfLines={3}
                        />

                        <TouchableOpacity
                            style={[styles.addBtn, isCreating && styles.addBtnDisabled]}
                            onPress={handleAddPreference}
                            disabled={isCreating}
                        >
                            {isCreating ? (
                                <ActivityIndicator size="small" color="#FFF" />
                            ) : (
                                <DonnaText style={styles.addBtnText}>Add Preference</DonnaText>
                            )}
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
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
    headerPlaceholder: {
        width: 32,
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
    errorCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        padding: Spacing.md,
        backgroundColor: 'rgba(128, 0, 32, 0.08)',
        borderRadius: Radius.lg,
        marginBottom: Spacing.xl,
    },
    errorText: {
        fontSize: 14,
        color: Colors.error,
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
    // Modal styles
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        backgroundColor: Colors.bgBase,
        borderTopLeftRadius: Radius.xl,
        borderTopRightRadius: Radius.xl,
        padding: Spacing.lg,
        paddingBottom: Spacing.xl + 20,
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: Spacing.lg,
    },
    modalTitle: {
        fontSize: 18,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    modalLabel: {
        fontSize: 13,
        fontWeight: '600',
        color: Colors.textMuted,
        marginBottom: Spacing.sm,
        marginTop: Spacing.md,
    },
    contextPicker: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: Spacing.sm,
    },
    contextOption: {
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.bgElevated,
    },
    contextOptionActive: {
        borderColor: Colors.accentSecondary,
        backgroundColor: 'rgba(217, 119, 69, 0.1)',
    },
    contextOptionText: {
        fontSize: 14,
        color: Colors.textSecondary,
    },
    contextOptionTextActive: {
        color: Colors.accentSecondary,
        fontWeight: '600',
    },
    input: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        padding: Spacing.md,
        fontSize: 15,
        color: Colors.textPrimary,
        minHeight: 100,
        textAlignVertical: 'top',
    },
    addBtn: {
        backgroundColor: Colors.accentSecondary,
        borderRadius: Radius.full,
        paddingVertical: 14,
        alignItems: 'center',
        marginTop: Spacing.lg,
    },
    addBtnDisabled: {
        opacity: 0.7,
    },
    addBtnText: {
        color: '#FFF',
        fontSize: 16,
        fontWeight: '600',
    },
});
