import React from 'react';
import { Pressable, StyleSheet, Animated } from 'react-native';
import { Colors, Radius, Spacing } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

interface DonnaButtonProps {
    title: string;
    onPress: () => void;
    variant?: 'primary' | 'secondary' | 'ghost';
    fullWidth?: boolean;
    children?: React.ReactNode;
    style?: any;
    textStyle?: any;
}

export const DonnaButton: React.FC<DonnaButtonProps> = ({
    title,
    onPress,
    variant = 'primary',
    fullWidth = false,
    children,
    style,
    textStyle,
}) => {
    const animatedScale = new Animated.Value(1);

    const onPressIn = () => {
        Animated.spring(animatedScale, {
            toValue: 0.98,
            useNativeDriver: true,
        }).start();
    };

    const onPressOut = () => {
        Animated.spring(animatedScale, {
            toValue: 1,
            useNativeDriver: true,
        }).start();
    };

    const getButtonStyle = () => {
        switch (variant) {
            case 'primary':
                return styles.primary;
            case 'secondary':
                return styles.secondary;
            case 'ghost':
                return styles.ghost;
        }
    };

    const getTextColor = () => {
        if (variant === 'primary') return '#FFFFFF';
        if (variant === 'ghost') return Colors.textMuted;
        return Colors.textPrimary;
    };

    return (
        <Pressable
            onPress={onPress}
            onPressIn={onPressIn}
            onPressOut={onPressOut}
            style={({ pressed }) => [
                styles.base,
                getButtonStyle(),
                fullWidth && styles.fullWidth,
                style,
            ]}
        >
            <Animated.View style={[styles.inner, { transform: [{ scale: animatedScale }] }]}>
                {children}
                <DonnaText
                    variant="bodyBase"
                    color={getTextColor()}
                    style={[styles.text, textStyle]}
                >
                    {title}
                </DonnaText>
            </Animated.View>
        </Pressable>
    );
};

const styles = StyleSheet.create({
    base: {
        paddingVertical: Spacing.md,
        paddingHorizontal: Spacing.lg,
        borderRadius: Radius.component,
        alignItems: 'center',
        justifyContent: 'center',
    },
    fullWidth: {
        width: '100%',
    },
    primary: {
        backgroundColor: Colors.accentPrimary,
    },
    secondary: {
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderColor: Colors.border,
    },
    ghost: {
        backgroundColor: 'transparent',
    },
    text: {
        fontWeight: '600',
    },
    inner: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
    },
});
