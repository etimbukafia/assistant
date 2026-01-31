import React from 'react';
import { StyleSheet, View, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors } from '../../theme/Theme';

interface ImmersiveBackgroundProps {
    children: React.ReactNode;
    style?: StyleProp<ViewStyle>;
}

export const ImmersiveBackground: React.FC<ImmersiveBackgroundProps> = ({ children, style }) => {
    return (
        <View style={[styles.container, style]}>
            {/* Base Background Color (Deep Navy) */}
            <View style={[StyleSheet.absoluteFill, { backgroundColor: Colors.bgBase }]} />

            {/* Subtle Gradient Overlay to create depth/glow */}
            <LinearGradient
                colors={[
                    Colors.accentPrimary, // Auburn glow at top-left
                    Colors.bgBase,        // Fade to base
                    Colors.accentPrecision // Teal glow at bottom-right
                ]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={[StyleSheet.absoluteFill, { opacity: 0.4 }]} // Low opacity for subtle effect
            />

            {/* Content Content */}
            <View style={styles.content}>
                {children}
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    content: {
        flex: 1,
    },
});
