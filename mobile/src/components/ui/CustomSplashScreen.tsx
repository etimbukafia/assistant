import React, { useEffect } from 'react';
import { StyleSheet, View, Image } from 'react-native';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withTiming,
    Easing
} from 'react-native-reanimated';
import { ImmersiveBackground } from './ImmersiveBackground';
import { DonnaText } from './DonnaText';
import { Colors, Typography, Radius } from '../../theme/Theme';

export const CustomSplashScreen = () => {
    const opacity = useSharedValue(0);

    useEffect(() => {
        // Simple, elegant fade in
        opacity.value = withTiming(1, {
            duration: 800,
            easing: Easing.out(Easing.ease)
        });
    }, []);

    const animatedStyle = useAnimatedStyle(() => ({
        opacity: opacity.value,
    }));

    return (
        <ImmersiveBackground style={styles.container}>
            <View style={styles.content}>
                <Animated.View style={[styles.logoContainer, animatedStyle]}>
                    <View style={styles.logoRow}>
                        <View style={styles.interlockContainer}>
                            <DonnaText style={styles.logoT}>T</DonnaText>
                        </View>
                        <DonnaText style={styles.logoText}>EEKS<DonnaText style={styles.logoDot}>.</DonnaText></DonnaText>
                    </View>
                </Animated.View>
            </View>
        </ImmersiveBackground>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    logoContainer: {
        alignItems: 'center',
    },
    logoRow: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    interlockContainer: {
        width: 60,
        height: 60,
        backgroundColor: Colors.accentPrimary, // Auburn
        borderRadius: Radius.sm,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: 10,
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 5,
    },
    logoT: {
        ...Typography.logo,
        fontSize: 40,
        color: '#FFFFFF',
        lineHeight: 48,
    },
    logoText: {
        ...Typography.logo,
        color: Colors.textPrimary,
        fontSize: 48,
        letterSpacing: 4,
    },
    logoDot: {
        color: Colors.accentSecondary, // Copper dot
    },
});
