
import React, { useState } from 'react';
import { StyleSheet, View, TouchableOpacity, ScrollView, Alert, ActivityIndicator, TextInput } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { activateTrial, triggerInitialSync } from '../../src/services/billing';

export default function ActivateTrialScreen() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const { refreshProfile } = useAuth();
    const [selectedIntegrations, setSelectedIntegrations] = useState(['gmail']);
    const [assistantName, setAssistantName] = useState('Donna');

    const toggleIntegration = (id: string) => {
        if (id === 'gmail') return; // Mandatory
        if (selectedIntegrations.includes(id)) {
            setSelectedIntegrations(prev => prev.filter(i => i !== id));
        } else {
            setSelectedIntegrations(prev => [...prev, id]);
        }
    };

    // Combined mutation for trial activation + initial sync
    const activationMutation = useMutation({
        mutationFn: async () => {
            // 1. Activate Trial with Assistant Name
            await activateTrial({ assistant_name: assistantName.trim() || 'Donna' });
            // 2. Trigger Initial Sync (may fail if GmailAccount not yet created — AuthContext handles it)
            await triggerInitialSync().catch((e: any) => console.warn('Initial sync skipped:', e?.message));
        },
        onSuccess: async () => {
            // 3. Invalidate subscription queries
            queryClient.invalidateQueries({ queryKey: ['subscription'] });
            // 4. Refresh local profile to update subscription state
            await refreshProfile();
            // 5. Navigate back to Inbox
            router.replace('/(tabs)');
        },
        onError: (error: any) => {
            console.error('Activation failed:', error);
            Alert.alert(
                "Activation Failed",
                error.response?.data?.detail || "Something went wrong. Please try again."
            );
        },
    });

    const handleActivate = () => {
        activationMutation.mutate();
    };

    return (
        <View style={styles.container}>
            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText variant="h2">Activate Trial</DonnaText>
            </View>

            <ScrollView contentContainerStyle={styles.content}>
                <View style={styles.hero}>
                    <View style={styles.iconCircle}>
                        <Ionicons name="rocket" size={32} color={Colors.accentPrimary} />
                    </View>
                    <DonnaText variant="h1" style={styles.heroTitle}>Unlock the Brain</DonnaText>
                    <DonnaText style={styles.heroText}>
                        Connect your real accounts to experience the full power of the AI Assistant free for 7 days.
                    </DonnaText>
                </View>

                {/* Assistant Name Section */}
                <View style={styles.section}>
                    <DonnaText variant="overline" style={styles.sectionTitle}>
                        Name Your Assistant
                    </DonnaText>
                    <View style={styles.nameInputContainer}>
                        <TextInput
                            style={styles.nameInput}
                            value={assistantName}
                            onChangeText={setAssistantName}
                            placeholder="Donna"
                            placeholderTextColor={Colors.textMuted}
                            maxLength={50}
                            autoCapitalize="words"
                        />
                    </View>
                    <DonnaText style={styles.nameHint}>
                        This is what your AI assistant will be called
                    </DonnaText>
                </View>

                <View style={styles.section}>
                    <DonnaText variant="overline" style={styles.sectionTitle}>Select Integrations</DonnaText>

                    {/* Gmail (Mandatory) */}
                    <TouchableOpacity
                        style={[styles.optionCard, styles.optionSelected]}
                        onPress={() => toggleIntegration('gmail')}
                        activeOpacity={0.9}
                    >
                        <View style={styles.optionIcon}>
                            <Ionicons name="mail" size={24} color="#EA4335" />
                        </View>
                        <View style={styles.optionContent}>
                            <DonnaText style={styles.optionTitle}>Gmail</DonnaText>
                            <DonnaText style={styles.optionDesc}>Required for email processing</DonnaText>
                        </View>
                        <Ionicons name="checkmark-circle" size={24} color={Colors.accentPrimary} />
                    </TouchableOpacity>

                    {/* Calendar (Optional) */}
                    <TouchableOpacity
                        style={[
                            styles.optionCard,
                            selectedIntegrations.includes('calendar') && styles.optionSelected
                        ]}
                        onPress={() => toggleIntegration('calendar')}
                    >
                        <View style={styles.optionIcon}>
                            <Ionicons name="calendar" size={24} color="#4285F4" />
                        </View>
                        <View style={styles.optionContent}>
                            <DonnaText style={styles.optionTitle}>Google Calendar</DonnaText>
                            <DonnaText style={styles.optionDesc}>For smart scheduling & briefings</DonnaText>
                        </View>
                        <Ionicons
                            name={selectedIntegrations.includes('calendar') ? "checkmark-circle" : "ellipse-outline"}
                            size={24}
                            color={selectedIntegrations.includes('calendar') ? Colors.accentPrimary : Colors.textMuted}
                        />
                    </TouchableOpacity>
                </View>
            </ScrollView >

            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.activateButton, activationMutation.isPending && styles.buttonDisabled]}
                    onPress={handleActivate}
                    disabled={activationMutation.isPending}
                >
                    {activationMutation.isPending ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <>
                            <DonnaText style={styles.activateButtonText}>Start Syncing</DonnaText>
                            <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
                        </>
                    )}
                </TouchableOpacity>
                <DonnaText style={styles.footerNote}>
                    No credit card required for trial.
                </DonnaText>
            </View>
        </View >
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
        paddingTop: 60,
        paddingHorizontal: Spacing.md,
        paddingBottom: Spacing.md,
    },
    backButton: {
        padding: Spacing.sm,
        marginRight: Spacing.sm,
        marginLeft: -Spacing.sm,
    },
    content: {
        padding: Spacing.md,
    },
    hero: {
        alignItems: 'center',
        marginBottom: Spacing.xl,
        paddingVertical: Spacing.lg,
    },
    iconCircle: {
        width: 64,
        height: 64,
        borderRadius: Radius.full,
        backgroundColor: '#F3E6E6', // Light Auburn
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: Spacing.md,
    },
    heroTitle: {
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    heroText: {
        textAlign: 'center',
        color: Colors.textSecondary,
        fontSize: 16,
        lineHeight: 24,
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionTitle: {
        marginBottom: Spacing.md,
    },
    optionCard: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: Colors.bgSurface,
        padding: Spacing.md,
        borderRadius: Radius.lg,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    optionSelected: {
        borderColor: Colors.accentPrimary,
        backgroundColor: '#FDFBFB',
    },
    optionIcon: {
        marginRight: Spacing.md,
    },
    optionContent: {
        flex: 1,
    },
    optionTitle: {
        fontWeight: '600',
        fontSize: 16,
        marginBottom: 2,
    },
    optionDesc: {
        fontSize: 13,
        color: Colors.textMuted,
    },
    footer: {
        padding: Spacing.md,
        paddingBottom: 40,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        backgroundColor: Colors.bgSurface,
    },
    activateButton: {
        backgroundColor: Colors.accentPrimary,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        paddingVertical: Spacing.md,
        borderRadius: Radius.full,
        gap: Spacing.sm,
        marginBottom: Spacing.sm,
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 4,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    activateButtonText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '600',
    },
    footerNote: {
        textAlign: 'center',
        fontSize: 12,
        color: Colors.textMuted,
    },
    nameInputContainer: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm + 2,
        marginBottom: Spacing.xs,
    },
    nameInput: {
        fontSize: 16,
        color: Colors.textPrimary,
        fontWeight: '500',
    },
    nameHint: {
        fontSize: 12,
        color: Colors.textMuted,
        marginLeft: Spacing.xs,
    },
});
