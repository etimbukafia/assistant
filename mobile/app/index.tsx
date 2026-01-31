import React, { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors } from '../src/theme/Theme';
import { DonnaText } from '../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withTiming,
    Easing,
    runOnJS
} from 'react-native-reanimated';

export default function SplashScreen() {
    const router = useRouter();
    const logoScale = useSharedValue(0.8);
    const logoOpacity = useSharedValue(0);

    useEffect(() => {
        // Animation sequence
        logoOpacity.value = withTiming(1, { duration: 1000 });
        logoScale.value = withTiming(1, {
            duration: 1000,
            easing: Easing.out(Easing.back(1.5))
        }, () => {
            // After animation, wait a bit then navigate
            runOnJS(navigateToLogin)();
        });
    }, []);

    const navigateToLogin = () => {
        setTimeout(() => {
            router.replace('/login' as any);
        }, 1200); // Give it a moment of stillness
    };

    const logoAnimatedStyle = useAnimatedStyle(() => ({
        transform: [{ scale: logoScale.value }],
        opacity: logoOpacity.value,
    }));

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <View style={styles.content}>
                <Animated.View style={[styles.logoContainer, logoAnimatedStyle]}>
                    <View style={styles.logoCircle}>
                        <DonnaText variant="h1" color={Colors.accentPrimary}>T</DonnaText>
                    </View>
                    <DonnaText variant="h1" style={styles.logoText}>Teeks</DonnaText>
                </Animated.View>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    logoContainer: {
        alignItems: 'center',
    },
    logoCircle: {
        width: 100,
        height: 100,
        borderRadius: 50,
        backgroundColor: Colors.bgElevated,
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: 1,
        borderColor: Colors.border,
        marginBottom: 20,
    },
    logoText: {
        fontSize: 32,
        letterSpacing: 4,
        fontWeight: '200',
    },
});
