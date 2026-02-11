import React, { useState, useEffect } from 'react';
import { Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { OnboardingScreen } from '../src/components/onboarding/OnboardingScreen';
import { useAuth } from '../src/context/AuthContext';

export default function LoginScreen() {
    const router = useRouter();
    const {
        signInWithGoogle,
        signOut,
        isAuthenticated,
        profileLoaded,
        onboardingCompleted,
        isActive,
        accountConflict,
        accountConflictMessage
    } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    // Handle account conflict - show error and sign out
    useEffect(() => {
        if (isAuthenticated && profileLoaded && accountConflict) {
            Alert.alert(
                'Account Issue',
                accountConflictMessage || 'An account with this email already exists with a different login. Please contact support@teeks.ai to recover your account.',
                [
                    {
                        text: 'OK',
                        onPress: async () => {
                            // Sign out so they can try a different account or contact support
                            await signOut();
                        }
                    }
                ],
                { cancelable: false }
            );
        }
    }, [isAuthenticated, profileLoaded, accountConflict, accountConflictMessage, signOut]);

    // Redirect authenticated users to appropriate screen
    // Wait for profileLoaded to prevent race condition where we navigate
    // before settings are fetched (would always go to subscription)
    useEffect(() => {
        // Don't navigate if there's an account conflict
        if (isAuthenticated && profileLoaded && !accountConflict) {
            if (onboardingCompleted) {
                // Returning user - go to main app
                router.replace('/(tabs)' as any);
            } else if (isActive) {
                // Has subscription but didn't finish setup
                router.replace('/auth/setup' as any);
            } else {
                // New user - needs to select subscription
                router.replace('/auth/subscription' as any);
            }
        }
    }, [isAuthenticated, profileLoaded, onboardingCompleted, isActive, accountConflict]);

    const handleGoogleAuth = async () => {
        try {
            setIsLoading(true);
            const success = await signInWithGoogle();
            if (success) {
                // Navigation will be handled by useEffect above after auth state updates
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

    const handleLogin = () => {
        router.push('/auth/welcome' as any);
    };

    return (
        <OnboardingScreen
            onGoogleAuth={handleGoogleAuth}
            onLogin={handleLogin}
            isLoading={isLoading}
        />
    );
}
