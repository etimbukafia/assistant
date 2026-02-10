import React from 'react';
import { View, StyleSheet, TouchableOpacity, ScrollView, Alert, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import * as WebBrowser from 'expo-web-browser';
import { useSettings } from '../../src/hooks/useSettings';
import { useBillingActions } from '../../src/hooks/useSubscription';

const FEATURES = [
    'Inbox intelligence',
    'Task & follow-up detection',
    'Scheduling suggestions',
    'AI-assisted drafts',
    'Executive context memory',
    'Secure processing',
];

export default function SubscriptionScreen() {
    const router = useRouter();

    // Fetch settings (includes subscription data)
    const { settings, isLoading, error, refetch } = useSettings();
    const [isRefetching, setIsRefetching] = React.useState(false);

    // Billing actions
    const { createCheckoutAsync, getPortalUrlAsync, isCreatingCheckout, isGettingPortalUrl } = useBillingActions();

    const handleRefresh = async () => {
        setIsRefetching(true);
        await refetch();
        setIsRefetching(false);
    };

    const handleCheckout = async () => {
        try {
            const data = await createCheckoutAsync({
                success_url: 'teeks://billing/success',
                cancel_url: 'teeks://billing/cancel',
            });
            if (data?.checkout_url) {
                // Use openAuthSessionAsync to intercept redirects and avoid double navigation
                const result = await WebBrowser.openAuthSessionAsync(
                    data.checkout_url,
                    'teeks://'
                );

                // Only refresh if checkout completed successfully
                if (result.type === 'success' && result.url?.includes('billing/success')) {
                    // Give webhook a moment to process
                    await new Promise(resolve => setTimeout(resolve, 1500));
                }
                // Always refetch to get latest status (success or not)
                refetch();
            }
        } catch (err: any) {
            Alert.alert('Error', err.response?.data?.detail || 'Failed to create checkout. Please try again.');
        }
    };

    const handlePortal = async () => {
        try {
            const data = await getPortalUrlAsync();
            if (data?.portal_url) {
                await WebBrowser.openBrowserAsync(data.portal_url);
            }
        } catch (err: any) {
            Alert.alert('Error', err.response?.data?.detail || 'Failed to open portal. Please try again.');
        }
    };

    const isCheckoutLoading = isCreatingCheckout || isGettingPortalUrl;

    const handleUpgrade = () => {
        Alert.alert(
            'Secure Checkout',
            "You'll be redirected to our secure checkout.",
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Continue',
                    onPress: handleCheckout,
                }
            ]
        );
    };

    const handleManageSubscription = () => {
        handlePortal();
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
    };

    // Derive UI states from backend data
    const isTrial = settings?.subscription_tier === 'trial';
    const isPro = settings?.subscription_tier === 'pro';
    const isActive = settings?.is_active ?? false;
    const isExpired = settings?.subscription_status === 'expired';
    const isGracePeriod = settings?.subscription_status === 'past_due';
    const isCanceled = settings?.subscription_status === 'canceled';

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentPrimary} />
                    <DonnaText style={styles.loadingText}>Loading subscription...</DonnaText>
                </View>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.closeButton}>
                    <Ionicons name="close" size={28} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Subscription</DonnaText>
                <View style={styles.placeholder} />
            </View>

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.content}
                refreshControl={
                    <RefreshControl
                        refreshing={isRefetching}
                        onRefresh={handleRefresh}
                        tintColor={Colors.accentPrimary}
                    />
                }
            >

                {/* Hero / Header Text */}
                <View style={styles.heroSection}>
                    <DonnaText style={styles.heroTitle}>Unlock{'\n'}Intelligence</DonnaText>
                </View>

                {/* Error State */}
                {error && (
                    <View style={styles.errorCard}>
                        <Ionicons name="warning-outline" size={20} color={Colors.error} />
                        <DonnaText style={styles.errorText}>Failed to load subscription status</DonnaText>
                        <TouchableOpacity onPress={() => refetch()}>
                            <DonnaText style={styles.retryText}>Retry</DonnaText>
                        </TouchableOpacity>
                    </View>
                )}

                {/* Status Card */}
                {settings && (
                    <View style={[styles.statusCard, isExpired && styles.statusCardExpired]}>
                        <View style={styles.statusHeader}>
                            <DonnaText style={styles.statusTitle}>
                                {isTrial ? 'Teeks Pro — Free Trial' :
                                    isGracePeriod ? 'Teeks Pro — Grace Period' :
                                        isExpired ? 'Your access is paused' :
                                            isCanceled ? 'Teeks Pro — Canceled' :
                                                'Teeks Pro — Active'}
                            </DonnaText>
                            <View style={[styles.statusBadge, {
                                backgroundColor: isActive ? Colors.success :
                                    isGracePeriod ? Colors.accentSecondary :
                                        Colors.textMuted
                            }]}>
                                <DonnaText style={styles.statusBadgeText}>
                                    {isActive ? 'Full Access' : isGracePeriod ? 'Limited' : 'Read-Only'}
                                </DonnaText>
                            </View>
                        </View>

                        <DonnaText style={styles.statusDescription}>
                            {isTrial && isActive ? `You're currently using Teeks with full access.\nYour free trial ends on ${formatDate(settings?.trial_ends_at)}.` :
                                isGracePeriod ? 'Your trial has ended, but Teeks is still available.\nAdd a payment method within 3 days to continue uninterrupted.' :
                                    isExpired ? 'Teeks is currently in read-only mode.\nResume your subscription to continue inbox processing and suggestions.' :
                                        isCanceled ? 'Your subscription is canceled but you still have access for the remaining period.' :
                                            isPro && isActive ? 'You have full access to all Teeks Pro features.' :
                                                'Checking your subscription status...'}
                        </DonnaText>

                        {isTrial && isActive && (
                            <DonnaText style={styles.statusSubtext}>
                                No payment is required until your trial ends.
                            </DonnaText>
                        )}

                        {settings?.days_remaining > 0 && (
                            <View style={styles.daysRemainingBadge}>
                                <DonnaText style={styles.daysRemainingText}>
                                    {settings?.days_remaining} days remaining
                                </DonnaText>
                            </View>
                        )}
                    </View>
                )}

                {/* Plan Selection (Only show if not active Pro or needs upgrade) */}
                {(!isPro || isGracePeriod || isExpired || isCanceled) && (
                    <View style={styles.planSection}>
                        <View style={styles.planCard}>
                            <View style={styles.planHeader}>
                                <View>
                                    <DonnaText style={styles.planName}>Teeks Pro</DonnaText>
                                    <DonnaText style={styles.planPrice}>
                                        $9.99 <DonnaText style={styles.planPeriod}>/ month</DonnaText>
                                    </DonnaText>
                                </View>
                            </View>

                            <View style={styles.divider} />

                            <DonnaText style={styles.featuresLabel}>Includes:</DonnaText>
                            <View style={styles.featuresList}>
                                {FEATURES.map((feature, index) => (
                                    <View key={index} style={styles.featureRow}>
                                        <Ionicons name="checkmark-sharp" size={18} color={Colors.accentSecondary} />
                                        <DonnaText style={styles.featureText}>{feature}</DonnaText>
                                    </View>
                                ))}
                            </View>

                            <DonnaText style={styles.planSubtext}>
                                Built for professional assistants managing real responsibility.
                            </DonnaText>
                        </View>

                        <TouchableOpacity
                            style={[styles.upgradeButton, isCheckoutLoading && styles.buttonDisabled]}
                            onPress={handleUpgrade}
                            activeOpacity={0.9}
                            disabled={isCheckoutLoading}
                        >
                            {isCheckoutLoading ? (
                                <ActivityIndicator size="small" color="#FFFFFF" />
                            ) : (
                                <DonnaText style={styles.upgradeButtonText}>
                                    {isExpired ? 'Resume Teeks Pro' : 'Continue with Teeks Pro'}
                                </DonnaText>
                            )}
                        </TouchableOpacity>
                        <DonnaText style={styles.redirectText}>You'll be redirected to our secure checkout.</DonnaText>
                    </View>
                )}

                {/* Manage Subscription (Only if Pro and active) */}
                {isPro && isActive && !isCanceled && (
                    <View style={styles.manageSection}>
                        <TouchableOpacity
                            style={[styles.manageButton, isCheckoutLoading && styles.buttonDisabled]}
                            onPress={handleManageSubscription}
                            disabled={isCheckoutLoading}
                        >
                            {isCheckoutLoading ? (
                                <ActivityIndicator size="small" color={Colors.textPrimary} />
                            ) : (
                                <DonnaText style={styles.manageButtonText}>Manage Subscription</DonnaText>
                            )}
                        </TouchableOpacity>
                        <DonnaText style={styles.manageSubtext}>Update payment method, view invoices, or cancel anytime.</DonnaText>
                    </View>
                )}

                {/* Support Link */}
                <TouchableOpacity style={styles.supportLink}>
                    <DonnaText style={styles.supportLinkText}>Contact Support</DonnaText>
                </TouchableOpacity>

                <View style={{ height: Spacing.xxl }} />
            </ScrollView>
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
        gap: Spacing.md,
    },
    loadingText: {
        color: Colors.textMuted,
        fontSize: 14,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.lg,
        paddingTop: Spacing.md,
        paddingBottom: Spacing.sm,
    },
    closeButton: {
        padding: Spacing.xs,
    },
    headerTitle: {
        fontFamily: 'Inter_500Medium',
        fontSize: 16,
        color: Colors.textPrimary,
    },
    placeholder: {
        width: 40,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        paddingHorizontal: Spacing.lg,
        paddingBottom: Spacing.xxl,
    },
    heroSection: {
        marginVertical: Spacing.xl,
        alignItems: 'center',
    },
    heroTitle: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 36,
        lineHeight: 44,
        color: Colors.textPrimary,
        textAlign: 'center',
    },
    errorCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        backgroundColor: Colors.error + '10',
        padding: Spacing.md,
        borderRadius: Radius.md,
        marginBottom: Spacing.lg,
    },
    errorText: {
        flex: 1,
        color: Colors.error,
        fontSize: 14,
    },
    retryText: {
        color: Colors.accentPrimary,
        fontWeight: '600',
    },
    statusCard: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.lg,
        padding: Spacing.lg,
        marginBottom: Spacing.xl,
        borderLeftWidth: 4,
        borderLeftColor: Colors.success,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 8,
        elevation: 2,
    },
    statusCardExpired: {
        borderLeftColor: Colors.textMuted,
    },
    statusHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: Spacing.sm,
    },
    statusTitle: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 18,
        color: Colors.textPrimary,
        flex: 1,
        marginRight: Spacing.sm,
    },
    statusBadge: {
        paddingHorizontal: Spacing.sm,
        paddingVertical: 2,
        borderRadius: Radius.full,
    },
    statusBadgeText: {
        color: '#FFF',
        fontSize: 11,
        fontWeight: 'bold',
        textTransform: 'uppercase',
    },
    statusDescription: {
        fontSize: 15,
        color: Colors.textSecondary,
        lineHeight: 22,
        marginBottom: Spacing.sm,
    },
    statusSubtext: {
        fontSize: 13,
        color: Colors.textMuted,
        fontStyle: 'italic',
    },
    daysRemainingBadge: {
        alignSelf: 'flex-start',
        backgroundColor: Colors.accentSecondary + '20',
        paddingHorizontal: Spacing.sm,
        paddingVertical: 4,
        borderRadius: Radius.full,
        marginTop: Spacing.sm,
    },
    daysRemainingText: {
        color: Colors.accentSecondary,
        fontSize: 12,
        fontWeight: '600',
    },
    planSection: {
        gap: Spacing.md,
    },
    planCard: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.surface,
        padding: Spacing.xl,
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
        shadowColor: Colors.accentSecondary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 12,
        elevation: 4,
    },
    planHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: Spacing.lg,
    },
    planName: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 24,
        color: Colors.textPrimary,
        marginBottom: 4,
    },
    planPrice: {
        fontFamily: 'Inter_600SemiBold',
        fontSize: 20,
        color: Colors.textPrimary,
    },
    planPeriod: {
        fontSize: 14,
        color: Colors.textMuted,
        fontWeight: 'normal',
    },
    divider: {
        height: 1,
        backgroundColor: Colors.border,
        marginBottom: Spacing.md,
    },
    featuresLabel: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.sm,
    },
    featuresList: {
        gap: 10,
        marginBottom: Spacing.lg,
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
    planSubtext: {
        fontSize: 13,
        color: Colors.textMuted,
        textAlign: 'center',
        marginTop: Spacing.sm,
    },
    upgradeButton: {
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.full,
        paddingVertical: 16,
        alignItems: 'center',
        marginTop: Spacing.sm,
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 4,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    upgradeButtonText: {
        color: '#FFFFFF',
        fontSize: 17,
        fontWeight: '600',
        fontFamily: 'Inter_600SemiBold',
    },
    redirectText: {
        fontSize: 13,
        color: Colors.textMuted,
        textAlign: 'center',
        marginTop: 4,
    },
    manageSection: {
        alignItems: 'center',
        marginTop: Spacing.lg,
    },
    manageButton: {
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.full,
        paddingVertical: 12,
        paddingHorizontal: 24,
        backgroundColor: Colors.bgSurface,
    },
    manageButtonText: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    manageSubtext: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: Spacing.sm,
        textAlign: 'center',
    },
    supportLink: {
        alignItems: 'center',
        marginTop: Spacing.xl,
    },
    supportLinkText: {
        fontSize: 15,
        color: Colors.textSecondary,
        textDecorationLine: 'underline',
    },
});
