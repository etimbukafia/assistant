import React, { useState } from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, Dimensions, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Typography, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { ImmersiveBackground } from '../../src/components/ui/ImmersiveBackground';
import { Glass } from '../../src/theme/Glass';

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
            <StatusBar style="light" />

            <SafeAreaView style={styles.safeArea}>
                {/* Header / Nav */}
                <View style={styles.header}>
                    <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                        <Ionicons name="arrow-back" size={24} color="#FFFFFF" />
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
                                <ActivityIndicator size="small" color={Colors.bgBase} />
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
        width: 40,
        height: 40,
        justifyContent: 'center',
        alignItems: 'center',
        borderRadius: Radius.full,
        backgroundColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
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
        fontSize: 36,
        lineHeight: 44,
        color: '#FFFFFF',
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
        backgroundColor: '#FFFFFF', // White background
        borderRadius: Radius.full,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 5,
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
        color: Colors.bgBase, // Dark text
    },
    googleButtonText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: Colors.bgBase, // Dark text
        fontWeight: '600',
    },
});
