import React, { useState, useMemo } from 'react';
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
import * as WebBrowser from 'expo-web-browser';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { activateTrial, createCheckout } from '../../src/services/billing';
import { api } from '../../src/services/api';

type PlanType = 'trial' | 'pro';

export default function SubscriptionSelectionScreen() {
    const router = useRouter();
    const { refreshProfile, user } = useAuth();
    const [selectedPlan, setSelectedPlan] = useState<PlanType>('trial');
    const [isProcessing, setIsProcessing] = useState(false);

    // Extract first name from cached Supabase user metadata (zero latency)
    const firstName = useMemo(() => {
        const fullName = user?.user_metadata?.full_name || user?.user_metadata?.name || '';
        const first = fullName.split(' ')[0];
        return first || 'there';
    }, [user]);

    const handleContinue = async () => {
        console.log('[SUB] CTA pressed, selectedPlan:', selectedPlan);
        console.log('[SUB] API baseURL:', api.defaults.baseURL);
        setIsProcessing(true);
        try {
            if (selectedPlan === 'trial') {
                console.log('[SUB] Calling activateTrial...');
                await activateTrial();
                console.log('[SUB] Trial activated, triggering initial sync...');
                // Trigger email backfill now that subscription is active
                try {
                    const { triggerInitialSync } = require('../../src/services/billing');
                    await triggerInitialSync();
                    console.log('[SUB] Initial sync triggered successfully');
                } catch (syncError: any) {
                    // Non-fatal: sync can be retried from settings
                    console.warn('[SUB] Initial sync trigger failed:', syncError?.message);
                }
                console.log('[SUB] Refreshing profile...');
                await refreshProfile();
                console.log('[SUB] Profile refreshed, navigating to setup...');
                router.replace('/auth/setup' as any);
            } else {
                console.log('[SUB] Calling createCheckout...');
                const data = await createCheckout({
                    success_url: 'teeks://auth/setup',
                    cancel_url: 'teeks://auth/subscription',
                });
                console.log('[SUB] Checkout response:', data);
                if (data?.checkout_url) {
                    const result = await WebBrowser.openAuthSessionAsync(
                        data.checkout_url,
                        'teeks://'
                    );

                    if (result.type === 'success' && result.url?.includes('auth/setup')) {
                        await new Promise(resolve => setTimeout(resolve, 1500));
                        await refreshProfile();
                        router.replace('/auth/setup' as any);
                    }
                }
            }
        } catch (error: any) {
            console.error('[SUB] ERROR:', error.message);
            console.error('[SUB] Error response status:', error.response?.status);
            console.error('[SUB] Error response data:', JSON.stringify(error.response?.data));
            console.error('[SUB] Error code:', error.code);
            Alert.alert(
                'Error',
                error.response?.data?.detail || 'Something went wrong. Please try again.'
            );
        } finally {
            console.log('[SUB] Done, setIsProcessing(false)');
            setIsProcessing(false);
        }
    };

    const isLoading = isProcessing;

    const ctaText = selectedPlan === 'trial'
        ? 'Try this week with Teeks'
        : 'Try this month with Teeks';

    return (
        <SafeAreaView style={styles.safe}>
            <StatusBar style="dark" />
            <ScrollView
                style={styles.scroll}
                contentContainerStyle={styles.content}
                showsVerticalScrollIndicator={false}
            >
                {/* Header */}
                <View style={styles.header}>
                    <DonnaText style={styles.title}>
                        You don't have to carry alone
                    </DonnaText>
                    <DonnaText style={styles.subtitle}>
                        Try Teeks free, or keep it by your side every day
                    </DonnaText>
                </View>

                {/* Email Cards */}
                <View style={styles.inbox}>
                    {/* Free Trial Email */}
                    <TouchableOpacity
                        style={[
                            styles.emailCard,
                            selectedPlan === 'trial' && styles.emailCardSelected,
                        ]}
                        onPress={() => setSelectedPlan('trial')}
                        activeOpacity={0.85}
                    >
                        {/* Clip */}
                        <View style={styles.clip} />

                        {/* Subject */}
                        <View style={styles.emailHeader}>
                            <DonnaText style={styles.subjectLabel}>
                                Subject: <DonnaText style={styles.subjectText}>Teeks Free Trial</DonnaText>
                            </DonnaText>
                        </View>

                        {/* Body */}
                        <View style={styles.emailBody}>
                            <DonnaText style={styles.greeting}>
                                Dear <DonnaText style={styles.userName}>{firstName}</DonnaText>,
                            </DonnaText>
                            <DonnaText style={styles.bodyBold}>
                                Start free. See the difference in a week.
                            </DonnaText>
                            <DonnaText style={styles.bodyText}>
                                Full access to all pro features and 100 Teeks credits for reply drafting and chat for 5 days. No credit card required.
                            </DonnaText>
                        </View>

                        {/* Price — bottom right */}
                        <View style={styles.emailFooter}>
                            <View style={styles.priceTag}>
                                <DonnaText style={styles.currency}>$</DonnaText>
                                <DonnaText style={styles.amount}>0</DonnaText>
                                <DonnaText style={styles.period}>/ 5 days</DonnaText>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Pro Email */}
                    <TouchableOpacity
                        style={[
                            styles.emailCard,
                            styles.emailCardPro,
                            selectedPlan === 'pro' && styles.emailCardSelected,
                        ]}
                        onPress={() => setSelectedPlan('pro')}
                        activeOpacity={0.85}
                    >
                        {/* Copper Clip */}
                        <View style={[styles.clip, styles.clipCopper]} />

                        {/* Subject */}
                        <View style={styles.emailHeader}>
                            <DonnaText style={styles.subjectLabel}>
                                Subject: <DonnaText style={styles.subjectText}>Teeks Pro</DonnaText>
                            </DonnaText>
                        </View>

                        {/* Body */}
                        <View style={styles.emailBody}>
                            <DonnaText style={styles.greeting}>
                                Dear <DonnaText style={styles.userName}>{firstName}</DonnaText>,
                            </DonnaText>
                            <DonnaText style={styles.bodyBold}>
                                Work with clarity. Achieve more with an executive partner at your side.
                            </DonnaText>
                            <DonnaText style={styles.bodyText}>
                                Inbox intelligence, task management, AI-assisted replies in your voice, calendar assistance, and executive context memory — everything you need, always by your side.
                            </DonnaText>
                        </View>

                        {/* Price — bottom right */}
                        <View style={styles.emailFooter}>
                            <View style={styles.priceTag}>
                                <DonnaText style={styles.currency}>$</DonnaText>
                                <DonnaText style={styles.amount}>19</DonnaText>
                                <DonnaText style={styles.period}>/ month</DonnaText>
                            </View>
                        </View>
                    </TouchableOpacity>

                    {/* Founding note */}
                    <DonnaText style={styles.foundingNote}>
                        Founding members get full access, early features, and locked-in pricing
                    </DonnaText>
                </View>
            </ScrollView>

            {/* CTA */}
            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.cta, isLoading && styles.ctaDisabled]}
                    onPress={handleContinue}
                    disabled={isLoading}
                    activeOpacity={0.9}
                >
                    {isLoading ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <DonnaText style={styles.ctaText}>{ctaText}</DonnaText>
                    )}
                </TouchableOpacity>
            </View>
        </SafeAreaView>
    );
}

