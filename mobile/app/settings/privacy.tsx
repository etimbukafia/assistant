import React, { useState } from 'react';
import {
    StyleSheet,
    View,
    ScrollView,
    TouchableOpacity,
    Alert,
    ActivityIndicator,
    TextInput,
    Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from '@/src/context/AuthContext';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { exportUserData, revokeGmailAccess, deleteAllData } from '@/src/services/privacy';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';

interface ActionCardProps {
    icon: string;
    iconColor: string;
    title: string;
    description: string;
    buttonText: string;
    buttonColor?: string;
    isLoading?: boolean;
    onPress: () => void;
    destructive?: boolean;
}

const ActionCard: React.FC<ActionCardProps> = ({
    icon,
    iconColor,
    title,
    description,
    buttonText,
    buttonColor = Colors.accentPrimary,
    isLoading,
    onPress,
    destructive,
}) => (
    <View style={styles.actionCard}>
        <View style={[styles.iconContainer, { backgroundColor: iconColor + '15' }]}>
            <Ionicons name={icon as any} size={24} color={iconColor} />
        </View>
        <View style={styles.actionContent}>
            <DonnaText style={styles.actionTitle}>{title}</DonnaText>
            <DonnaText style={styles.actionDescription}>{description}</DonnaText>
            <TouchableOpacity
                style={[
                    styles.actionButton,
                    { backgroundColor: destructive ? 'transparent' : buttonColor },
                    destructive && styles.destructiveButton,
                    isLoading && styles.buttonDisabled,
                ]}
                onPress={onPress}
                disabled={isLoading}
            >
                {isLoading ? (
                    <ActivityIndicator size="small" color={destructive ? Colors.error : '#FFF'} />
                ) : (
                    <DonnaText style={[
                        styles.actionButtonText,
                        destructive && styles.destructiveButtonText
                    ]}>
                        {buttonText}
                    </DonnaText>
                )}
            </TouchableOpacity>
        </View>
    </View>
);

export default function PrivacyScreen() {
    const router = useRouter();
    const { signOut } = useAuth();
    const queryClient = useQueryClient();

    // Delete confirmation modal state
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [deleteConfirmText, setDeleteConfirmText] = useState('');

    // Export mutation
    const exportMutation = useMutation({
        mutationFn: exportUserData,
        onSuccess: async (data) => {
            try {
                // Save to file and share using SDK 54 API
                const fileName = `teeks_export_${new Date().toISOString().split('T')[0]}.json`;
                const file = new File(Paths.cache, fileName);
                file.write(JSON.stringify(data, null, 2));

                if (await Sharing.isAvailableAsync()) {
                    await Sharing.shareAsync(file.uri, {
                        mimeType: 'application/json',
                        dialogTitle: 'Export Your Data',
                    });
                } else {
                    Alert.alert('Success', 'Your data has been exported successfully.');
                }
            } catch (err) {
                Alert.alert('Error', 'Failed to save export file.');
            }
        },
        onError: (err: any) => {
            Alert.alert('Error', err.response?.data?.detail || 'Failed to export data. Please try again.');
        },
    });

    // Revoke Gmail mutation
    const revokeMutation = useMutation({
        mutationFn: revokeGmailAccess,
        onSuccess: () => {
            queryClient.invalidateQueries();
            Alert.alert(
                'Gmail Disconnected',
                'Your Gmail access has been revoked. All processed email data has been deleted.',
                [{ text: 'OK', onPress: () => router.replace('/login') }]
            );
        },
        onError: (err: any) => {
            Alert.alert('Error', err.response?.data?.detail || 'Failed to revoke access. Please try again.');
        },
    });

    // Delete all data mutation
    const deleteMutation = useMutation({
        mutationFn: deleteAllData,
        onSuccess: async () => {
            setShowDeleteModal(false);
            await signOut();
            Alert.alert(
                'Account Deleted',
                'All your data has been permanently deleted.',
                [{ text: 'OK', onPress: () => router.replace('/login') }]
            );
        },
        onError: (err: any) => {
            Alert.alert('Error', err.response?.data?.detail || 'Failed to delete data. Please try again.');
        },
    });

    const handleExport = () => {
        Alert.alert(
            'Export Your Data',
            'This will download a copy of all your data stored by Teeks, including messages, tasks, preferences, and more.',
            [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Export', onPress: () => exportMutation.mutate() },
            ]
        );
    };

    const handleRevokeGmail = () => {
        Alert.alert(
            'Revoke Gmail Access',
            'This will disconnect your Gmail account and delete all processed email data.\n\nYour settings and preferences will be kept. You can reconnect anytime.',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Revoke Access',
                    style: 'destructive',
                    onPress: () => revokeMutation.mutate(),
                },
            ]
        );
    };

    const handleDeleteConfirm = () => {
        if (deleteConfirmText.toLowerCase() === 'delete') {
            deleteMutation.mutate();
        } else {
            Alert.alert('Error', 'Please type DELETE to confirm.');
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <DonnaText style={styles.headerTitle}>Data & Privacy</DonnaText>
                <View style={styles.placeholder} />
            </View>

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Introduction */}
                <View style={styles.introSection}>
                    <DonnaText style={styles.introText}>
                        You have full control over your data. Export, disconnect, or delete at any time.
                    </DonnaText>
                </View>

                {/* Your Data Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>YOUR DATA</DonnaText>
                    <ActionCard
                        icon="download-outline"
                        iconColor={Colors.accentSecondary}
                        title="Export My Data"
                        description="Download a complete copy of all your data stored by Teeks, including messages, tasks, calendar events, preferences, and more."
                        buttonText="Download Export"
                        buttonColor={Colors.accentSecondary}
                        isLoading={exportMutation.isPending}
                        onPress={handleExport}
                    />
                </View>

                {/* Connected Accounts Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>CONNECTED ACCOUNTS</DonnaText>
                    <ActionCard
                        icon="mail-outline"
                        iconColor={Colors.accentPrecision}
                        title="Revoke Gmail Access"
                        description="Disconnect your Gmail account and delete all processed email data. Your settings will be preserved."
                        buttonText="Disconnect Gmail"
                        isLoading={revokeMutation.isPending}
                        onPress={handleRevokeGmail}
                        destructive
                    />
                </View>

                {/* Danger Zone Section */}
                <View style={styles.section}>
                    <DonnaText style={[styles.sectionLabel, { color: Colors.error }]}>DANGER ZONE</DonnaText>
                    <View style={styles.dangerCard}>
                        <View style={[styles.iconContainer, { backgroundColor: Colors.error + '15' }]}>
                            <Ionicons name="trash-outline" size={24} color={Colors.error} />
                        </View>
                        <View style={styles.actionContent}>
                            <DonnaText style={styles.actionTitle}>Delete All Data</DonnaText>
                            <DonnaText style={styles.actionDescription}>
                                Permanently delete your account and all associated data. This action cannot be undone.
                            </DonnaText>
                            <TouchableOpacity
                                style={[styles.dangerButton, deleteMutation.isPending && styles.buttonDisabled]}
                                onPress={() => setShowDeleteModal(true)}
                                disabled={deleteMutation.isPending}
                            >
                                <DonnaText style={styles.dangerButtonText}>Delete My Account</DonnaText>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>

                {/* Legal Links */}
                <View style={styles.linksSection}>
                    <TouchableOpacity style={styles.link}>
                        <DonnaText style={styles.linkText}>Privacy Policy</DonnaText>
                        <Ionicons name="open-outline" size={16} color={Colors.textMuted} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.link}>
                        <DonnaText style={styles.linkText}>Terms of Service</DonnaText>
                        <Ionicons name="open-outline" size={16} color={Colors.textMuted} />
                    </TouchableOpacity>
                </View>
            </ScrollView>

            {/* Delete Confirmation Modal */}
            <Modal
                visible={showDeleteModal}
                transparent
                animationType="fade"
                onRequestClose={() => setShowDeleteModal(false)}
            >
                <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                        <View style={styles.modalIconContainer}>
                            <Ionicons name="warning" size={32} color={Colors.error} />
                        </View>
                        <DonnaText style={styles.modalTitle}>Delete All Data?</DonnaText>
                        <DonnaText style={styles.modalDescription}>
                            This will permanently delete:{'\n'}
                            • All messages and summaries{'\n'}
                            • Tasks and reminders{'\n'}
                            • Calendar events{'\n'}
                            • Preferences and memory{'\n'}
                            • Your account settings
                        </DonnaText>
                        <DonnaText style={styles.modalWarning}>
                            This action is irreversible.
                        </DonnaText>
                        <DonnaText style={styles.confirmLabel}>
                            Type DELETE to confirm:
                        </DonnaText>
                        <TextInput
                            style={styles.confirmInput}
                            value={deleteConfirmText}
                            onChangeText={setDeleteConfirmText}
                            placeholder="DELETE"
                            placeholderTextColor={Colors.textMuted}
                            autoCapitalize="characters"
                        />
                        <View style={styles.modalButtons}>
                            <TouchableOpacity
                                style={styles.cancelButton}
                                onPress={() => {
                                    setShowDeleteModal(false);
                                    setDeleteConfirmText('');
                                }}
                            >
                                <DonnaText style={styles.cancelButtonText}>Cancel</DonnaText>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[
                                    styles.confirmDeleteButton,
                                    deleteConfirmText.toLowerCase() !== 'delete' && styles.buttonDisabled,
                                    deleteMutation.isPending && styles.buttonDisabled,
                                ]}
                                onPress={handleDeleteConfirm}
                                disabled={deleteConfirmText.toLowerCase() !== 'delete' || deleteMutation.isPending}
                            >
                                {deleteMutation.isPending ? (
                                    <ActivityIndicator size="small" color="#FFF" />
                                ) : (
                                    <DonnaText style={styles.confirmDeleteButtonText}>Delete Forever</DonnaText>
                                )}
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </Modal>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    backButton: {
        padding: Spacing.xs,
    },
    headerTitle: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    placeholder: {
        width: 40,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 60,
    },
    introSection: {
        marginBottom: Spacing.xl,
    },
    introText: {
        fontSize: 15,
        color: Colors.textSecondary,
        lineHeight: 22,
        textAlign: 'center',
    },
    section: {
        marginBottom: Spacing.xl,
    },
    sectionLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
        marginLeft: Spacing.xs,
    },
    actionCard: {
        flexDirection: 'row',
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        gap: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    dangerCard: {
        flexDirection: 'row',
        backgroundColor: Colors.error + '08',
        borderRadius: Radius.lg,
        padding: Spacing.md,
        gap: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.error + '30',
    },
    iconContainer: {
        width: 48,
        height: 48,
        borderRadius: 12,
        justifyContent: 'center',
        alignItems: 'center',
    },
    actionContent: {
        flex: 1,
    },
    actionTitle: {
        fontSize: 16,
        fontWeight: '600',
        color: Colors.textPrimary,
        marginBottom: 4,
    },
    actionDescription: {
        fontSize: 13,
        color: Colors.textMuted,
        lineHeight: 18,
        marginBottom: Spacing.sm,
    },
    actionButton: {
        alignSelf: 'flex-start',
        paddingVertical: 8,
        paddingHorizontal: 16,
        borderRadius: Radius.full,
    },
    buttonDisabled: {
        opacity: 0.5,
    },
    actionButtonText: {
        color: '#FFF',
        fontSize: 14,
        fontWeight: '600',
    },
    destructiveButton: {
        borderWidth: 1,
        borderColor: Colors.error,
    },
    destructiveButtonText: {
        color: Colors.error,
    },
    dangerButton: {
        alignSelf: 'flex-start',
        paddingVertical: 8,
        paddingHorizontal: 16,
        borderRadius: Radius.full,
        backgroundColor: Colors.error,
    },
    dangerButtonText: {
        color: '#FFF',
        fontSize: 14,
        fontWeight: '600',
    },
    linksSection: {
        marginTop: Spacing.lg,
        gap: Spacing.sm,
    },
    link: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.xs,
        paddingVertical: Spacing.sm,
    },
    linkText: {
        fontSize: 14,
        color: Colors.textMuted,
    },
    // Modal styles
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.lg,
    },
    modalContent: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.xl,
        width: '100%',
        maxWidth: 360,
    },
    modalIconContainer: {
        width: 64,
        height: 64,
        borderRadius: 32,
        backgroundColor: Colors.error + '15',
        justifyContent: 'center',
        alignItems: 'center',
        alignSelf: 'center',
        marginBottom: Spacing.md,
    },
    modalTitle: {
        fontSize: 20,
        fontWeight: '700',
        color: Colors.textPrimary,
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    modalDescription: {
        fontSize: 14,
        color: Colors.textSecondary,
        lineHeight: 20,
        marginBottom: Spacing.md,
    },
    modalWarning: {
        fontSize: 14,
        fontWeight: '600',
        color: Colors.error,
        textAlign: 'center',
        marginBottom: Spacing.lg,
    },
    confirmLabel: {
        fontSize: 13,
        color: Colors.textMuted,
        marginBottom: Spacing.xs,
    },
    confirmInput: {
        backgroundColor: Colors.bgBase,
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.component,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        fontSize: 16,
        color: Colors.textPrimary,
        marginBottom: Spacing.lg,
        textAlign: 'center',
    },
    modalButtons: {
        flexDirection: 'row',
        gap: Spacing.sm,
    },
    cancelButton: {
        flex: 1,
        paddingVertical: 12,
        borderRadius: Radius.component,
        backgroundColor: Colors.bgBase,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: Colors.border,
    },
    cancelButtonText: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    confirmDeleteButton: {
        flex: 1,
        paddingVertical: 12,
        borderRadius: Radius.component,
        backgroundColor: Colors.error,
        alignItems: 'center',
    },
    confirmDeleteButtonText: {
        fontSize: 15,
        fontWeight: '600',
        color: '#FFF',
    },
});
