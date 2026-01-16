import React from 'react';
import { StyleSheet, View, SafeAreaView } from 'react-native';
import { Colors, Spacing, Typography } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';

export default function ChatScreen() {
    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="light" />
            <View style={styles.content}>
                <View style={styles.iconCircle}>
                    <Ionicons name="chatbubbles-outline" size={48} color={Colors.accentSecondary} />
                </View>
                <DonnaText style={styles.title}>Donna AI</DonnaText>
                <DonnaText style={styles.subtitle}>
                    Have a natural conversation with your executive memory.
                </DonnaText>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.xl,
    },
    iconCircle: {
        width: 100,
        height: 100,
        borderRadius: 50,
        backgroundColor: 'rgba(217, 119, 69, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.xl,
    },
    title: {
        ...Typography.h2,
        color: Colors.textPrimary,
        marginBottom: Spacing.md,
        textAlign: 'center',
    },
    subtitle: {
        ...Typography.bodyBase,
        color: Colors.textMuted,
        textAlign: 'center',
        lineHeight: 24,
    },
});
