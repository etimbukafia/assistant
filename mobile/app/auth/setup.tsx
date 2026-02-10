import React, { useState } from 'react';
import {
    View,
    StyleSheet,
    SafeAreaView,
    TouchableOpacity,
    ScrollView,
    TextInput,
    ActivityIndicator,
    Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { completeOnboarding } from '../../src/services/onboarding';
import { triggerInitialSync } from '../../src/services/billing';

export default function SetupScreen() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const { refreshProfile } = useAuth();
    const [assistantName, setAssistantName] = useState('Donna');
    const [selectedIntegrations, setSelectedIntegrations] = useState<string[]>([]);

    const toggleIntegration = (id: string) => {
        if (selectedIntegrations.includes(id)) {
            setSelectedIntegrations(prev => prev.filter(i => i !== id));
        } else {
            setSelectedIntegrations(prev => [...prev, id]);
        }
    };

    const setupMutation = useMutation({
        mutationFn: async () => {
            await completeOnboarding({ assistant_name: assistantName.trim() || 'Donna' });

            // Only trigger email sync if user chose to connect Gmail
            if (selectedIntegrations.includes('gmail')) {
                triggerInitialSync().catch(console.error);
            }
        },
        onSuccess: () => {
            // Navigate immediately - don't block on profile refresh
            router.replace('/(tabs)' as any);

            // Refresh profile in background (non-blocking)
            queryClient.invalidateQueries({ queryKey: ['settings'] });
            refreshProfile().catch(console.error);
        },
        onError: (error: any) => {
            console.error('Setup failed:', error);
            Alert.alert(
                'Setup Failed',
                error.response?.data?.detail || 'Something went wrong. Please try again.'
            );
        },
    });

    const handleComplete = () => {
        setupMutation.mutate();
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.content}
                showsVerticalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
            >
                {/* Header */}
                <View style={styles.header}>
                    <View style={styles.iconCircle}>
                        <Ionicons name="sparkles" size={32} color={Colors.accentPrimary} />
                    </View>
                    <DonnaText style={styles.title}>Set Up Your Assistant</DonnaText>
                    <DonnaText style={styles.subtitle}>
                        Personalize your experience and connect your accounts
                    </DonnaText>
                </View>

                {/* Assistant Name Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionTitle}>Name Your Assistant</DonnaText>
                    <View style={styles.inputContainer}>
                        <TextInput
                            style={styles.input}
                            value={assistantName}
                            onChangeText={setAssistantName}
                            placeholder="Donna"
                            placeholderTextColor={Colors.textMuted}
                            maxLength={50}
                            autoCapitalize="words"
                        />
                    </View>
                    <DonnaText style={styles.hint}>
                        This is what your AI assistant will be called throughout the app
                    </DonnaText>
                </View>

                {/* Integrations Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionTitle}>Connect Your Accounts</DonnaText>

                    {/* Gmail */}
                    <TouchableOpacity
                        style={[
                            styles.integrationCard,
                            selectedIntegrations.includes('gmail') && styles.integrationSelected,
                        ]}
                        onPress={() => toggleIntegration('gmail')}
                        activeOpacity={0.8}
                    >
                        <View style={[styles.integrationIcon, { backgroundColor: '#EA433510' }]}>
                            <Ionicons name="mail" size={24} color="#EA4335" />
                        </View>
                        <View style={styles.integrationContent}>
                            <View style={styles.integrationTitleRow}>
                                <DonnaText style={styles.integrationName}>Gmail</DonnaText>
                                <View style={styles.optionalBadge}>
                                    <DonnaText style={styles.optionalBadgeText}>Recommended</DonnaText>
                                </View>
                            </View>
                            <DonnaText style={styles.integrationDesc}>
                                Teeks will sync your recent emails to get started
                            </DonnaText>
                        </View>
                        <Ionicons
                            name={selectedIntegrations.includes('gmail') ? 'checkmark-circle' : 'ellipse-outline'}
                            size={24}
                            color={selectedIntegrations.includes('gmail') ? Colors.accentPrimary : Colors.textMuted}
                        />
                    </TouchableOpacity>

                    {/* Calendar (Optional) */}
                    <TouchableOpacity
                        style={[
                            styles.integrationCard,
                            selectedIntegrations.includes('calendar') && styles.integrationSelected,
                        ]}
                        onPress={() => toggleIntegration('calendar')}
                        activeOpacity={0.8}
                    >
                        <View style={[styles.integrationIcon, { backgroundColor: '#4285F410' }]}>
                            <Ionicons name="calendar" size={24} color="#4285F4" />
                        </View>
                        <View style={styles.integrationContent}>
                            <View style={styles.integrationTitleRow}>
                                <DonnaText style={styles.integrationName}>Google Calendar</DonnaText>
                                <View style={styles.optionalBadge}>
                                    <DonnaText style={styles.optionalBadgeText}>Optional</DonnaText>
                                </View>
                            </View>
                            <DonnaText style={styles.integrationDesc}>
                                Smart scheduling suggestions and daily briefings
                            </DonnaText>
                        </View>
                        <Ionicons
                            name={selectedIntegrations.includes('calendar') ? 'checkmark-circle' : 'ellipse-outline'}
                            size={24}
                            color={selectedIntegrations.includes('calendar') ? Colors.accentPrimary : Colors.textMuted}
                        />
                    </TouchableOpacity>
                </View>

                {/* Info Note */}
                <View style={styles.infoNote}>
                    <Ionicons name="shield-checkmark" size={20} color={Colors.accentSecondary} />
                    <DonnaText style={styles.infoNoteText}>
                        Your data is encrypted and processed securely. We never share your information.
                    </DonnaText>
                </View>
            </ScrollView>

            {/* Footer */}
            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.completeButton, setupMutation.isPending && styles.buttonDisabled]}
                    onPress={handleComplete}
                    disabled={setupMutation.isPending}
                    activeOpacity={0.9}
                >
                    {setupMutation.isPending ? (
                        <View style={styles.loadingContent}>
                            <ActivityIndicator color="#FFFFFF" size="small" />
                            <DonnaText style={styles.completeButtonText}>Setting up...</DonnaText>
                        </View>
                    ) : (
                        <>
                            <DonnaText style={styles.completeButtonText}>Complete Setup</DonnaText>
                            <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
                        </>
                    )}
                </TouchableOpacity>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.lg,
        paddingTop: Spacing.xl,
    },
    header: {
        alignItems: 'center',
        marginBottom: Spacing.xl,
    },
    iconCircle: {
        width: 72,
        height: 72,
        borderRadius: 36,
        backgroundColor: Colors.accentPrimary + '15',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: Spacing.md,
    },
    title: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 28,
        color: Colors.textPrimary,
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    subtitle: {
        fontSize: 16,
        color: Colors.textSecondary,
        textAlign: 'center',
        lineHeight: 24,
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionTitle: {
        fontSize: 13,
        fontWeight: '600',
        color: Colors.textMuted,
        textTransform: 'uppercase',
        letterSpacing: 1,
        marginBottom: Spacing.md,
    },
    inputContainer: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.md,
        marginBottom: Spacing.xs,
    },
    input: {
        fontSize: 18,
        color: Colors.textPrimary,
        fontWeight: '500',
    },
    hint: {
        fontSize: 13,
        color: Colors.textMuted,
        marginLeft: Spacing.xs,
    },
    integrationCard: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: Colors.bgSurface,
        padding: Spacing.md,
        borderRadius: Radius.lg,
        marginBottom: Spacing.sm,
        borderWidth: 2,
        borderColor: Colors.border,
    },
    integrationSelected: {
        borderColor: Colors.accentPrimary,
        backgroundColor: Colors.accentPrimary + '05',
    },
    integrationIcon: {
        width: 48,
        height: 48,
        borderRadius: Radius.md,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: Spacing.md,
    },
    integrationContent: {
        flex: 1,
    },
    integrationTitleRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        marginBottom: 2,
    },
    integrationName: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    integrationDesc: {
        fontSize: 13,
        color: Colors.textMuted,
        lineHeight: 18,
    },
    requiredBadge: {
        backgroundColor: Colors.accentPrimary + '20',
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: Radius.sm,
    },
    requiredBadgeText: {
        fontSize: 10,
        fontWeight: '600',
        color: Colors.accentPrimary,
        textTransform: 'uppercase',
    },
    optionalBadge: {
        backgroundColor: Colors.textMuted + '20',
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: Radius.sm,
    },
    optionalBadgeText: {
        fontSize: 10,
        fontWeight: '600',
        color: Colors.textMuted,
        textTransform: 'uppercase',
    },
    infoNote: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: Spacing.sm,
        backgroundColor: Colors.accentSecondary + '10',
        padding: Spacing.md,
        borderRadius: Radius.md,
    },
    infoNoteText: {
        flex: 1,
        fontSize: 13,
        color: Colors.textSecondary,
        lineHeight: 20,
    },
    footer: {
        padding: Spacing.lg,
        paddingBottom: Spacing.xl,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        backgroundColor: Colors.bgSurface,
    },
    completeButton: {
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.full,
        paddingVertical: Spacing.md + 2,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 4,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    loadingContent: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
    },
    completeButtonText: {
        color: '#FFFFFF',
        fontSize: 17,
        fontWeight: '600',
    },
});
