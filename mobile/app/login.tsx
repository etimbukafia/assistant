import React, { useState } from 'react';
import { Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { OnboardingScreen } from '../src/components/onboarding/OnboardingScreen';
import { useAuth } from '../src/context/AuthContext';

export default function LoginScreen() {
    const router = useRouter();
    const { signInWithGoogle } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    const handleGoogleAuth = async () => {
        try {
            setIsLoading(true);
            const success = await signInWithGoogle();
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
