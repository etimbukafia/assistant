import React from 'react';
import { StyleSheet, View, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

interface ConnectIntegrationCTAProps {
    integration: 'gmail' | 'calendar';
}

const integrationConfig = {
    gmail: {
        icon: 'mail' as const,
        iconColor: '#EA4335',
        title: 'Connect Gmail',
        description: 'Link your email to start processing messages with AI.',
        buttonText: 'Connect Gmail',
    },
    calendar: {
        icon: 'calendar' as const,
        iconColor: '#4285F4',
        title: 'Connect Calendar',
        description: 'Sync your calendar for smart scheduling and meeting briefings.',
        buttonText: 'Connect Calendar',
    },
};

export function ConnectIntegrationCTA({ integration }: ConnectIntegrationCTAProps) {
    const router = useRouter();
    const config = integrationConfig[integration];

    const handleConnect = () => {
        // Navigate to integration settings screen
        router.push('/settings/integrations' as any);
    };

    return (
        <View style={styles.container}>
            <View style={styles.content}>
                <View style={[styles.iconContainer, { backgroundColor: `${config.iconColor}15` }]}>
                    <Ionicons name={config.icon} size={24} color={config.iconColor} />
                </View>
                <View style={styles.textContainer}>
                    <DonnaText variant="bodyLarge" style={styles.title}>{config.title}</DonnaText>
                    <DonnaText style={styles.description}>{config.description}</DonnaText>
                </View>
            </View>

            <TouchableOpacity style={styles.button} onPress={handleConnect}>
                <DonnaText style={styles.buttonText}>{config.buttonText}</DonnaText>
                <Ionicons name="arrow-forward" size={16} color={Colors.accentPrecision} />
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    content: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: Spacing.md,
        gap: Spacing.md,
    },
    iconContainer: {
        width: 44,
        height: 44,
        borderRadius: Radius.component,
        alignItems: 'center',
        justifyContent: 'center',
    },
    textContainer: {
        flex: 1,
    },
    title: {
        fontWeight: '600',
        marginBottom: 2,
    },
    description: {
        color: Colors.textSecondary,
        fontSize: 13,
        lineHeight: 18,
    },
    button: {
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.full,
        paddingVertical: Spacing.sm,
        paddingHorizontal: Spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.xs,
        borderWidth: 1,
        borderColor: Colors.accentPrecision,
    },
    buttonText: {
        color: Colors.accentPrecision,
        fontWeight: '600',
        fontSize: 14,
    },
});
