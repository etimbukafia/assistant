import React, { useEffect, useState } from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../../src/theme/Theme';
import { DonnaText } from '../../../src/components/ui/DonnaText';

export default function ChooseAccountScreen() {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Simulate loading state often seen in webviews
        const timer = setTimeout(() => {
            setIsLoading(false);
        }, 800);
        return () => clearTimeout(timer);
    }, []);

    const handleSelectAccount = () => {
        // Navigate to consent screen
        router.push('/auth/google/consent' as any);
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Mock Chat/Modal Header look */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()}>
                    <Ionicons name="close" size={24} color="#5f6368" />
                </TouchableOpacity>
                <DonnaText style={styles.urlBar}>accounts.google.com</DonnaText>
                <View style={{ width: 24 }} />
            </View>

            {isLoading ? (
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color="#1a73e8" />
                </View>
            ) : (
                <View style={styles.content}>
                    {/* Google Logo */}
                    <View style={styles.logoContainer}>
                        <DonnaText style={styles.googleLogo}>Google</DonnaText>
                        <DonnaText style={styles.signInText}>Sign in</DonnaText>
                        <DonnaText style={styles.subtitle}>to continue to Donna</DonnaText>
                    </View>

                    {/* Account List */}
                    <View style={styles.accountList}>
                        <TouchableOpacity style={styles.accountItem} onPress={handleSelectAccount}>
                            <View style={[styles.avatar, { backgroundColor: '#8e24aa' }]}>
                                <DonnaText style={styles.avatarText}>J</DonnaText>
                            </View>
                            <View style={styles.accountInfo}>
                                <DonnaText style={styles.name}>Jane Doe</DonnaText>
                                <DonnaText style={styles.email}>jane.doe@example.com</DonnaText>
                            </View>
                        </TouchableOpacity>

                        <View style={styles.divider} />

                        <TouchableOpacity style={styles.accountItem}>
                            <View style={styles.avatar}>
                                <Ionicons name="person-add-outline" size={20} color="#5f6368" />
                            </View>
                            <DonnaText style={styles.addAccountText}>Use another account</DonnaText>
                        </TouchableOpacity>
                    </View>

                    <View style={styles.footer}>
                        <DonnaText style={styles.footerText}>
                            To continue, Google will share your name, email address, and language preference with Donna.
                        </DonnaText>
                    </View>
                </View>
            )}
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF', // Google Webview is white
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: '#e0e0e0',
    },
    urlBar: {
        fontSize: 12,
        color: '#5f6368',
        fontFamily: 'Inter_400Regular',
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    content: {
        flex: 1,
        paddingHorizontal: Spacing.xl,
        alignItems: 'center',
        paddingTop: Spacing.xl * 1.5,
    },
    logoContainer: {
        alignItems: 'center',
        marginBottom: Spacing.xl * 1.5,
    },
    googleLogo: {
        fontSize: 24,
        fontWeight: 'bold', // Product Sans approximation
        color: '#5f6368',
        marginBottom: Spacing.xs,
    },
    signInText: {
        fontSize: 22,
        color: '#202124',
        fontFamily: 'Inter_400Regular',
        marginBottom: Spacing.xs,
    },
    subtitle: {
        fontSize: 16,
        color: '#202124',
        fontFamily: 'Inter_400Regular',
    },
    accountList: {
        width: '100%',
        marginBottom: Spacing.xl,
    },
    accountItem: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingVertical: Spacing.md,
        paddingHorizontal: Spacing.xs,
    },
    avatar: {
        width: 32,
        height: 32,
        borderRadius: 16,
        backgroundColor: '#f1f3f4', // Default grey for add account
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.md,
    },
    avatarText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '500',
    },
    accountInfo: {
        justifyContent: 'center',
    },
    name: {
        fontSize: 14,
        color: '#202124',
        fontWeight: '500',
        fontFamily: 'Inter_400Regular',
    },
    email: {
        fontSize: 12,
        color: '#5f6368',
        fontFamily: 'Inter_400Regular',
    },
    addAccountText: {
        fontSize: 14,
        color: '#202124',
        fontFamily: 'Inter_400Regular',
        fontWeight: '500',
    },
    divider: {
        height: 1,
        backgroundColor: '#e0e0e0',
        width: '100%',
    },
    footer: {
        marginTop: Spacing.xl,
        paddingHorizontal: Spacing.md,
    },
    footerText: {
        fontSize: 12,
        color: '#5f6368',
        textAlign: 'center',
        lineHeight: 18,
        fontFamily: 'Inter_400Regular',
    }
});
