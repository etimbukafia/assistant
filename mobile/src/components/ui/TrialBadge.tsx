/**
 * TrialBadge - Minimal header badge for trial CTA
 * 
 * Shows after user dismisses the full SyncDataCTA banner.
 * Taps navigate to the trial activation screen.
 */

import React from 'react';
import { StyleSheet, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';
import { useSyncCTA } from '../../context/SyncCTAContext';
import { useAuth } from '../../context/AuthContext';

export function TrialBadge() {
    const router = useRouter();
    const { ctaDismissed } = useSyncCTA();
    const { isSandbox } = useAuth();

    // Only show when CTA is dismissed AND user is in sandbox mode
    if (!ctaDismissed || !isSandbox) {
        return null;
    }

    return (
        <TouchableOpacity
            style={styles.badge}
            onPress={() => router.push('/settings/activate_trial' as any)}
        >
            <DonnaText style={styles.badgeText}>Start Trial</DonnaText>
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
