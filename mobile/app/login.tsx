import React, { useState, useEffect } from 'react';
import { Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { OnboardingScreen } from '../src/components/onboarding/OnboardingScreen';
import { useAuth } from '../src/context/AuthContext';

export default function LoginScreen() {
    const router = useRouter();
    const { signInWithGoogle, isAuthenticated, onboardingCompleted, isActive } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    // Redirect authenticated users to appropriate screen
    useEffect(() => {
        if (isAuthenticated) {
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
    }, [isAuthenticated, onboardingCompleted, isActive]);

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
