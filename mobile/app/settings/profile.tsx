import React from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity, Switch, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '@/src/context/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { fetchSubscription, SubscriptionData } from '@/src/services/billing';

interface SettingRowProps {
    icon: string;
    iconColor?: string;
    title: string;
    subtitle?: string;
    onPress?: () => void;
    showArrow?: boolean;
    rightElement?: React.ReactNode;
    destructive?: boolean;
}

const SettingRow: React.FC<SettingRowProps> = ({
    icon,
    iconColor = Colors.textSecondary,
    title,
    subtitle,
    onPress,
    showArrow = true,
    rightElement,
    destructive,
}) => (
    <TouchableOpacity style={styles.settingRow} onPress={onPress} disabled={!onPress}>
        <View style={[styles.iconContainer, { backgroundColor: iconColor + '15' }]}>
            <Ionicons name={icon as any} size={20} color={iconColor} />
        </View>
        <View style={styles.settingTextContainer}>
            <DonnaText style={[styles.settingTitle, destructive && { color: Colors.error }]}>
                {title}
            </DonnaText>
            {subtitle && <DonnaText style={styles.settingSubtitle}>{subtitle}</DonnaText>}
        </View>
        {rightElement}
        {showArrow && !rightElement && (
            <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
        )}
    </TouchableOpacity>
);

