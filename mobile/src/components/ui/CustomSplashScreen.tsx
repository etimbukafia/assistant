import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withTiming,
    Easing
} from 'react-native-reanimated';
import { TeeksWordmark } from './TeeksWordmark';
import { ImmersiveBackground } from './ImmersiveBackground';
import { Colors } from '../../theme/Theme';

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
                    <TeeksWordmark width={300} height={75} color={Colors.accentPrimary} />
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
