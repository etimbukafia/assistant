import React from 'react';
import { TouchableOpacity, StyleSheet, Modal, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Spacing } from '../../theme/Theme';
import { useRouter } from 'expo-router';

export function ChatButton() {
    const router = useRouter();

    return (
        <TouchableOpacity
            style={styles.container}
            onPress={() => router.push('/chat')}
            activeOpacity={0.9}
        >
            <View style={styles.iconContainer}>
                <Ionicons name="chatbubbles" size={28} color="#FFFFFF" />
            </View>
        </TouchableOpacity>
    );
}

const styles = StyleSheet.create({
    container: {
        position: 'absolute',
        bottom: 100, // Position above the tab bar
        right: Spacing.lg,
        zIndex: 1000,
        shadowColor: "#000",
        shadowOffset: {
            width: 0,
            height: 4,
        },
        shadowOpacity: 0.30,
        shadowRadius: 4.65,
        elevation: 8,
    },
    iconContainer: {
        width: 64,
        height: 64,
        borderRadius: 32,
        backgroundColor: Colors.accentPrimary,
        justifyContent: 'center',
        alignItems: 'center',
    }
});
