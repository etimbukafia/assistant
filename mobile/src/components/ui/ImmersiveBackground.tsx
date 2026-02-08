import React from 'react';
import { StyleSheet, View, ViewStyle, StyleProp } from 'react-native';
import { Colors } from '../../theme/Theme';

interface ImmersiveBackgroundProps {
    children: React.ReactNode;
    style?: StyleProp<ViewStyle>;
}

export const ImmersiveBackground: React.FC<ImmersiveBackgroundProps> = ({ children, style }) => {
    return (
        <View style={[styles.container, style]}>
            <View style={[StyleSheet.absoluteFill, { backgroundColor: Colors.bgBase }]} />
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
