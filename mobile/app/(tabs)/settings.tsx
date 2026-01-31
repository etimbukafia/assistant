import React from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '@/src/context/AuthContext';

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

export default function SettingsHubScreen() {
    const router = useRouter();
    const { user, subscriptionTier } = useAuth();

    const displayName = user?.user_metadata?.full_name || user?.user_metadata?.name;
    const initial = displayName?.[0]?.toUpperCase() || 'J';

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

                {/* Main Settings Sections */}
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
        marginBottom: Spacing.xl,
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
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 1,
    },
    versionText: {
        textAlign: 'center',
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: Spacing.xl,
    },
});
