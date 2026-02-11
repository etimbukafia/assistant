import { useEffect } from 'react';
import { useRouter } from 'expo-router';
import { useAuth } from '../src/context/AuthContext';

// Smart redirect based on auth state
export default function IndexRedirect() {
    const router = useRouter();
    const { isLoading, isAuthenticated, profileLoaded, onboardingCompleted, isActive, accountConflict } = useAuth();

    useEffect(() => {
        // Wait for auth state to be determined
        if (isLoading) return;

        // Not authenticated - go to login
        if (!isAuthenticated) {
            router.replace('/login' as any);
            return;
        }

        // Authenticated but profile not loaded yet - wait
        if (!profileLoaded) return;

        // Account conflict - go to login (which will show the error)
        if (accountConflict) {
            router.replace('/login' as any);
            return;
        }

        // Route based on onboarding state
        if (onboardingCompleted) {
            router.replace('/(tabs)' as any);
        } else if (isActive) {
            router.replace('/auth/setup' as any);
        } else {
            router.replace('/auth/subscription' as any);
        }
    }, [isLoading, isAuthenticated, profileLoaded, onboardingCompleted, isActive, accountConflict]);

    // Return null - CustomSplashScreen in _layout.tsx handles the visual
    return null;
}
