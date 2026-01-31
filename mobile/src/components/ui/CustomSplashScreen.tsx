import React, { useEffect } from 'react';
import { StyleSheet, View, Image } from 'react-native';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withRepeat,
    withSequence,
    withTiming,
    Easing
} from 'react-native-reanimated';
import { ImmersiveBackground } from './ImmersiveBackground';
import { DonnaText } from './DonnaText';
import { Colors, Spacing } from '../../theme/Theme';

export const CustomSplashScreen = () => {
    const scale = useSharedValue(0.9);
    const opacity = useSharedValue(0);

    useEffect(() => {
        // Fade in
        opacity.value = withTiming(1, { duration: 800 });

        // Gentle breathing animation
        scale.value = withRepeat(
            withSequence(
                withTiming(1, { duration: 1500, easing: Easing.inOut(Easing.ease) }),
                withTiming(0.95, { duration: 1500, easing: Easing.inOut(Easing.ease) })
            ),
            -1,
            true
        );
    }, []);

    const animatedStyle = useAnimatedStyle(() => ({
        transform: [{ scale: scale.value }],
        opacity: opacity.value,
    }));

    return (
        <ImmersiveBackground style={styles.container}>
            <View style={styles.content}>
                <Animated.View style={[styles.logoContainer, animatedStyle]}>
                    <Image
                        source={require('../../../assets/images/teeks-brand-logo.png')}
                        style={styles.logo}
                        resizeMode="contain"
                    />
                </Animated.View>

                <Animated.View style={{ opacity: opacity }}>
                    <DonnaText style={styles.tagline}>
                        AI personal assistant for assistants
                    </DonnaText>
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
        marginBottom: Spacing.xl,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.3,
        shadowRadius: 20,
    },
    logo: {
        width: 180,
        height: 180,
    },
    tagline: {
        fontFamily: 'Inter_400Regular',
        fontSize: 14,
        color: Colors.textSecondary,
        letterSpacing: 2,
        textTransform: 'uppercase',
        opacity: 0.8,
    },
});
