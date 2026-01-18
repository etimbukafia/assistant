import React, { useState } from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, Dimensions, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';

const { width } = Dimensions.get('window');

export default function WelcomeScreen() {
    const router = useRouter();
    const { signInWithGoogle } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    const handleGoogleAuth = async () => {
        try {
            setIsLoading(true);
            await signInWithGoogle();
            // On success, the auth state change will trigger navigation
            router.replace('/(tabs)' as any);
        } catch (error: any) {
            console.error('Google auth error:', error);
            Alert.alert(
                'Sign In Failed',
                error?.message || 'Unable to sign in with Google. Please try again.',
                [{ text: 'OK' }]
            );
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header / Nav */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
            </View>

            <View style={styles.content}>
                {/* Title Section */}
                <View style={styles.titleContainer}>
                    <DonnaText style={styles.title}>
                        Welcome!
                    </DonnaText>
                </View>

                {/* Auth Actions */}
                <View style={styles.actionsContainer}>
                    {/* Google Button */}
                    <TouchableOpacity
                        style={[styles.googleButton, isLoading && styles.googleButtonDisabled]}
                        activeOpacity={0.9}
                        onPress={handleGoogleAuth}
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <ActivityIndicator size="small" color="#4285F4" />
                        ) : (
                            <>
                                {/* Visual G icon placeholder or text */}
                                <View style={styles.googleIconPlaceholder}>
                                    <DonnaText style={styles.googleIconText}>G</DonnaText>
                                </View>
                                <DonnaText style={styles.googleButtonText}>Continue with Google</DonnaText>
                            </>
                        )}
                    </TouchableOpacity>
                </View>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase, // Linen
    },
    header: {
        paddingHorizontal: Spacing.lg,
        paddingTop: Spacing.md,
    },
    backButton: {
        padding: Spacing.xs,
    },
    content: {
        flex: 1,
        justifyContent: 'center', // Center vertically
        paddingHorizontal: Spacing.xl,
        paddingBottom: Spacing.xxl * 2,
    },
    titleContainer: {
        alignItems: 'center',
        marginBottom: Spacing.xxl,
    },
    title: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 32,
        lineHeight: 40, // Prevent clipping
        color: Colors.accentPrimary, // Rich Auburn
        textAlign: 'center',
    },
    actionsContainer: {
        width: '100%',
        gap: Spacing.md,
    },
    googleButton: {
        width: '100%',
        height: 56,
        backgroundColor: '#FFFFFF', // White background
        borderRadius: Radius.full,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 4,
        elevation: 3,
        marginBottom: Spacing.sm,
    },
    googleButtonDisabled: {
        opacity: 0.6,
    },
    googleIconPlaceholder: {
        marginRight: 12,
    },
    googleIconText: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#4285F4', // Google Blue
    },
    googleButtonText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: '#3C4043', // Dark grey text
        fontWeight: '500',
    },
    socialButton: {
        width: '100%',
        height: 56,
        borderRadius: Radius.full,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 0.5, // Dimmed to show it's disabled/placeholder
    },
    socialButtonText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: '#FFFFFF',
        fontWeight: '500',
    },
    dividerContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        marginVertical: Spacing.lg,
        opacity: 0.6,
    },
    dividerLine: {
        flex: 1,
        height: 1,
        backgroundColor: Colors.border,
    },
    dividerText: {
        marginHorizontal: Spacing.md,
        color: Colors.textMuted,
        fontFamily: 'Inter_400Regular',
        fontSize: 14,
    },
    footerContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        width: '100%',
        marginTop: Spacing.sm,
    },
    footerText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        color: Colors.textMuted,
    },
    linkText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 15,
        color: '#4ADE80', // Lighter green for visibility
        fontWeight: '600',
    },
});
