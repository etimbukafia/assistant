import React, { useEffect, useState } from 'react';
import { View, StyleSheet, SafeAreaView, TouchableOpacity, ScrollView, Image } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../../src/theme/Theme';
import { DonnaText } from '../../../src/components/ui/DonnaText';

export default function ConsentScreen() {
    const router = useRouter();

    const handleAllow = () => {
        // Navigate to tabs (inbox)
        router.push('/(tabs)' as any);
    };

    const handleCancel = () => {
        router.back();
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Mock Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()}>
                    <Ionicons name="close" size={24} color="#5f6368" />
                </TouchableOpacity>
                <DonnaText style={styles.urlBar}>accounts.google.com</DonnaText>
                <View style={{ width: 24 }} />
            </View>

            <ScrollView contentContainerStyle={styles.content}>
                {/* App Logo & Google Logo */}
                <View style={styles.branding}>
                    <DonnaText style={styles.appName}>Donna</DonnaText>
                    <DonnaText style={styles.wantsAccess}>wants to access your Google Account</DonnaText>
                    <View style={styles.userBadge}>
                        <View style={[styles.avatar, { backgroundColor: '#8e24aa' }]}>
                            <DonnaText style={styles.avatarText}>J</DonnaText>
                        </View>
                        <DonnaText style={styles.email}>jane.doe@example.com</DonnaText>
                    </View>
                </View>

                {/* Permissions List */}
                <View style={styles.permissionsList}>
                    <DonnaText style={styles.sectionTitle}>This will allow Donna to:</DonnaText>

                    <View style={styles.permissionItem}>
                        <Ionicons name="mail-outline" size={24} color="#5f6368" style={styles.permIcon} />
                        <View style={styles.permTextContainer}>
                            <DonnaText style={styles.permTitle}>Read, compose, send, and permanently delete all your email from Gmail</DonnaText>
                        </View>
                        <Ionicons name="information-circle-outline" size={20} color="#5f6368" />
                    </View>

                    <View style={styles.permissionItem}>
                        <Ionicons name="calendar-outline" size={24} color="#5f6368" style={styles.permIcon} />
                        <View style={styles.permTextContainer}>
                            <DonnaText style={styles.permTitle}>See, edit, share, and permanently delete all the calendars you can access using Google Calendar</DonnaText>
                        </View>
                        <Ionicons name="information-circle-outline" size={20} color="#5f6368" />
                    </View>
                </View>

                {/* Trust Info */}
                <View style={styles.trustInfo}>
                    <Ionicons name="shield-checkmark-outline" size={20} color="#5f6368" />
                    <DonnaText style={styles.trustText}>
                        <DonnaText style={{ fontWeight: 'bold' }}>Make sure you trust Donna.</DonnaText> You may be sharing sensitive info with this site or app. <DonnaText style={{ color: '#1a73e8' }}>Learn about how Donna handles your data.</DonnaText>
                    </DonnaText>
                </View>
            </ScrollView>

            {/* Sticky Actions Footer */}
            <View style={styles.actionsFooter}>
                <TouchableOpacity style={styles.cancelButton} onPress={handleCancel}>
                    <DonnaText style={styles.cancelText}>Cancel</DonnaText>
                </TouchableOpacity>

                <TouchableOpacity style={styles.allowButton} onPress={handleAllow}>
                    <DonnaText style={styles.allowText}>Allow</DonnaText>
                </TouchableOpacity>
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#FFFFFF',
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
    content: {
        paddingHorizontal: Spacing.lg,
        paddingBottom: 100, // Space for footer
    },
    branding: {
        alignItems: 'center',
        marginTop: Spacing.xl,
        marginBottom: Spacing.xl,
    },
    appName: {
        fontSize: 24,
        fontFamily: 'PlayfairDisplay_600SemiBold',
        color: '#202124',
        marginBottom: Spacing.xs,
    },
    wantsAccess: {
        fontSize: 16,
        color: '#202124',
        fontFamily: 'Inter_400Regular',
        marginBottom: Spacing.lg,
    },
    userBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: Spacing.xs,
        paddingRight: Spacing.md,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: '#e0e0e0',
    },
    avatar: {
        width: 24,
        height: 24,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.sm,
    },
    avatarText: {
        color: '#FFFFFF',
        fontSize: 12,
        fontWeight: 'bold',
    },
    email: {
        fontSize: 12,
        color: '#3c4043',
        fontFamily: 'Inter_400Regular',
        fontWeight: '500',
    },
    permissionsList: {
        marginBottom: Spacing.xl,
    },
    sectionTitle: {
        fontSize: 16,
        color: '#202124',
        fontWeight: '500',
        marginBottom: Spacing.lg,
        fontFamily: 'Inter_400Regular',
    },
    permissionItem: {
        flexDirection: 'row',
        marginBottom: Spacing.lg,
    },
    permIcon: {
        marginRight: Spacing.md,
        marginTop: 2,
    },
    permTextContainer: {
        flex: 1,
        marginRight: Spacing.sm,
    },
    permTitle: {
        fontSize: 14,
        color: '#3c4043',
        lineHeight: 20,
        fontFamily: 'Inter_400Regular',
    },
    trustInfo: {
        flexDirection: 'row',
        padding: Spacing.md,
        backgroundColor: '#f8f9fa',
        borderRadius: 8,
    },
    trustText: {
        flex: 1,
        fontSize: 12,
        color: '#5f6368',
        marginLeft: Spacing.sm,
        lineHeight: 18,
        fontFamily: 'Inter_400Regular',
    },
    actionsFooter: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        flexDirection: 'row',
        justifyContent: 'flex-end',
        padding: Spacing.md,
        backgroundColor: '#FFFFFF',
        borderTopWidth: 1,
        borderTopColor: '#e0e0e0',
    },
    cancelButton: {
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.sm,
        borderRadius: 4,
        marginRight: Spacing.sm,
    },
    cancelText: {
        color: '#1a73e8',
        fontWeight: '500',
        fontSize: 14,
        fontFamily: 'Inter_400Regular',
    },
    allowButton: {
        paddingHorizontal: Spacing.xl,
        paddingVertical: Spacing.sm,
        backgroundColor: '#1a73e8',
        borderRadius: 4,
    },
    allowText: {
        color: '#FFFFFF',
        fontWeight: '500',
        fontSize: 14,
        fontFamily: 'Inter_400Regular',
    }
});
