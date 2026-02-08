import React from 'react';
import { View, StyleSheet, TouchableOpacity, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '../src/theme/Theme';
import { DonnaText } from '../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { ImmersiveBackground } from '../src/components/ui/ImmersiveBackground';

const { width } = Dimensions.get('window');

export default function LoginScreen() {
    const router = useRouter();

    const handleLogin = () => {
        router.push('/auth/welcome' as any);
    };

    return (
        <ImmersiveBackground style={styles.container}>
            <StatusBar style="light" />

            <SafeAreaView style={styles.safeArea}>
                <View style={styles.content}>
                    {/* Brand Section */}
                    <View style={styles.brandContainer}>
                        <View style={styles.logoRow}>
                            <DonnaText style={styles.logoText}>TEEKS</DonnaText>
                        </View>

                        <DonnaText style={styles.slogan}>
                            AI personal assistant for assistants
                        </DonnaText>

                        <View style={styles.divider} />
                    </View>

                    {/* Actions Section */}
                    <View style={styles.actionsContainer}>
                        <TouchableOpacity
                            style={styles.primaryButton}
                            activeOpacity={0.9}
                            onPress={handleLogin}
                        >
                            <DonnaText style={styles.primaryButtonText}>Log in</DonnaText>
                            <DonnaText style={[styles.primaryButtonText, { marginLeft: 8 }]}>→</DonnaText>
                        </TouchableOpacity>
                    </View>
                </View>
            </SafeAreaView>
        </ImmersiveBackground>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    safeArea: {
        flex: 1,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        paddingHorizontal: Spacing.xl,
        paddingBottom: Spacing.xxl,
    },
    brandContainer: {
        alignItems: 'center',
        marginBottom: Spacing.xxl * 2,
    },
    logoRow: {
        flexDirection: 'row',
        marginBottom: Spacing.lg,
        alignItems: 'baseline',
    },
    logoText: {
        ...Typography.logo,
        color: Colors.textPrimary, // White text on dark glass background
        fontSize: 48,
        lineHeight: 68, // Fix clipping
        letterSpacing: 6,
        paddingVertical: 10, // Extra safety for custom font rendering
    },
    slogan: {
        ...Typography.bodyBase,
        letterSpacing: 2,
        color: Colors.textSecondary,
        opacity: 0.8,
        marginBottom: Spacing.lg,
        textAlign: 'center',
        fontSize: 14,
        textTransform: 'uppercase',
    },
    divider: {
        width: 40,
        height: 1,
        backgroundColor: Colors.accentSecondary, // Copper divider
        opacity: 0.8,
        marginTop: Spacing.md,
    },

    actionsContainer: {
        width: '100%',
        alignItems: 'center',
        gap: Spacing.md,
    },
    primaryButton: {
        width: '100%',
        height: 56,
        backgroundColor: Colors.accentPrimary, // Auburn
        borderRadius: Radius.full,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 12,
        elevation: 5,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
    },
    primaryButtonText: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        fontWeight: '600',
        letterSpacing: 1,
        color: '#FFFFFF',
        textTransform: 'uppercase',
    },
});
