import React from 'react';
import { View, StyleSheet, TouchableOpacity, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '../src/theme/Theme';
import { DonnaText } from '../src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';

const { width } = Dimensions.get('window');

export default function LoginScreen() {
    const router = useRouter();

    const handleLogin = () => {
        router.push('/auth/welcome' as any);
    };



    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            <View style={styles.content}>
                {/* Brand Section */}
                <View style={styles.brandContainer}>
                    <View style={styles.logoRow}>
                        <DonnaText style={styles.logoText}>CORT</DonnaText>
                        <DonnaText style={[styles.logoText, { color: Colors.accentPrimary }]}>A</DonnaText>
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
                    </TouchableOpacity>
                </View>
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
        paddingHorizontal: Spacing.xl,
        paddingBottom: Spacing.xxl, // visual balance
    },
    brandContainer: {
        alignItems: 'center',
        marginBottom: Spacing.xxl * 1.5,
    },
    logoRow: {
        flexDirection: 'row',
        marginBottom: Spacing.lg,
        alignItems: 'baseline',
    },
    logoText: {
        ...Typography.logo,
        color: Colors.textPrimary,
        lineHeight: 60,
    },
    slogan: {
        ...Typography.bodyBase,
        letterSpacing: 1.5,
        color: Colors.textPrimary,
        opacity: 0.9,
        marginBottom: Spacing.lg,
        textAlign: 'center',
        fontFamily: 'Inter_400Regular',
    },
    divider: {
        width: 40,
        height: 1,
        backgroundColor: Colors.accentPrimary,
        opacity: 0.5,
        marginBottom: Spacing.lg,
    },

    actionsContainer: {
        width: '100%',
        alignItems: 'center',
        gap: Spacing.md,
    },
    primaryButton: {
        width: '100%',
        height: 56,
        backgroundColor: Colors.accentPrimary,
        borderRadius: Radius.full, // Pill shape
        justifyContent: 'center',
        alignItems: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 5,
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