export default function ProfileScreen() {
    const router = useRouter();
    const { user, signOut } = useAuth();

    // Fetch subscription with TanStack Query
    const { data: subscription } = useQuery({
        queryKey: ['subscription'],
        queryFn: fetchSubscription,
    });

    // Get display name from Supabase user_metadata (populated by Google OAuth)
    const displayName = user?.user_metadata?.full_name || user?.user_metadata?.name;
    const displayEmail = user?.email;
    const initial = displayName?.[0]?.toUpperCase() || 'J';

    // Generate subscription subtitle from real data
    const getSubscriptionSubtitle = () => {
        if (!subscription) return 'Loading...';
        if (subscription.tier === 'pro' && subscription.status === 'active') {
            return 'Active subscription';
        }
        if (subscription.days_remaining > 0) {
            return `${subscription.days_remaining} days left in trial`;
        }
        return 'Trial expired';
    };

    const handleLogout = async () => {
        Alert.alert(
            'Sign Out',
            'Are you sure you want to sign out?',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Sign Out', style: 'destructive', onPress: async () => {
                        await signOut();
                        router.replace('/login');
                    }
                },
            ]
        );
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.closeButton}>
                    <Ionicons name="close" size={28} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Settings</DonnaText>
                <View style={styles.placeholder} />
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Profile Card */}
                <View style={styles.profileCard}>
                    <View style={styles.avatar}>
                        <DonnaText style={styles.avatarText}>
                            {initial}
                        </DonnaText>
                    </View>
                    <View style={styles.profileInfo}>
                        <DonnaText variant="h2" style={styles.profileName}>
                            {displayName}
                        </DonnaText>
                        <DonnaText style={styles.profileEmail}>
                            {displayEmail}
                        </DonnaText>
                    </View>
                    <TouchableOpacity style={styles.editButton}>
                        <Ionicons name="pencil" size={16} color={Colors.accentSecondary} />
                    </TouchableOpacity>
                </View>

                {/* Subscription Banner */}
                <TouchableOpacity
                    style={styles.subscriptionBanner}
                    onPress={() => router.push('/settings/subscription' as any)}
                >
                    <View style={styles.subscriptionIcon}>
                        <Ionicons name="diamond" size={20} color={Colors.accentSecondary} />
                    </View>
                    <View style={styles.subscriptionInfo}>
                        <DonnaText style={styles.subscriptionTitle}>Corta Pro</DonnaText>
                        <DonnaText style={styles.subscriptionSubtitle}>{getSubscriptionSubtitle()}</DonnaText>
                    </View>
                    <DonnaText style={styles.upgradeText}>
                        {subscription?.tier === 'pro' && subscription?.status === 'active' ? 'Manage →' : 'Upgrade →'}
                    </DonnaText>
                </TouchableOpacity>

                {/* General Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>GENERAL</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="notifications-outline"
                            iconColor={Colors.accentSecondary}
                            title="Notifications"
                            subtitle="Push & email preferences"
                            onPress={() => Alert.alert('Coming Soon', 'Notification settings')}
                        />
                        <SettingRow
                            icon="moon-outline"
                            iconColor={Colors.accentPrecision}
                            title="Appearance"
                            subtitle="Theme & display options"
                            onPress={() => Alert.alert('Coming Soon', 'Appearance settings')}
                        />
                    </View>
                </View>

                {/* AI & Automation Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>AI & AUTOMATION</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="sparkles-outline"
                            iconColor={Colors.accentSecondary}
                            title="Task Detection"
                            subtitle="How Donna extracts tasks"
                            onPress={() => Alert.alert('Coming Soon', 'Task detection settings')}
                        />
                        <SettingRow
                            icon="checkmark-done-outline"
                            iconColor={Colors.success}
                            title="Auto-Approve Tasks"
                            showArrow={false}
                            rightElement={
                                <Switch
                                    value={false}
                                    trackColor={{ true: Colors.success }}
                                    thumbColor="#FFF"
                                />
                            }
                        />
                        <SettingRow
                            icon="brain-outline"
                            iconColor="#9B59B6"
                            title="Memory & Preferences"
                            subtitle="What Donna remembers"
                            onPress={() => Alert.alert('Coming Soon', 'Memory settings')}
                        />
                    </View>
                </View>

                {/* Calendar Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>CALENDAR</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="calendar-outline"
                            iconColor={Colors.accentPrecision}
                            title="Calendar Settings"
                            subtitle="Working hours, buffers, timezone"
                            onPress={() => Alert.alert('Coming Soon', 'Calendar settings')}
                        />
                        <SettingRow
                            icon="mail-outline"
                            iconColor={Colors.accentSecondary}
                            title="Digests"
                            subtitle="Morning briefing & summaries"
                            onPress={() => router.push('/settings/digests' as any)}
                        />
                    </View>
                </View>

                {/* Data & Privacy Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>DATA & PRIVACY</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="shield-checkmark-outline"
                            iconColor={Colors.accentPrecision}
                            title="Data & Privacy"
                            subtitle="Export, revoke access, delete data"
                            onPress={() => router.push('/settings/privacy' as any)}
                        />
                    </View>
                </View>

                {/* Sign Out Button */}
                <TouchableOpacity style={styles.signOutButton} onPress={handleLogout}>
                    <Ionicons name="log-out-outline" size={20} color={Colors.error} />
                    <DonnaText style={styles.signOutText}>Sign Out</DonnaText>
                </TouchableOpacity>

                {/* App Version */}
                <DonnaText style={styles.versionText}>Corta v1.0.0 (Build 42)</DonnaText>
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
    closeButton: {
        padding: Spacing.xs,
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    placeholder: {
        width: 44,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 60,
    },
    profileCard: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        marginBottom: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    avatar: {
        width: 56,
        height: 56,
        borderRadius: 28,
        backgroundColor: Colors.accentPrecision,
        justifyContent: 'center',
        alignItems: 'center',
    },
    avatarText: {
        color: '#FFF',
        fontSize: 22,
        fontWeight: '600',
    },
    profileInfo: {
        flex: 1,
    },
    profileName: {
        marginBottom: 2,
    },
    profileEmail: {
        fontSize: 14,
        color: Colors.textMuted,
    },
    editButton: {
        width: 36,
        height: 36,
        borderRadius: 18,
        backgroundColor: 'rgba(217, 119, 69, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    subscriptionBanner: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        backgroundColor: 'rgba(217, 119, 69, 0.08)',
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
        marginBottom: Spacing.xl,
    },
    subscriptionIcon: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: 'rgba(217, 119, 69, 0.15)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    subscriptionInfo: {
        flex: 1,
    },
    subscriptionTitle: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    subscriptionSubtitle: {
        fontSize: 13,
        color: Colors.accentSecondary,
    },
    upgradeText: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.accentSecondary,
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
        marginLeft: Spacing.xs,
    },
    sectionCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: Colors.border,
    },
    settingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    iconContainer: {
        width: 36,
        height: 36,
        borderRadius: 10,
        justifyContent: 'center',
        alignItems: 'center',
    },
    settingTextContainer: {
        flex: 1,
    },
    settingTitle: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    settingSubtitle: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 1,
    },
    signOutButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        paddingVertical: Spacing.md,
        marginTop: Spacing.md,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.error,
    },
    signOutText: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.error,
    },
    versionText: {
        textAlign: 'center',
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: Spacing.xl,
    },
});