// ——— Styles ———
const WARM_BG = '#FFFDF9';
const CARD_BG = '#FFFFFF';
const CARD_LITE = '#FFFCF8';
const SOFT_SHADOW = 'rgba(126, 46, 46, 0.04)';

const styles = StyleSheet.create({
    safe: {
        flex: 1,
        backgroundColor: WARM_BG,
    },
    scroll: {
        flex: 1,
    },
    content: {
        padding: Spacing.lg,
        paddingTop: Spacing.xxl,
        paddingBottom: Spacing.xl,
    },

    // ── Header ──
    header: {
        alignItems: 'center',
        marginBottom: Spacing.xl + 8,
    },
    title: {
        fontFamily: 'PlayfairDisplay_700Bold',
        fontSize: 24,
        lineHeight: 30,
        letterSpacing: -0.5,
        color: Colors.accentPrimary,   // Auburn, not black
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    subtitle: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        color: Colors.textSecondary,
        textAlign: 'center',
        lineHeight: 22,
    },

    // ── Inbox stack ──
    inbox: {
        gap: 20,
    },

    // ── Email Card ──
    emailCard: {
        backgroundColor: CARD_LITE,
        borderRadius: Radius.md,
        borderWidth: 1,
        borderColor: 'rgba(5, 11, 20, 0.05)',
        overflow: 'visible',
        // Soft shadow
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.06,
        shadowRadius: 20,
        elevation: 3,
    },
    emailCardPro: {
        backgroundColor: CARD_BG,
    },
    emailCardSelected: {
        borderColor: Colors.accentSecondary,
        borderWidth: 2,
        shadowOpacity: 0.12,
        shadowRadius: 28,
        elevation: 6,
    },

    // ── Clip decoration ──
    clip: {
        position: 'absolute',
        top: -6,
        left: 28,
        width: 36,
        height: 10,
        borderRadius: 2,
        backgroundColor: Colors.borderStrong, // Silver
        zIndex: 10,
    },
    clipCopper: {
        backgroundColor: Colors.accentSecondary, // Copper
    },

    // ── Email Header (Subject) ──
    emailHeader: {
        paddingHorizontal: Spacing.lg,
        paddingTop: Spacing.md + 4,
        paddingBottom: Spacing.sm + 2,
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderBottomColor: 'rgba(0,0,0,0.06)',
        borderStyle: 'dashed',
    },
    subjectLabel: {
        fontFamily: 'Inter_400Regular',
        fontSize: 11,
        letterSpacing: 0.8,
        textTransform: 'uppercase',
        color: Colors.textMuted,
        opacity: 0.55,      // Faded subject line
    },
    subjectText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 11,
        letterSpacing: 0.8,
        textTransform: 'uppercase',
        color: Colors.textSecondary,
        fontWeight: '600',
    },

    // ── Email Body ──
    emailBody: {
        paddingHorizontal: Spacing.lg,
        paddingTop: Spacing.md,
        paddingBottom: Spacing.sm,
    },
    greeting: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        color: Colors.textPrimary,
        marginBottom: Spacing.sm + 2,
    },
    userName: {
        color: Colors.accentSecondary,
        fontWeight: '600',
    },
    bodyBold: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
        lineHeight: 22,
    },
    bodyText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 22,
    },

    // ── Email Footer (Price) ──
    emailFooter: {
        paddingHorizontal: Spacing.lg,
        paddingBottom: Spacing.md,
        alignItems: 'flex-end',
    },
    priceTag: {
        flexDirection: 'row',
        alignItems: 'baseline',
    },
    currency: {
        fontFamily: 'Inter_400Regular',
        fontSize: 11,
        color: Colors.textMuted,
        opacity: 0.6,
        marginRight: 1,
    },
    amount: {
        fontFamily: 'PlayfairDisplay_700Bold',
        fontSize: 22,
        color: Colors.accentPrimary,
    },
    period: {
        fontFamily: 'Inter_400Regular',
        fontSize: 12,
        color: Colors.textMuted,
        marginLeft: 3,
    },

    // ── Founding Note ──
    foundingNote: {
        fontFamily: 'Inter_400Regular',
        fontSize: 13,
        fontStyle: 'italic',
        color: Colors.textMuted,
        textAlign: 'center',
        lineHeight: 20,
    },

    // ── Footer CTA ──
    footer: {
        padding: Spacing.lg,
        paddingBottom: Spacing.xl,
        backgroundColor: WARM_BG,
    },
    cta: {
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.xs,
        paddingVertical: Spacing.md + 2,
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.25,
        shadowRadius: 12,
        elevation: 4,
    },
    ctaDisabled: {
        opacity: 0.6,
    },
    ctaText: {
        color: '#FFFFFF',
        fontSize: 17,
        fontWeight: '600',
        letterSpacing: 0.2,
    },
});
