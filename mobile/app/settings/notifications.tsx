/**
 * Notification Settings Screen
 *
 * Toggle switches for push notification categories.
 * Reads/writes notification_preferences via the settings hook.
 */

import React from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Switch, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useSettings } from '@/src/hooks/useSettings';

const DEFAULT_PREFS = {
    push_enabled: true,
    push_urgent_tasks: true,
    push_deadlines: true,
    push_digests: true,
    push_briefings: true,
};

export default function NotificationSettingsScreen() {
    const router = useRouter();
    const { settings, isLoading, updateSettings, isUpdating } = useSettings();

    const prefs = settings?.notification_preferences ?? DEFAULT_PREFS;

    const handleToggle = (key: string, value: boolean) => {
        updateSettings({
            notification_preferences: { ...prefs, [key]: value },
        });
    };

    const Header = () => (
        <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
            </TouchableOpacity>
            <DonnaText style={styles.headerTitle}>Notifications</DonnaText>
            <View style={styles.headerPlaceholder} />
        </View>
    );

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <Header />
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                </View>
            </SafeAreaView>
        );
    }

    const pushEnabled = prefs.push_enabled ?? true;

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <Header />

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Master Toggle */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>PUSH NOTIFICATIONS</DonnaText>
                    <View style={styles.sectionCard}>
                        <View style={styles.settingRow}>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Enable Push Notifications</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Receive alerts on your device for important events
                                </DonnaText>
                            </View>
                            <Switch
                                value={pushEnabled}
                                onValueChange={(v) => handleToggle('push_enabled', v)}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating}
                            />
                        </View>
                    </View>
                </View>

                {/* Category Toggles */}
                <View style={[styles.section, !pushEnabled && styles.disabledSection]}>
                    <DonnaText style={styles.sectionLabel}>NOTIFICATION CATEGORIES</DonnaText>
                    <View style={styles.sectionCard}>
                        <View style={styles.settingRow}>
                            <View style={[styles.iconContainer, { backgroundColor: Colors.error + '15' }]}>
                                <Ionicons name="alert-circle" size={20} color={Colors.error} />
                            </View>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Urgent Tasks</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    High-priority tasks that need immediate attention
                                </DonnaText>
                            </View>
                            <Switch
                                value={prefs.push_urgent_tasks ?? true}
                                onValueChange={(v) => handleToggle('push_urgent_tasks', v)}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating || !pushEnabled}
                            />
                        </View>

                        <View style={styles.settingRow}>
                            <View style={[styles.iconContainer, { backgroundColor: Colors.accentSecondary + '15' }]}>
                                <Ionicons name="time" size={20} color={Colors.accentSecondary} />
                            </View>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Deadlines</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Upcoming task deadlines and due dates
                                </DonnaText>
                            </View>
                            <Switch
                                value={prefs.push_deadlines ?? true}
                                onValueChange={(v) => handleToggle('push_deadlines', v)}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating || !pushEnabled}
                            />
                        </View>

                        <View style={styles.settingRow}>
                            <View style={[styles.iconContainer, { backgroundColor: Colors.accentPrecision + '15' }]}>
                                <Ionicons name="mail" size={20} color={Colors.accentPrecision} />
                            </View>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Digests</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    When your daily email digests are ready
                                </DonnaText>
                            </View>
                            <Switch
                                value={prefs.push_digests ?? true}
                                onValueChange={(v) => handleToggle('push_digests', v)}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating || !pushEnabled}
                            />
                        </View>

                        <View style={[styles.settingRow, { borderBottomWidth: 0 }]}>
                            <View style={[styles.iconContainer, { backgroundColor: Colors.accentPrecision + '15' }]}>
                                <Ionicons name="calendar" size={20} color={Colors.accentPrecision} />
                            </View>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Briefings</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Morning and end-of-day briefing alerts
                                </DonnaText>
                            </View>
                            <Switch
                                value={prefs.push_briefings ?? true}
                                onValueChange={(v) => handleToggle('push_briefings', v)}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating || !pushEnabled}
                            />
                        </View>
                    </View>
                </View>

                {/* Info */}
                <View style={styles.infoCard}>
                    <Ionicons name="information-circle-outline" size={20} color={Colors.textSecondary} />
                    <DonnaText style={styles.infoText}>
                        All activity is always available in your in-app notification feed, regardless of push settings.
                    </DonnaText>
                </View>
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
    backButton: {
        padding: Spacing.xs,
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    headerPlaceholder: {
        width: 40,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
    },
    section: {
        marginBottom: Spacing.xl,
    },
    disabledSection: {
        opacity: 0.5,
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
    infoCard: {
        flexDirection: 'row',
        gap: Spacing.sm,
        padding: Spacing.md,
        backgroundColor: 'rgba(217, 119, 69, 0.05)',
        borderRadius: Radius.lg,
    },
    infoText: {
        flex: 1,
        fontSize: 13,
        color: Colors.textSecondary,
        lineHeight: 18,
    },
});
