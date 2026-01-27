import React, { useState, useEffect } from 'react';
import { StyleSheet, View, ScrollView, TouchableOpacity, Switch, TextInput, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { useSettings } from '@/src/hooks/useSettings';

export default function GeneralSettingsScreen() {
    const router = useRouter();
    const { settings, isLoading, updateSetting, isUpdating, isSandbox } = useSettings();

    const [instructions, setInstructions] = useState('');

    useEffect(() => {
        if (settings?.task_detection_instructions !== undefined) {
            setInstructions(settings.task_detection_instructions || '');
        }
    }, [settings?.task_detection_instructions]);

    const handleSaveInstructions = () => {
        if (isSandbox) return; // Don't save in sandbox mode
        if (instructions !== settings?.task_detection_instructions) {
            updateSetting('task_detection_instructions', instructions || null);
        }
    };

    // Header component - reused in loading state
    const Header = () => (
        <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
            </TouchableOpacity>
            <DonnaText style={styles.headerTitle}>General Settings</DonnaText>
            <View style={styles.headerPlaceholder} />
        </View>
    );

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <StatusBar style="dark" />
                <Header />
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                </View>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />
            <Header />

            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* AI Behavior Section */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>AI & AUTOMATION</DonnaText>
                    <View style={styles.sectionCard}>
                        <View style={styles.settingRow}>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Auto-Approve Tasks</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Automatically add AI-detected tasks to your list
                                </DonnaText>
                            </View>
                            <Switch
                                value={settings?.auto_approve_tasks ?? false}
                                onValueChange={(value) => {
                                    if (isSandbox) {
                                        Alert.alert('Demo Mode', 'Settings changes are disabled in demo mode. Connect your email to enable.');
                                        return;
                                    }
                                    updateSetting('auto_approve_tasks', value);
                                }}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating || isSandbox}
                            />
                        </View>

                        <View style={styles.settingRow}>
                            <View style={styles.settingTextContainer}>
                                <DonnaText style={styles.settingTitle}>Quick Reply from Task</DonnaText>
                                <DonnaText style={styles.settingSubtitle}>
                                    Enable AI-drafted replies directly from tasks
                                </DonnaText>
                            </View>
                            <Switch
                                value={settings?.enable_quick_reply_from_task ?? false}
                                onValueChange={(value) => {
                                    if (isSandbox) {
                                        Alert.alert('Demo Mode', 'Settings changes are disabled in demo mode. Connect your email to enable.');
                                        return;
                                    }
                                    updateSetting('enable_quick_reply_from_task', value);
                                }}
                                trackColor={{ true: Colors.success }}
                                thumbColor="#FFF"
                                disabled={isUpdating || isSandbox}
                            />
                        </View>
                    </View>
                </View>

                {/* Task Detection Instructions */}
                <View style={styles.section}>
                    <DonnaText style={styles.sectionLabel}>DETECTION INSTRUCTIONS</DonnaText>
                    <View style={styles.instructionContainer}>
                        <DonnaText style={styles.instructionHint}>
                            Guide Donna on how to identify tasks in your emails. Mention specific keywords, projects, or contexts to watch for.
                        </DonnaText>
                        <TextInput
                            style={styles.instructionInput}
                            multiline
                            numberOfLines={6}
                            placeholder="e.g. Focus on requests from the executive team, follow-ups regarding the Project Phoenix launch..."
                            placeholderTextColor={Colors.textMuted}
                            value={instructions}
                            onChangeText={setInstructions}
                            onBlur={handleSaveInstructions}
                            textAlignVertical="top"
                            editable={!isSandbox}
                        />
                        {isUpdating && (
                            <DonnaText style={styles.savingText}>Saving...</DonnaText>
                        )}
                    </View>
                </View>

                {/* Quick Info */}
                <View style={styles.infoCard}>
                    <Ionicons name="information-circle-outline" size={20} color={Colors.textSecondary} />
                    <DonnaText style={styles.infoText}>
                        These settings directly influence how Donna processes your inbox. Be specific in your instructions for the best results.
                    </DonnaText>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
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
    headerPlaceholder: {
        width: 40,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: Spacing.md,
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
    sectionCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: Colors.border,
    },
    settingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    settingTextContainer: {
        flex: 1,
    },
    settingTitle: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    settingSubtitle: {
        fontSize: 13,
        color: Colors.textMuted,
        marginTop: 1,
    },
    instructionContainer: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    instructionHint: {
        fontSize: 13,
        color: Colors.textSecondary,
        marginBottom: Spacing.md,
        lineHeight: 18,
    },
    instructionInput: {
        backgroundColor: Colors.bgBase,
        borderRadius: Radius.md,
        padding: Spacing.md,
        fontSize: 15,
        color: Colors.textPrimary,
        minHeight: 120,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    savingText: {
        fontSize: 12,
        color: Colors.accentSecondary,
        marginTop: 8,
        textAlign: 'right',
        fontStyle: 'italic',
    },
    infoCard: {
        flexDirection: 'row',
        gap: Spacing.sm,
        padding: Spacing.md,
        backgroundColor: 'rgba(217, 119, 69, 0.05)',
        borderRadius: Radius.lg,
        marginTop: Spacing.md,
    },
    infoText: {
        flex: 1,
        fontSize: 13,
        color: Colors.textSecondary,
        lineHeight: 18,
    },
});
