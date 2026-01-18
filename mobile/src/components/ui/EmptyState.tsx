import React from 'react';
import { StyleSheet, View, TouchableOpacity, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

type EmptyStateVariant = 'inbox' | 'tasks' | 'calendar' | 'chat' | 'search' | 'generic';

interface EmptyStateProps {
    variant?: EmptyStateVariant;
    title?: string;
    message?: string;
    actionLabel?: string;
    onAction?: () => void;
    icon?: string;
    style?: ViewStyle;
}

const VARIANTS: Record<EmptyStateVariant, { icon: string; title: string; message: string; color: string }> = {
    inbox: {
        icon: 'mail-open-outline',
        title: 'Inbox Zero!',
        message: 'You\'ve cleared your inbox. Enjoy the calm. ✨',
        color: Colors.success,
    },
    tasks: {
        icon: 'checkbox-outline',
        title: 'All Done!',
        message: 'No tasks on your plate. Take a break or add something new.',
        color: Colors.success,
    },
    calendar: {
        icon: 'calendar-outline',
        title: 'No Upcoming Events',
        message: 'Your calendar is clear. Sync to see your meetings.',
        color: Colors.accentPrecision,
    },
    chat: {
        icon: 'chatbubbles-outline',
        title: 'Start a Conversation',
        message: 'Ask Donna anything about your email, tasks, or schedule.',
        color: Colors.accentSecondary,
    },
    search: {
        icon: 'search-outline',
        title: 'No Results Found',
        message: 'Try adjusting your search or filters.',
        color: Colors.textMuted,
    },
    generic: {
        icon: 'document-outline',
        title: 'Nothing Here Yet',
        message: 'Content will appear here once available.',
        color: Colors.textMuted,
    },
};

export const EmptyState: React.FC<EmptyStateProps> = ({
    variant = 'generic',
    title,
    message,
    actionLabel,
    onAction,
    icon,
    style,
}) => {
    const config = VARIANTS[variant];
    const displayIcon = icon || config.icon;
    const displayTitle = title || config.title;
    const displayMessage = message || config.message;

    return (
        <View style={[styles.container, style]}>
            <View style={[styles.iconCircle, { backgroundColor: config.color + '12' }]}>
                <Ionicons name={displayIcon as any} size={48} color={config.color} />
            </View>

            <DonnaText variant="h2" style={styles.title}>
                {displayTitle}
            </DonnaText>

            <DonnaText style={styles.message}>
                {displayMessage}
            </DonnaText>

            {actionLabel && onAction && (
                <TouchableOpacity style={styles.actionButton} onPress={onAction}>
                    <DonnaText style={styles.actionText}>{actionLabel}</DonnaText>
                </TouchableOpacity>
            )}
        </View>
    );
};

// Specific empty states with preset styling
export const InboxZeroState: React.FC<{ style?: ViewStyle }> = ({ style }) => (
    <EmptyState variant="inbox" style={style} />
);

export const TasksCompleteState: React.FC<{ onAddTask?: () => void; style?: ViewStyle }> = ({ onAddTask, style }) => (
    <EmptyState
        variant="tasks"
        actionLabel={onAddTask ? "Add a Task" : undefined}
        onAction={onAddTask}
        style={style}
    />
);

export const NoEventsState: React.FC<{ onSync?: () => void; style?: ViewStyle }> = ({ onSync, style }) => (
    <EmptyState
        variant="calendar"
        actionLabel={onSync ? "Sync Calendar" : undefined}
        onAction={onSync}
        style={style}
    />
);

export const StartChatState: React.FC<{ onStart?: () => void; style?: ViewStyle }> = ({ onStart, style }) => (
    <EmptyState
        variant="chat"
        actionLabel={onStart ? "Start Chatting" : undefined}
        onAction={onStart}
        style={style}
    />
);

export const NoSearchResultsState: React.FC<{ style?: ViewStyle }> = ({ style }) => (
    <EmptyState variant="search" style={style} />
);

const styles = StyleSheet.create({
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.xl,
        paddingVertical: 80,
    },
    iconCircle: {
        width: 100,
        height: 100,
        borderRadius: 50,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: Spacing.lg,
    },
    title: {
        textAlign: 'center',
        marginBottom: Spacing.sm,
        color: Colors.textPrimary,
    },
    message: {
        textAlign: 'center',
        color: Colors.textSecondary,
        fontSize: 15,
        lineHeight: 22,
        maxWidth: 280,
    },
    actionButton: {
        marginTop: Spacing.xl,
        paddingVertical: 12,
        paddingHorizontal: 24,
        backgroundColor: Colors.accentSecondary,
        borderRadius: Radius.full,
    },
    actionText: {
        color: '#FFF',
        fontWeight: '600',
        fontSize: 15,
    },
});

export default EmptyState;
