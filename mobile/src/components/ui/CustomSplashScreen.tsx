import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withTiming,
    Easing
} from 'react-native-reanimated';
import { SvgXml } from 'react-native-svg';
import { ImmersiveBackground } from './ImmersiveBackground';

// Teeks wordmark SVG - icon + text
const teeksWordmarkSvg = `
<svg width="600" height="150" viewBox="0 0 600 150" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="text_grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#F9F6F2" />
      <stop offset="100%" stop-color="#FFFFFF" />
    </linearGradient>
  </defs>

  <!-- Icon Part (Mini Interlock) -->
  <g transform="translate(20, 25) scale(0.25)">
    <path d="M80 100C80 88.9543 88.9543 80 100 80H230V150H80V100Z" fill="#7E2E2E"/>
    <path d="M245 80H300C311.046 80 320 88.9543 320 100V150H245V80Z" fill="#D97745"/>
    <path d="M165 165H235V300C235 311.046 226.046 320 215 320H185C173.954 320 165 311.046 165 300V165Z" fill="#7E2E2E"/>
  </g>

  <!-- Wordmark -->
  <text x="130" y="105" font-family="serif" font-weight="bold" font-size="80" fill="url(#text_grad)" letter-spacing="-2">Teeks<tspan fill="#D97745">.</tspan></text>
</svg>
`;

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
                    <SvgXml xml={teeksWordmarkSvg} width={300} height={75} />
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
});
