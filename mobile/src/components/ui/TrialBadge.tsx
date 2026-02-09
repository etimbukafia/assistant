/**
 * TrialBadge - Minimal header badge for subscription status
 *
 * Shows days remaining in trial or upgrade prompt.
 */

import React from 'react';
import { StyleSheet, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';
import { useAuth } from '../../context/AuthContext';

export function TrialBadge() {
    const router = useRouter();
    const { isActive, subscriptionTier, daysRemaining } = useAuth();

    // Show badge when on trial with days remaining
    if (subscriptionTier !== 'trial' || !isActive) {
        return null;
    }

    return (
        <TouchableOpacity
            style={styles.badge}
            onPress={() => router.push('/settings/subscription' as any)}
        >
            <DonnaText style={styles.badgeText}>
                {daysRemaining} day{daysRemaining !== 1 ? 's' : ''} left
            </DonnaText>
        </TouchableOpacity>
    );
}

const styles = StyleSheet.create({
    badge: {
        backgroundColor: Colors.accentPrimary,
        paddingHorizontal: Spacing.sm,
        paddingVertical: Spacing.xs - 2,
        borderRadius: Radius.full,
    },
    badgeText: {
        color: '#FFFFFF',
        fontSize: 11,
        fontWeight: '600',
    },
});
