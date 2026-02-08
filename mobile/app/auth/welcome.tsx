import React, { useState } from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, Dimensions, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { ImmersiveBackground } from '../../src/components/ui/ImmersiveBackground';

const { width } = Dimensions.get('window');

export default function WelcomeScreen() {
    const router = useRouter();
    const { signInWithGoogle } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    const handleGoogleAuth = async () => {
        try {
            setIsLoading(true);
            const success = await signInWithGoogle();
            // Only navigate if sign-in was successful (not cancelled)
            if (success) {
                router.replace('/(tabs)' as any);
            }
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
        <ImmersiveBackground style={styles.container}>
            <StatusBar style="dark" />

            <SafeAreaView style={styles.safeArea}>
                {/* Header / Nav */}
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <DonnaText style={styles.backButtonText}>←</DonnaText>
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
                                <ActivityIndicator size="small" color="#FFFFFF" />
                            ) : (
                                <>
                                    <View style={styles.googleIconPlaceholder}>
                                        <Ionicons name="logo-google" size={20} color="#FFFFFF" />
                                    </View>
                                    <DonnaText style={styles.googleButtonText}>Continue with Google</DonnaText>
                                </>
                            )}
                        </TouchableOpacity>
                    </View>
                </View>
            </SafeAreaView>
        </ImmersiveBackground>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    safeArea: {
        flex: 1,
    },
    header: {
        paddingHorizontal: Spacing.lg,
        paddingTop: Spacing.md,
    },
    backButton: {
        padding: Spacing.xs,
        width: 44,
        height: 44,
        justifyContent: 'center',
        alignItems: 'center',
        borderRadius: Radius.full,
        backgroundColor: 'rgba(0,0,0,0.05)', // Subtle dark on linen
        borderWidth: 1,
        borderColor: 'rgba(0,0,0,0.1)',
    },
    backButtonText: {
        fontSize: 24,
        color: Colors.textPrimary, // Dark obsidian
        lineHeight: 28,
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
        fontSize: 40,
        lineHeight: 48,
        color: Colors.accentPrimary, // Rich Auburn
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    subtitle: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: Colors.textSecondary,
        textAlign: 'center',
        opacity: 0.8,
    },
    actionsContainer: {
        width: '100%',
        gap: Spacing.md,
    },
    googleButton: {
        width: '100%',
        height: 56,
        backgroundColor: Colors.accentSecondary, // Natural Copper
        borderRadius: Radius.full,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: Colors.accentSecondary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.4,
        shadowRadius: 12,
        elevation: 5,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.2)',
        marginBottom: Spacing.sm,
    },
    googleButtonDisabled: {
        opacity: 0.6,
    },
    googleIconPlaceholder: {
        marginRight: 12,
    },
    googleButtonText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: '#FFFFFF', // White text on copper
        fontWeight: '600',
        letterSpacing: 0.5,
    },
});
