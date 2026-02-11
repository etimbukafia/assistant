import React from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { SettingRow } from '@/src/components/ui/SettingRow';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '@/src/context/AuthContext';

export default function ProfileScreen() {
    const router = useRouter();
    const { user, signOut } = useAuth();

    const displayName = user?.user_metadata?.full_name || user?.user_metadata?.name;
    const displayEmail = user?.email;
    const initial = displayName?.[0]?.toUpperCase() || 'J';

    const handleLogout = async () => {
        Alert.alert(
            'Sign Out',
            'Are you sure you want to sign out?',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Sign Out', style: 'destructive', onPress: async () => {
                        try {
                            await signOut();
                        } catch (error) {
                            console.error('Sign out error:', error);
                        }
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
                <DonnaText style={styles.headerTitle}>Profile</DonnaText>
                <View style={styles.placeholder} />
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Profile Card */}
                <View style={styles.profileCard}>
                    <View style={styles.avatar}>
                        <DonnaText style={styles.avatarText}>{initial}</DonnaText>
                    </View>
                    <View style={styles.profileInfo}>
                        <DonnaText variant="h2" style={styles.profileName}>{displayName}</DonnaText>
                        <DonnaText style={styles.profileEmail}>{displayEmail}</DonnaText>
                    </View>
                    <TouchableOpacity style={styles.editButton}>
                        <Ionicons name="pencil" size={16} color={Colors.accentSecondary} />
                    </TouchableOpacity>
                </View>

                {/* Account Actions */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>ACCOUNT</DonnaText>
                    <View style={styles.sectionCard}>
                        <SettingRow
                            icon="shield-checkmark-outline"
                            iconColor={Colors.accentPrecision}
                            title="Data & Privacy"
                            subtitle="Export, revoke access, delete account"
                            onPress={() => router.push('/settings/privacy' as any)}
                        />
                    </View>
                </View>

                {/* Sign Out */}
                <TouchableOpacity style={styles.signOutButton} onPress={handleLogout}>
                    <Ionicons name="log-out-outline" size={20} color={Colors.error} />
                    <DonnaText style={styles.signOutText}>Sign Out</DonnaText>
                </TouchableOpacity>

                {/* Version */}
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
        padding: Spacing.lg,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        marginBottom: Spacing.xl,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    avatar: {
        width: 64,
        height: 64,
        borderRadius: 32,
        backgroundColor: Colors.accentPrecision,
        justifyContent: 'center',
        alignItems: 'center',
    },
    avatarText: {
        color: '#FFF',
        fontSize: 24,
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
