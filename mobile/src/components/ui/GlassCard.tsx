import React from 'react';
import { StyleSheet, ViewStyle, StyleProp, View } from 'react-native';
import { BlurView } from 'expo-blur';
import { Glass } from '../../theme/Glass';

type GlassVariant = 'default' | 'heavy' | 'light' | 'warm';

interface GlassCardProps {
    children: React.ReactNode;
    style?: StyleProp<ViewStyle>;
    variant?: GlassVariant;
    intensity?: number;
}

export const GlassCard: React.FC<GlassCardProps> = ({
    children,
    style,
    variant = 'default',
    intensity
}) => {
    const glassStyle = Glass[variant];

    // Determine blur intensity based on variant if not explicitly provided
    const defaultIntensity = variant === 'heavy' ? 40 : variant === 'light' ? 10 : 20;
    const finalIntensity = intensity ?? defaultIntensity;

    return (
        <BlurView
            intensity={finalIntensity}
            tint="dark"
            style={[styles.container, glassStyle, style]}
        >
            {children}
        </BlurView>
    );
};

const styles = StyleSheet.create({
    container: {
        overflow: 'hidden',
        borderRadius: 20, // Common radius for glass cards (xl)
    },
});
