import React, { useMemo } from 'react';
import { StyleSheet, View, ScrollView, SafeAreaView, TouchableOpacity } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Radius } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import demoData from '@/src/data/demo_state.json';
import { Message } from '@/src/types/api';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { InlineTaskItem } from '@/src/components/ui/InlineTaskItem';
import { useChat } from '@/src/context/ChatContext';

export default function MessageDetailScreen() {
    const { id } = useLocalSearchParams();
    const router = useRouter();
    const { openChat } = useChat(); // Global chat trigger

    // Mock Data Fetch
    const message = useMemo(() => {
        const messages = demoData.messages as unknown as Message[];
        return messages.find(m => m.id.toString() === id);
    }, [id]);

    if (!message) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.errorContainer}>
                    <DonnaText>Message not found</DonnaText>
                </View>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar style="dark" />

            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
                </TouchableOpacity>
                <View style={styles.headerActions}>
                    {/* Chat Trigger - Summons Donna */}
                    <TouchableOpacity
                        style={styles.actionButton}
                        onPress={openChat}
                    >
                        <Ionicons name="sparkles" size={22} color={Colors.accentSecondary} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.actionButton}>
                        <Ionicons name="archive-outline" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.actionButton}>
                        <Ionicons name="trash-outline" size={24} color={Colors.textPrimary} />
                    </TouchableOpacity>
                </View>
            </View>

            <ScrollView contentContainerStyle={styles.content}>
                {/* Subject & Meta */}
                <DonnaText variant="h2" style={styles.subject}>{message.subject}</DonnaText>

                <View style={styles.metaContainer}>
                    <View style={styles.senderAvatar}>
                        <DonnaText style={styles.avatarText}>{message.sender[0]}</DonnaText>
                    </View>
                    <View>
                        <DonnaText variant="labelSmall" color={Colors.textPrimary}>{message.sender}</DonnaText>
                        <DonnaText variant="caption">
                            {formatDistanceToNow(parseISO(message.received_at), { addSuffix: true })} • to me
                        </DonnaText>
                    </View>
                </View>

                {/* AI Summary */}
                {message.summary && (
                    <View style={styles.summaryBox}>
                        <View style={styles.summaryHeader}>
                            <Ionicons name="sparkles" size={16} color={Colors.accentPrecision} />
                            <DonnaText variant="labelSmall" color={Colors.accentPrecision} style={styles.summaryLabel}>
                                DONNA'S SUMMARY
                            </DonnaText>
                        </View>
                        <DonnaText variant="bodyBase" style={styles.summaryText}>
                            {message.summary}
                        </DonnaText>
                    </View>
                )}

                {/* Inline Tasks */}
                {message.tasks && message.tasks.length > 0 && (
                    <View style={styles.tasksContainer}>
                        <DonnaText variant="overline" style={styles.sectionTitle}>ACTIONS & INTELLIGENCE</DonnaText>
                        {message.tasks.map(task => (
                            <InlineTaskItem
                                key={task.id}
                                task={task}
                                onUpdate={() => { }} // Mock update
                            />
                        ))}
                    </View>
                )}

                {/* Body */}
                <View style={styles.bodyContainer}>
                    <DonnaText variant="bodyBase" style={styles.bodyText}>
                        {message.body}
                    </DonnaText>
                </View>
            </ScrollView>

            {/* Bottom Action Bar */}
            <View style={styles.bottomBar}>
                <TouchableOpacity style={styles.replyButton}>
                    <Ionicons name="return-up-back" size={20} color="#FFF" />
                    <DonnaText style={styles.replyButtonText}>Reply</DonnaText>
                </TouchableOpacity>
                {message.scheduling_intent && (
                    <TouchableOpacity style={[styles.replyButton, { backgroundColor: Colors.accentSecondary }]}>
                        <Ionicons name="calendar" size={20} color="#FFF" />
                        <DonnaText style={styles.replyButtonText}>Schedule</DonnaText>
                    </TouchableOpacity>
                )}
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    errorContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    backButton: {
        padding: Spacing.xs,
    },
    headerActions: {
        flexDirection: 'row',
        gap: Spacing.md,
    },
    actionButton: {
        padding: Spacing.xs,
    },
    content: {
        padding: Spacing.md,
        paddingBottom: 100,
    },
    subject: {
        marginBottom: Spacing.md,
    },
    metaContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: Spacing.lg,
    },
    senderAvatar: {
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: Colors.border,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: Spacing.sm,
    },
    avatarText: {
        fontSize: 18,
        fontWeight: 'bold',
        color: Colors.textSecondary,
    },
    summaryBox: {
        backgroundColor: 'rgba(30, 58, 138, 0.05)',
        padding: Spacing.md,
        borderRadius: Radius.surface,
        marginBottom: Spacing.lg,
        borderLeftWidth: 3,
        borderLeftColor: Colors.accentPrecision,
    },
    summaryHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        marginBottom: Spacing.xs,
    },
    summaryLabel: {
        fontWeight: 'bold',
    },
    summaryText: {
        fontStyle: 'italic',
        lineHeight: 24,
    },
    tasksContainer: {
        marginBottom: Spacing.lg,
    },
    sectionTitle: {
        marginBottom: Spacing.sm,
        marginLeft: Spacing.xs,
    },
    bodyContainer: {
        paddingTop: Spacing.md,
    },
    bodyText: {
        lineHeight: 24,
        color: Colors.textPrimary,
    },
    bottomBar: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: Colors.bgElevated,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
        padding: Spacing.md,
        paddingBottom: Spacing.xl, // Safe area
        flexDirection: 'row',
        gap: Spacing.md,
    },
    replyButton: {
        flex: 1,
        backgroundColor: Colors.textPrimary,
        borderRadius: Radius.full,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        paddingVertical: Spacing.md,
        gap: Spacing.sm,
    },
    replyButtonText: {
        color: '#FFFFFF',
        fontWeight: '600',
        fontSize: 16,
    },
});
