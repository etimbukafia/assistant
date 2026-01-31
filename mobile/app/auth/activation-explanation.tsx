import React from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, ScrollView, Dimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { useBillingActions } from '../../src/hooks/useSubscription';

const { width } = Dimensions.get('window');

export default function ActivationExplanationScreen() {
    const router = useRouter();
    const { assistantName } = useAuth(); // Get dynamic name
    const { refreshProfile } = useAuth();
    const { activateTrialAsync, triggerInitialSyncAsync, isActivatingTrial, isTriggering } = useBillingActions();

    const handleStartSync = () => {
        router.push('/settings/activate_trial');
    };

    const isLoading = isActivatingTrial || isTriggering;

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.closeButton}>
                    <Ionicons name="close" size={28} color={Colors.textPrimary} />
                </TouchableOpacity>
            </View>

            <ScrollView contentContainerStyle={styles.content}>
                <View style={styles.iconContainer}>
                    <View style={styles.iconCircle}>
                        <Ionicons name="shield-checkmark" size={40} color={Colors.accentSecondary} />
                    </View>
                </View>

                <DonnaText style={styles.title}>
                    Personalizing Your Assistant
                </DonnaText>

                <View style={styles.bulletContainer}>
                    <View style={styles.bullet}>
                        <View style={styles.bulletIcon}>
                            <Ionicons name="time-outline" size={24} color={Colors.accentSecondary} />
                        </View>
                        <View style={styles.bulletText}>
                            <DonnaText style={styles.bulletTitle}>24-Hour Lookback</DonnaText>
                            <DonnaText style={styles.bulletDescription}>
                                {assistantName} will briefly analyze your last 24 hours of emails to understand your current priorities.
                            </DonnaText>
                        </View>
                    </View>

                    <View style={styles.bullet}>
                        <View style={styles.bulletIcon}>
                            <Ionicons name="sync-outline" size={24} color={Colors.accentSecondary} />
                        </View>
                        <View style={styles.bulletText}>
                            <DonnaText style={styles.bulletTitle}>Real-time Intelligence</DonnaText>
                            <DonnaText style={styles.bulletDescription}>
                                Going forward, {assistantName} automatically processes new emails as they arrive, keeping your highlights current.
                            </DonnaText>
                        </View>
                    </View>

                    <View style={styles.bullet}>
                        <View style={styles.bulletIcon}>
                            <Ionicons name="finger-print-outline" size={24} color={Colors.accentSecondary} />
                        </View>
                        <View style={styles.bulletText}>
                            <DonnaText style={styles.bulletTitle}>Privacy First</DonnaText>
                            <DonnaText style={styles.bulletDescription}>
                                No actions are taken without your explicit confirmation. Your data is encrypted and used only to assist you.
                            </DonnaText>
                        </View>
                    </View>
                </View>

                <View style={styles.spacer} />

                <TouchableOpacity
                    style={styles.primaryButton}
                    onPress={handleStartSync}
                >
                    <DonnaText style={styles.buttonText}>Use {assistantName} with my inbox</DonnaText>
                </TouchableOpacity>

                <DonnaText style={styles.footerNote}>
                    You can disconnect your inbox at any time in settings.
                </DonnaText>
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
        paddingHorizontal: Spacing.lg,
        paddingTop: Spacing.md,
        alignItems: 'flex-end',
    },
    closeButton: {
        padding: Spacing.xs,
    },
    content: {
        paddingHorizontal: Spacing.xl,
        paddingTop: Spacing.lg,
        paddingBottom: Spacing.xxl,
        alignItems: 'center',
    },
    iconContainer: {
        marginBottom: Spacing.xl,
    },
    iconCircle: {
        width: 80,
        height: 80,
        borderRadius: 40,
        backgroundColor: 'rgba(217, 119, 69, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    title: {
        ...Typography.h1,
        textAlign: 'center',
        marginBottom: Spacing.xl * 1.5,
        color: Colors.textPrimary,
    },
    bulletContainer: {
        width: '100%',
        gap: Spacing.xl,
    },
    bullet: {
        flexDirection: 'row',
        alignItems: 'flex-start',
    },
    bulletIcon: {
        width: 40,
        marginRight: Spacing.md,
        paddingTop: 2,
    },
    bulletText: {
        flex: 1,
    },
    bulletTitle: {
        ...Typography.h2,
        fontSize: 18,
        color: Colors.textPrimary,
        marginBottom: Spacing.xs,
    },
    bulletDescription: {
        ...Typography.bodyBase,
        color: Colors.textMuted,
        lineHeight: 22,
    },
    spacer: {
        height: Spacing.xl * 2,
    },
    primaryButton: {
        width: '100%',
        height: 56,
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.full,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.md,
    },
    buttonText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        fontWeight: '600',
        color: '#FFFFFF',
        letterSpacing: 0.5,
    },
    footerNote: {
        ...Typography.caption,
        color: Colors.textMuted,
        textAlign: 'center',
        opacity: 0.6,
    },
});
