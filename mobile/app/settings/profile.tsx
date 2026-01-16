import React from 'react';
import { StyleSheet, View, SafeAreaView, TouchableOpacity, ScrollView, Dimensions } from 'react-native';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../src/context/AuthContext';
import { useRouter } from 'expo-router';

const { width } = Dimensions.get('window');

export default function ProfileScreen() {
    const { logout, user } = useAuth();
    const router = useRouter();

    const initial = user?.name?.[0] || '?';
    const userName = user?.name || 'Guest User';
    const userEmail = user?.email || 'Set up your account';

    const SettingItem = ({ icon, title, value, onPress, color = Colors.accentSecondary }: any) => (
        <TouchableOpacity style={styles.item} onPress={onPress}>
            <View style={styles.itemLeft}>
                <Ionicons name={icon} size={20} color={color} style={styles.itemIcon} />
                <DonnaText style={[styles.itemTitle, { color }]}>{title}</DonnaText>
            </View>
            <View style={styles.itemRight}>
                {value && <DonnaText style={styles.itemValue}>{value}</DonnaText>}
                <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
            </View>
        </TouchableOpacity>
    );

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header with Close */}
            <View style={styles.modalHeader}>
                <TouchableOpacity onPress={() => router.back()} style={styles.closeButton}>
                    <Ionicons name="close" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.modalTitle}>Your Assistant</DonnaText>
                <View style={{ width: 40 }} />
            </View>

            <ScrollView contentContainerStyle={styles.scrollContent}>
                {/* Profile Card */}
                <View style={styles.profileCard}>
                    <View style={styles.avatarLarge}>
                        <DonnaText style={styles.avatarText}>{initial}</DonnaText>
                    </View>
                    <DonnaText style={styles.userName}>{userName}</DonnaText>
                    <DonnaText style={styles.userEmail}>{userEmail}</DonnaText>

                    <View style={styles.badgeRow}>
                        <View style={styles.badge}>
                            <DonnaText style={styles.badgeText}>Pro Member</DonnaText>
                        </View>
                    </View>
                </View>

                {/* Settings Sections */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>Intelligence & Memory</DonnaText>
                    <View style={styles.card}>
                        <SettingItem icon="brain" title="Memory Palace" value="84 facts" />
                        <SettingItem icon="chatbubble-ellipses-outline" title="Communication Tone" value="Executive" />
                        <SettingItem icon="filter-outline" title="Priority Rules" value="Active" />
                    </View>
                </View>

                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>Connections</DonnaText>
                    <View style={styles.card}>
                        <SettingItem icon="mail-outline" title="Gmail Sync" value="Live" />
                        <SettingItem icon="calendar-outline" title="Google Calendar" value="Connected" />
                    </View>
                </View>

                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>Preferences</DonnaText>
                    <View style={styles.card}>
                        <SettingItem icon="notifications-outline" title="Notifications" />
                        <SettingItem icon="moon-outline" title="Quiet Hours" />
                        <SettingItem icon="log-out-outline" title="Logout" color={Colors.accentPrimary} onPress={logout} />
                    </View>
                </View>

                <DonnaText style={styles.version}>Donna Mobile v0.1.0 Beta</DonnaText>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    modalHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.lg,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    closeButton: {
        padding: Spacing.xs,
        width: 40,
    },
    modalTitle: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 18,
        color: Colors.textPrimary,
    },
    scrollContent: {
        paddingHorizontal: Spacing.md,
        paddingBottom: Spacing.xxl,
    },
    profileCard: {
        alignItems: 'center',
        paddingVertical: Spacing.xl,
        backgroundColor: Colors.bgElevated,
        marginTop: Spacing.md,
        borderRadius: Radius.surface,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    avatarLarge: {
        width: 80,
        height: 80,
        borderRadius: 40,
        backgroundColor: Colors.accentSecondary,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.md,
        shadowColor: Colors.accentSecondary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.2,
        shadowRadius: 8,
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
    },
    avatarText: {
        fontSize: 32,
        color: '#FFFFFF',
        fontWeight: '200',
    },
    userName: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 22,
        color: Colors.textPrimary,
    },
    userEmail: {
        ...Typography.bodyBase,
        color: Colors.textMuted,
        marginTop: 4,
    },
    badgeRow: {
        marginTop: Spacing.md,
    },
    badge: {
        backgroundColor: 'rgba(217, 119, 69, 0.1)',
        paddingHorizontal: 12,
        paddingVertical: 4,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
    },
    badgeText: {
        fontSize: 12,
        color: Colors.accentSecondary,
        fontWeight: '600',
        textTransform: 'uppercase',
        letterSpacing: 0.5,
    },
    section: {
        marginTop: Spacing.xl,
    },
    sectionLabel: {
        ...Typography.labelSmall,
        color: Colors.textMuted,
        marginBottom: Spacing.sm,
        marginLeft: Spacing.xs,
        textTransform: 'uppercase',
        letterSpacing: 1,
    },
    card: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: Colors.border,
    },
    item: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    itemLeft: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    itemIcon: {
        marginRight: Spacing.md,
        width: 24,
    },
    itemTitle: {
        ...Typography.bodyBase,
    },
    itemRight: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    itemValue: {
        ...Typography.bodyBase,
        color: Colors.textMuted,
        marginRight: Spacing.xs,
        fontSize: 14,
    },
    version: {
        ...Typography.caption,
        color: Colors.textMuted,
        textAlign: 'center',
        marginTop: Spacing.xxl,
        opacity: 0.5,
    },
});
