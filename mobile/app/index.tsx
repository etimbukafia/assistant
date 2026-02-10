import { useEffect } from 'react';
import { useRouter } from 'expo-router';

// This is just a redirect - the CustomSplashScreen handles the visual splash
export default function IndexRedirect() {
    const router = useRouter();

    useEffect(() => {
        // Immediately redirect to login screen
        router.replace('/login' as any);
    }, []);

    // Return null - CustomSplashScreen in _layout.tsx handles the visual
    return null;
}
