import React, { useEffect, useState } from 'react';
import { View, StyleSheet, SafeAreaView } from 'react-native';
import { useRouter } from 'expo-router';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withRepeat,
    withTiming,
    withSequence,
    Easing,
    FadeIn,
    FadeOut
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { Colors, Spacing } from '../src/theme/Theme';
import { DonnaText } from '../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';

const LOGS = [
    { text: "Mapping the Executive's ecosystem...", haptic: Haptics.ImpactFeedbackStyle.Light, delay: 0 },
    { text: "Filtering 42 threads for High-Value Interruptions...", haptic: Haptics.ImpactFeedbackStyle.Light, delay: 1500 },
    { text: "Synthesizing 'Principal Memory' for drafting...", haptic: Haptics.ImpactFeedbackStyle.Medium, delay: 3000 },
    { text: "Morning Briefing prepared.", haptic: Haptics.ImpactFeedbackStyle.Heavy, delay: 4500 },
];

export default function SyncingScreen() {
    const router = useRouter();
    const rotation = useSharedValue(0);
    const [logIndex, setLogIndex] = useState(0);

    useEffect(() => {
        // Start orbit animation
        rotation.value = withRepeat(
            withTiming(360, { duration: 2000, easing: Easing.linear }),
            -1,
            false
        );

        // Sequence logs and haptics
        const timeouts = LOGS.map((log, index) => {
            return setTimeout(() => {
                setLogIndex(index);
                Haptics.impactAsync(log.haptic);
            }, log.delay);
        });

        // Final navigation
        const finalTimer = setTimeout(() => {
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            router.replace('/(tabs)');
        }, 5500);

        return () => {
            timeouts.forEach(clearTimeout);
            clearTimeout(finalTimer);
        };
    }, []);

    const orbitStyle = useAnimatedStyle(() => {
        return {
            transform: [{ rotate: `${rotation.value}deg` }],
        };
    });

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="light" />
            <View style={styles.content}>
                <View style={styles.loaderContainer}>
                    <Animated.View style={[styles.orbit, orbitStyle]}>
                        <View style={styles.dot} />
                    </Animated.View>
                    <View style={styles.core} />
                </View>

                <View style={styles.textContainer}>
                    <Animated.View
                        key={logIndex}
                        entering={FadeIn.duration(400)}
                        exiting={FadeOut.duration(400)}
                        style={styles.logWrapper}
                    >
                        <DonnaText variant="h2" style={styles.logText}>
                            {LOGS[logIndex].text}
                        </DonnaText>
                        <DonnaText variant="bodyBase" color={Colors.textMuted} style={styles.subtitle}>
                            Donna is personalizing your workspace
                        </DonnaText>
                    </Animated.View>
                </View>
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
        paddingHorizontal: Spacing.xl,
    },
    loaderContainer: {
        width: 120,
        height: 120,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.xl * 2,
    },
    core: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: Colors.accentPrimary,
        opacity: 0.8,
    },
    orbit: {
        position: 'absolute',
        width: 100,
        height: 100,
        borderRadius: 50,
        borderWidth: 1,
        borderColor: 'rgba(0, 123, 167, 0.2)',
        justifyContent: 'flex-start',
        alignItems: 'center',
    },
    dot: {
        width: 12,
        height: 12,
        borderRadius: 6,
        backgroundColor: Colors.accentPrecision,
        marginTop: -6,
    },
    textContainer: {
        alignItems: 'center',
        height: 100,
        width: '100%',
    },
    logWrapper: {
        alignItems: 'center',
        position: 'absolute',
    },
    logText: {
        textAlign: 'center',
    },
    subtitle: {
        marginTop: Spacing.sm,
        textAlign: 'center',
        opacity: 0.6,
    },
});
