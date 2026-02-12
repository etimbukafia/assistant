import React, { useState, useEffect } from 'react';
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
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';

/**
 * Pre-frame screen shown before Google OAuth.
 *
 * Purpose: Build trust by explaining what Teeks will and won't do
 * BEFORE the user sees Google's intimidating permission screen.
 */
export default function ConnectGoogleScreen() {
    const router = useRouter();
    const { signInWithGoogle, isAuthenticated, profileLoaded, onboardingCompleted, isActive, refreshProfile } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    // Navigate returning users who are already authenticated
    // (e.g., deep link back to this screen while logged in)
    useEffect(() => {
        if (!isLoading && isAuthenticated && profileLoaded) {
            if (onboardingCompleted) {
                router.replace('/(tabs)' as any);
            } else if (isActive) {
                router.replace('/auth/setup' as any);
            }
            // Don't auto-navigate to subscription — wait for explicit sign-in flow
            // to complete (connectGmail must finish first)
        }
    }, [isAuthenticated, profileLoaded, onboardingCompleted, isActive, isLoading]);

    const handleConnect = async () => {
        try {
            setIsLoading(true);
            const success = await signInWithGoogle();
            if (success) {
                // signInWithGoogle completed — Gmail tokens are now stored.
                // Refresh profile to get updated gmail_connected status,
                // then navigate based on subscription state.
                await refreshProfile();
                router.replace('/auth/subscription' as any);
                return;
            }
        } catch (error: any) {
            console.error('Google auth error:', error);

            // Check if it's a missing scopes error
            const errorData = error?.response?.data?.detail;
            if (errorData?.error === 'missing_scopes') {
                Alert.alert(
                    'Permissions Required',
                    `To use Teeks, please grant all requested permissions:\n\n• ${errorData.missing_permissions?.join('\n• ')}`,
                    [
                        { text: 'Cancel', style: 'cancel' },
                        { text: 'Try Again', onPress: () => handleConnect() }
                    ]
                );
            } else if (errorData?.error === 'account_conflict') {
                Alert.alert(
                    'Account Issue',
                    errorData.message || 'An account with this email already exists. Please contact support.',
                    [{ text: 'OK' }]
                );
            } else {
                Alert.alert(
                    'Connection Failed',
                    'Unable to connect your Google account. Please try again.',
                    [
                        { text: 'Cancel', style: 'cancel' },
                        { text: 'Try Again', onPress: () => handleConnect() }
                    ]
                );
            }
        } finally {
            setIsLoading(false);
        }
    };

    const handleBack = () => {
        router.back();
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header with back button */}
            <View style={styles.header}>
                <TouchableOpacity onPress={handleBack} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
            </View>

            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.content}
                showsVerticalScrollIndicator={false}
            >
                {/* Icon and Title */}
                <View style={styles.titleSection}>
                    <View style={styles.iconContainer}>
                        <Ionicons name="logo-google" size={32} color="#4285F4" />
                    </View>
                    <DonnaText style={styles.title}>Connect Your Google Workspace</DonnaText>
                    <DonnaText style={styles.subtitle}>
                        Teeks needs access to your Gmail and Calendar to help manage your work
                    </DonnaText>
                </View>

                {/* What Teeks Will Do */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionTitle}>Teeks will:</DonnaText>

                    <View style={styles.listItem}>
                        <Ionicons name="checkmark-circle" size={20} color={Colors.success} />
                        <DonnaText style={styles.listText}>
                            Read emails to extract tasks and context
                        </DonnaText>
                    </View>

                    <View style={styles.listItem}>
                        <Ionicons name="checkmark-circle" size={20} color={Colors.success} />
                        <DonnaText style={styles.listText}>
                            Draft responses for your approval
                        </DonnaText>
                    </View>

                    <View style={styles.listItem}>
                        <Ionicons name="checkmark-circle" size={20} color={Colors.success} />
                        <DonnaText style={styles.listText}>
                            Check calendar availability when scheduling
                        </DonnaText>
                    </View>

                    <View style={styles.listItem}>
                        <Ionicons name="checkmark-circle" size={20} color={Colors.success} />
                        <DonnaText style={styles.listText}>
                            Create events only with your confirmation
                        </DonnaText>
                    </View>
                </View>

                {/* What Teeks Will Never Do */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionTitle}>Teeks will never:</DonnaText>

                    <View style={styles.listItem}>
                        <Ionicons name="close-circle" size={20} color={Colors.error} />
                        <DonnaText style={styles.listText}>
                            Send emails without your approval
                        </DonnaText>
                    </View>

                    <View style={styles.listItem}>
                        <Ionicons name="close-circle" size={20} color={Colors.error} />
                        <DonnaText style={styles.listText}>
                            Share or sell your data
                        </DonnaText>
                    </View>

                    <View style={styles.listItem}>
                        <Ionicons name="close-circle" size={20} color={Colors.error} />
                        <DonnaText style={styles.listText}>
                            Access files unrelated to email or calendar
                        </DonnaText>
                    </View>
                </View>

                {/* Revoke Notice */}
                <View style={styles.revokeNotice}>
                    <Ionicons name="shield-checkmark" size={20} color={Colors.accentSecondary} />
                    <DonnaText style={styles.revokeText}>
                        You can revoke access anytime in your Google account settings
                    </DonnaText>
                </View>
            </ScrollView>

            {/* CTA Button */}
            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.connectButton, isLoading && styles.buttonDisabled]}
                    onPress={handleConnect}
                    disabled={isLoading}
                    activeOpacity={0.9}
                >
                    {isLoading ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <>
                            <Ionicons name="logo-google" size={20} color="#FFFFFF" />
                            <DonnaText style={styles.connectButtonText}>
                                Continue with Google
                            </DonnaText>
                        </>
                    )}
                </TouchableOpacity>
            </View>
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
        paddingTop: Spacing.sm,
    },
    backButton: {
        width: 40,
        height: 40,
        justifyContent: 'center',
        alignItems: 'center',
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.lg,
        paddingTop: Spacing.md,
    },
    titleSection: {
        alignItems: 'center',
        marginBottom: Spacing.xl,
    },
    iconContainer: {
        width: 64,
        height: 64,
        borderRadius: 32,
        backgroundColor: '#4285F410',
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.md,
    },
    title: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 24,
        color: Colors.textPrimary,
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    subtitle: {
        fontSize: 15,
        color: Colors.textSecondary,
        textAlign: 'center',
        lineHeight: 22,
    },
    section: {
        marginBottom: Spacing.lg,
    },
    sectionTitle: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: Spacing.md,
    },
    listItem: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: Spacing.sm,
        marginBottom: Spacing.sm,
    },
    listText: {
        flex: 1,
        fontSize: 15,
        color: Colors.textSecondary,
        lineHeight: 22,
    },
    revokeNotice: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: Spacing.sm,
        backgroundColor: Colors.accentSecondary + '10',
        padding: Spacing.md,
        borderRadius: Radius.md,
        marginTop: Spacing.md,
    },
    revokeText: {
        flex: 1,
        fontSize: 13,
        color: Colors.textSecondary,
        lineHeight: 20,
    },
    footer: {
        padding: Spacing.lg,
        paddingBottom: Spacing.xl,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        backgroundColor: Colors.bgSurface,
    },
    connectButton: {
        backgroundColor: '#4285F4',
        borderRadius: Radius.full,
        paddingVertical: Spacing.md + 2,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        shadowColor: '#4285F4',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 4,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    connectButtonText: {
        color: '#FFFFFF',
        fontSize: 17,
        fontWeight: '600',
    },
});
