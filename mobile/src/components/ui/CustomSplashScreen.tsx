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
import { Colors, Typography } from '../../theme/Theme';

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
                <Animated.View style={[styles.logoRow, animatedStyle]}>
                    {/* "T" Logo Icon */}
                    <Image
                        source={require('../../../assets/teeks_logo_cleaned_1769863142071.png')}
                        style={styles.logoIcon}
                        resizeMode="contain"
                    />
                    {/* "eeks" Text */}
                    <DonnaText style={styles.logoText}>eeks</DonnaText>
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
    logoRow: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    logoIcon: {
        width: 48,
        height: 48,
        marginRight: 4,
    },
    logoText: {
        ...Typography.logo,
        color: Colors.textPrimary,
        fontSize: 42,
        letterSpacing: 2,
    },
});
