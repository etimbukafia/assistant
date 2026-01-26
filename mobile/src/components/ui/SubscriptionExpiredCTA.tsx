import React from 'react';
import { StyleSheet, View, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

interface SubscriptionExpiredCTAProps {
    tier?: 'trial' | 'pro';
}

export function SubscriptionExpiredCTA({ tier = 'trial' }: SubscriptionExpiredCTAProps) {
    const router = useRouter();

    const title = tier === 'trial' ? 'Trial Expired' : 'Subscription Expired';
    const description = tier === 'trial'
        ? 'Your 7-day trial has ended. Subscribe to keep syncing emails and calendar.'
        : 'Your subscription has expired. Resubscribe to continue syncing.';
    const buttonText = tier === 'trial' ? 'Upgrade to Pro' : 'Resubscribe';

    const handleSubscribe = () => {
        router.push('/settings/subscription' as any);
    };

    return (
        <View style={styles.container}>
            <View style={styles.content}>
                <View style={styles.iconContainer}>
                    <Ionicons name="time-outline" size={24} color={Colors.accentSecondary} />
                </View>
                <View style={styles.textContainer}>
                    <DonnaText variant="bodyLarge" style={styles.title}>{title}</DonnaText>
                    <DonnaText style={styles.description}>{description}</DonnaText>
                </View>
            </View>

            <TouchableOpacity style={styles.button} onPress={handleSubscribe}>
                <DonnaText style={styles.buttonText}>{buttonText}</DonnaText>
                <Ionicons name="arrow-forward" size={16} color="#FFFFFF" />
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
        borderColor: Colors.accentSecondary,
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
        backgroundColor: `${Colors.accentSecondary}15`,
        alignItems: 'center',
        justifyContent: 'center',
    },
    textContainer: {
        flex: 1,
    },
    title: {
        fontWeight: '600',
        color: Colors.accentSecondary,
        marginBottom: 2,
    },
    description: {
        color: Colors.textSecondary,
        fontSize: 13,
        lineHeight: 18,
    },
    button: {
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.full,
        paddingVertical: Spacing.sm,
        paddingHorizontal: Spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.xs,
    },
    buttonText: {
        color: '#FFFFFF',
        fontWeight: '600',
        fontSize: 14,
    },
});
