import React from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { SettingRow } from '@/src/components/ui/SettingRow';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '@/src/context/AuthContext';

export default function SettingsHubScreen() {
    const router = useRouter();
    const { user, signOut, subscriptionTier, isActive, daysRemaining } = useAuth();

    const displayName = user?.user_metadata?.full_name || user?.user_metadata?.name;
    const initial = displayName?.[0]?.toUpperCase() || 'J';

    const getSubscriptionSubtitle = () => {
        if (subscriptionTier === 'pro' && isActive) {
            return 'Active subscription';
        }
        if (daysRemaining > 0) {
            return `${daysRemaining} days left in trial`;
        }
        return 'Trial expired';
    };

    const handleLogout = async () => {
        const doSignOut = async () => {
            try {
                await signOut();
            } catch (error) {
                console.error('Sign out error:', error);
            }
            router.replace('/login');
        };

        // Alert.alert doesn't work on web, use confirm() instead
        if (Platform.OS === 'web') {
            const confirmed = window.confirm('Are you sure you want to sign out?');
            if (confirmed) {
                await doSignOut();
            }
        } else {
            Alert.alert(
                'Sign Out',
                'Are you sure you want to sign out?',
                [
                    { text: 'Cancel', style: 'cancel' },
                    { text: 'Sign Out', style: 'destructive', onPress: doSignOut },
                ]
            );
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            <View style={styles.header}>
                <DonnaText style={styles.headerTitle}>Settings</DonnaText>
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Profile Section */}
                <TouchableOpacity
                    style={styles.profileCard}
                    onPress={() => router.push('/settings/profile' as any)}
                >
                    <View style={styles.avatar}>
                        <DonnaText style={styles.avatarText}>{initial}</DonnaText>
                    </View>
                    <View style={styles.profileInfo}>
                        <DonnaText variant="h2" style={styles.profileName}>{displayName}</DonnaText>
                        <DonnaText style={styles.profileEmail}>{user?.email}</DonnaText>
                    </View>
                    <Ionicons name="chevron-forward" size={20} color={Colors.textMuted} />
                </TouchableOpacity>

                {/* Subscription Banner */}
                <TouchableOpacity
                    style={styles.subscriptionBanner}
                    onPress={() => router.push('/settings/subscription' as any)}
                >
                    <View style={styles.subscriptionIcon}>
                        <Ionicons name="diamond" size={20} color={Colors.accentSecondary} />
                    </View>
                    <View style={styles.subscriptionInfo}>
                        <DonnaText style={styles.subscriptionTitle}>Teeks Pro</DonnaText>
                        <DonnaText style={styles.subscriptionSubtitle}>{getSubscriptionSubtitle()}</DonnaText>
                    </View>
                    <DonnaText style={styles.upgradeText}>
                        {subscriptionTier === 'pro' && isActive ? 'Manage →' : 'Upgrade →'}
                    </DonnaText>
                </TouchableOpacity>

                {/* Preferences */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>PREFERENCES</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="settings-outline"
                            iconColor={Colors.accentSecondary}
                            title="General"
                            subtitle="AI behavior, notifications, display"
                            onPress={() => router.push('/settings/general' as any)}
                        />
                        <SettingRow
                            icon="people-outline"
                            iconColor={Colors.accentPrecision}
                            title="Contacts"
                            subtitle="VIPs, tones, and relationship context"
                            onPress={() => router.push('/settings/contacts' as any)}
                        />
                        <SettingRow
                            icon="notifications-outline"
                            iconColor={Colors.accentSecondary}
                            title="Notifications"
                            subtitle="Push alerts and categories"
                            onPress={() => router.push('/settings/notifications' as any)}
                        />
                        <SettingRow
                            icon="brain-outline"
                            iconColor="#9B59B6"
                            title="Memory"
                            subtitle="Manage what Donna remembers"
                            onPress={() => router.push('/settings/memory' as any)}
                        />
                    </View>
                </View>

                {/* Productivity */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>PRODUCTIVITY</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="calendar-outline"
                            iconColor={Colors.accentPrecision}
                            title="Calendar"
                            subtitle="Working hours, buffers, sync"
                            onPress={() => router.push('/settings/calendar' as any)}
                        />
                        <SettingRow
                            icon="mail-outline"
                            iconColor={Colors.accentSecondary}
                            title="Digests"
                            subtitle="Briefing delivery times"
                            onPress={() => router.push('/settings/digests' as any)}
                        />
                    </View>
                </View>

                {/* Account */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>ACCOUNT</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="diamond-outline"
                            iconColor={Colors.accentSecondary}
                            title="Subscription"
                            subtitle={subscriptionTier === 'pro' ? 'Teeks Pro Active' : 'Trial Version'}
                            onPress={() => router.push('/settings/subscription' as any)}
                        />
                        <SettingRow
                            icon="shield-checkmark-outline"
                            iconColor={Colors.accentPrecision}
                            title="Privacy & Data"
                            subtitle="Security and export options"
                            onPress={() => router.push('/settings/privacy' as any)}
                        />
                    </View>
                </View>

                {/* Sign Out */}
                <TouchableOpacity style={styles.signOutButton} onPress={handleLogout}>
                    <Ionicons name="log-out-outline" size={20} color={Colors.error} />
                    <DonnaText style={styles.signOutText}>Sign Out</DonnaText>
                </TouchableOpacity>

                <DonnaText style={styles.versionText}>Teeks v1.0.0 (Build 42)</DonnaText>
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
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
        alignItems: 'center',
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
        fontFamily: 'Inter_600SemiBold',
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 40,
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
        width: 48,
        height: 48,
        borderRadius: 24,
        backgroundColor: Colors.accentSecondary,
        justifyContent: 'center',
        alignItems: 'center',
    },
    avatarText: {
        color: '#FFF',
        fontSize: 18,
        fontWeight: '600',
    },
    profileInfo: {
        flex: 1,
    },
    profileName: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    profileEmail: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 2,
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
        marginBottom: Spacing.lg,
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
