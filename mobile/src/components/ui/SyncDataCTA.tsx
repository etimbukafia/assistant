
import React from 'react';
import { StyleSheet, View, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

export function SyncDataCTA() {
    const router = useRouter();

    return (
        <View style={styles.container}>
            <View style={styles.content}>
                <View style={styles.iconContainer}>
                    <Ionicons name="sync" size={24} color="#FFFFFF" />
                </View>
                <View style={styles.textContainer}>
                    <DonnaText variant="h2" style={styles.title}>Sync your world</DonnaText>
                    <DonnaText style={styles.description}>
                        Connect Gmail & Calendar to see your real life here.
                    </DonnaText>
                </View>
            </View>

            <TouchableOpacity
                style={styles.button}
                onPress={() => router.push('/settings/activate_trial' as any)}
            >
                <DonnaText style={styles.buttonText}>Start 7-Day Free Trial</DonnaText>
                <Ionicons name="arrow-forward" size={16} color={Colors.accentPrimary} />
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        marginHorizontal: Spacing.md,
        marginBottom: Spacing.md,
        shadowColor: Colors.accentPrimary,
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.2,
        shadowRadius: 8,
        elevation: 4,
    },
    content: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: Spacing.md,
        gap: Spacing.md,
    },
    iconContainer: {
        width: 40,
        height: 40,
        borderRadius: Radius.full,
        backgroundColor: 'rgba(255,255,255,0.2)',
        alignItems: 'center',
        justifyContent: 'center',
    },
    textContainer: {
        flex: 1,
    },
    title: {
        color: '#FFFFFF',
        fontSize: 18,
        marginBottom: 2,
    },
    description: {
        color: 'rgba(255,255,255,0.9)',
        fontSize: 14,
        lineHeight: 20,
    },
    button: {
        backgroundColor: '#FFFFFF',
        borderRadius: Radius.full,
        paddingVertical: Spacing.sm,
        paddingHorizontal: Spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.xs,
    },
    buttonText: {
        color: Colors.accentPrimary,
        fontWeight: '600',
        fontSize: 14,
    },
});
