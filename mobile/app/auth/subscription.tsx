import React, { useState } from 'react';
import {
    View,
    StyleSheet,
    SafeAreaView,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
    Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { useMutation } from '@tanstack/react-query';
import { activateTrial, createCheckout, triggerInitialSync } from '../../src/services/billing';

const FEATURES = [
    'Inbox intelligence & summaries',
    'Task & follow-up detection',
    'AI-assisted draft replies',
    'Scheduling suggestions',
    'Executive context memory',
];

type PlanType = 'trial' | 'pro_monthly' | 'pro_yearly';

export default function SubscriptionSelectionScreen() {
    const router = useRouter();
    const { refreshProfile } = useAuth();
    const [selectedPlan, setSelectedPlan] = useState<PlanType>('trial');
    const [isProcessing, setIsProcessing] = useState(false);

    const trialMutation = useMutation({
        mutationFn: () => activateTrial(),
        onSuccess: async () => {
            // Start email sync immediately in background - don't wait for it
            // This runs while user fills out setup screen, saving ~10-30s perceived wait
            triggerInitialSync().catch(console.error);

            // Refresh profile and navigate (parallel operations)
            await refreshProfile();
            router.replace('/auth/setup' as any);
        },
        onError: (error: any) => {
            Alert.alert(
                'Activation Failed',
                error.response?.data?.detail || 'Something went wrong. Please try again.'
            );
        },
    });

    const handleContinue = async () => {
        setIsProcessing(true);

        try {
            if (selectedPlan === 'trial') {
                trialMutation.mutate();
            } else {
                // Pro plan - open checkout
                const data = await createCheckout({
                    success_url: 'teeks://auth/setup',
                    cancel_url: 'teeks://auth/subscription',
                });

                if (data?.checkout_url) {
                    await WebBrowser.openBrowserAsync(data.checkout_url);
                    // Start email sync immediately in background after successful checkout
                    triggerInitialSync().catch(console.error);
                    // After checkout, refresh profile and navigate
                    await refreshProfile();
                    router.replace('/auth/setup' as any);
                }
            }
        } catch (error: any) {
            Alert.alert(
                'Error',
                error.response?.data?.detail || 'Something went wrong. Please try again.'
            );
        } finally {
            setIsProcessing(false);
        }
    };

    const isLoading = isProcessing || trialMutation.isPending;

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.content}
                showsVerticalScrollIndicator={false}
            >
                {/* Header */}
                <View style={styles.header}>
                    <DonnaText style={styles.title}>Choose Your Plan</DonnaText>
                    <DonnaText style={styles.subtitle}>
                        Start with a free trial or go Pro right away
                    </DonnaText>
                </View>

                {/* Plan Options */}
                <View style={styles.plansContainer}>
                    {/* Free Trial */}
                    <TouchableOpacity
                        style={[
                            styles.planCard,
                            selectedPlan === 'trial' && styles.planCardSelected,
                        ]}
                        onPress={() => setSelectedPlan('trial')}
                        activeOpacity={0.8}
                    >
                        <View style={styles.planHeader}>
                            <View style={styles.planTitleRow}>
                                <DonnaText style={styles.planName}>Free Trial</DonnaText>
                                {selectedPlan === 'trial' && (
                                    <Ionicons name="checkmark-circle" size={24} color={Colors.accentPrimary} />
                                )}
                            </View>
                            <DonnaText style={styles.planPrice}>
                                $0 <DonnaText style={styles.planPeriod}>for 7 days</DonnaText>
                            </DonnaText>
                        </View>
                        <DonnaText style={styles.planDescription}>
                            Full access to all features. No credit card required.
                        </DonnaText>
                    </TouchableOpacity>

                    {/* Pro Monthly */}
                    <TouchableOpacity
                        style={[
                            styles.planCard,
                            selectedPlan === 'pro_monthly' && styles.planCardSelected,
                        ]}
                        onPress={() => setSelectedPlan('pro_monthly')}
                        activeOpacity={0.8}
                    >
                        <View style={styles.planHeader}>
                            <View style={styles.planTitleRow}>
                                <DonnaText style={styles.planName}>Pro Monthly</DonnaText>
                                {selectedPlan === 'pro_monthly' && (
                                    <Ionicons name="checkmark-circle" size={24} color={Colors.accentPrimary} />
                                )}
                            </View>
                            <DonnaText style={styles.planPrice}>
                                $9.99 <DonnaText style={styles.planPeriod}>/ month</DonnaText>
                            </DonnaText>
                        </View>
                        <DonnaText style={styles.planDescription}>
                            Billed monthly. Cancel anytime.
                        </DonnaText>
                    </TouchableOpacity>

                    {/* Pro Yearly */}
                    <TouchableOpacity
                        style={[
                            styles.planCard,
                            selectedPlan === 'pro_yearly' && styles.planCardSelected,
                        ]}
                        onPress={() => setSelectedPlan('pro_yearly')}
                        activeOpacity={0.8}
                    >
                        <View style={styles.saveBadge}>
                            <DonnaText style={styles.saveBadgeText}>Save 17%</DonnaText>
                        </View>
                        <View style={styles.planHeader}>
                            <View style={styles.planTitleRow}>
                                <DonnaText style={styles.planName}>Pro Yearly</DonnaText>
                                {selectedPlan === 'pro_yearly' && (
                                    <Ionicons name="checkmark-circle" size={24} color={Colors.accentPrimary} />
                                )}
                            </View>
                            <DonnaText style={styles.planPrice}>
                                $99.99 <DonnaText style={styles.planPeriod}>/ year</DonnaText>
                            </DonnaText>
                        </View>
                        <DonnaText style={styles.planDescription}>
                            Best value. 2 months free.
                        </DonnaText>
                    </TouchableOpacity>
                </View>

                {/* Features List */}
                <View style={styles.featuresSection}>
                    <DonnaText style={styles.featuresTitle}>All plans include:</DonnaText>
                    <View style={styles.featuresList}>
                        {FEATURES.map((feature, index) => (
                            <View key={index} style={styles.featureRow}>
                                <Ionicons name="checkmark" size={18} color={Colors.accentSecondary} />
                                <DonnaText style={styles.featureText}>{feature}</DonnaText>
                            </View>
                        ))}
                    </View>
                </View>
            </ScrollView>

            {/* Footer CTA */}
            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.continueButton, isLoading && styles.buttonDisabled]}
                    onPress={handleContinue}
                    disabled={isLoading}
                    activeOpacity={0.9}
                >
                    {isLoading ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <DonnaText style={styles.continueButtonText}>
                            {selectedPlan === 'trial' ? 'Start Free Trial' : 'Continue to Checkout'}
                        </DonnaText>
                    )}
                </TouchableOpacity>
                {selectedPlan !== 'trial' && (
                    <DonnaText style={styles.footerNote}>
                        You'll be redirected to secure checkout
                    </DonnaText>
                )}
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
        marginBottom: Spacing.xl,
    },
    title: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 32,
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    subtitle: {
        fontSize: 16,
        color: Colors.textSecondary,
        lineHeight: 24,
    },
    plansContainer: {
        gap: Spacing.md,
        marginBottom: Spacing.xl,
    },
    planCard: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.lg,
        padding: Spacing.lg,
        borderWidth: 2,
        borderColor: Colors.border,
    },
    planCardSelected: {
        borderColor: Colors.accentPrimary,
        backgroundColor: Colors.accentPrimary + '08',
    },
    planHeader: {
        marginBottom: Spacing.xs,
    },
    planTitleRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 4,
    },
    planName: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 20,
        color: Colors.textPrimary,
    },
    planPrice: {
        fontSize: 24,
        fontWeight: '700',
        color: Colors.textPrimary,
    },
    planPeriod: {
        fontSize: 14,
        fontWeight: '400',
        color: Colors.textMuted,
    },
    planDescription: {
        fontSize: 14,
        color: Colors.textSecondary,
    },
    saveBadge: {
        position: 'absolute',
        top: -10,
        right: Spacing.md,
        backgroundColor: Colors.accentSecondary,
        paddingHorizontal: Spacing.sm,
        paddingVertical: 4,
        borderRadius: Radius.full,
    },
    saveBadgeText: {
        color: '#FFFFFF',
        fontSize: 12,
        fontWeight: '700',
    },
    featuresSection: {
        marginBottom: Spacing.lg,
    },
    featuresTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.md,
        textTransform: 'uppercase',
        letterSpacing: 1,
    },
    featuresList: {
        gap: 12,
    },
    featureRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
    },
    featureText: {
        fontSize: 15,
        color: Colors.textPrimary,
    },
    footer: {
        padding: Spacing.lg,
        paddingBottom: Spacing.xl,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        backgroundColor: Colors.bgSurface,
    },
    continueButton: {
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.full,
        paddingVertical: Spacing.md + 2,
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 4,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    continueButtonText: {
        color: '#FFFFFF',
        fontSize: 17,
        fontWeight: '600',
    },
    footerNote: {
        textAlign: 'center',
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: Spacing.sm,
    },
});
