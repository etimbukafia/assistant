import React from 'react';
import { StyleSheet, View, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';
import { Task } from '../../types/api';

interface InlineTaskItemProps {
    task: Task;
    onApprove?: (taskId: number) => void;
    onComplete?: (taskId: number) => void;
    onStart?: (taskId: number) => void;
    onDismiss?: (taskId: number) => void;
    onPress?: (task: Task) => void;
}

export const InlineTaskItem: React.FC<InlineTaskItemProps> = ({
    task,
    onApprove,
    onComplete,
    onStart,
    onDismiss,
    onPress,
}) => {
    const isCompleted = task.status === 'completed';
    const isDismissed = task.status === 'dismissed';
    const isPendingApproval = task.status === 'pending_approval';
    const isWaitingFor = task.status === 'waiting_for';
    const isActive = task.status === 'approved' || task.status === 'in_progress';

    const handlePress = () => {
        if (onPress) {
            onPress(task);
            return;
        }

        // Default behavior based on status
        if (isPendingApproval && onApprove) {
            onApprove(task.id);
        } else if (isWaitingFor && onStart) {
            // waiting_for → move to in_progress (user received what they were waiting for)
            onStart(task.id);
        } else if (isActive && onComplete) {
            // active tasks → complete
            onComplete(task.id);
        }
        // Completed/dismissed tasks: no action on press
    };

    const getPriorityColor = (priority: string) => {
        switch (priority) {
            case 'urgent': return Colors.error;
            case 'high': return Colors.accentPrimary;
            case 'normal': return Colors.accentPrecision;
            case 'low': return Colors.textMuted;
            default: return Colors.textMuted;
        }
    };

    // Container style based on status
    const getContainerStyle = () => {
        if (isCompleted || isDismissed) return [styles.container, styles.completedContainer];
        if (isPendingApproval) return [styles.container, styles.pendingApprovalContainer];
        if (isWaitingFor) return [styles.container, styles.waitingForContainer];
        return styles.container;
    };

    // Determine if the item is actionable
    const isActionable = !isCompleted && !isDismissed;

    return (
        <TouchableOpacity
            style={getContainerStyle()}
            onPress={handlePress}
            activeOpacity={isActionable ? 0.7 : 1}
            disabled={!isActionable && !onPress}
        >
            {/* Waiting For: Purple accent bar on left */}
            {isWaitingFor && <View style={styles.waitingForBar} />}

            <View style={styles.content}>
                <View style={[
                    styles.checkbox,
                    isCompleted && styles.checkedCheckbox,
                    isPendingApproval && styles.pendingCheckbox,
                ]}>
                    {isCompleted && <Ionicons name="checkmark" size={14} color="#FFF" />}
                    {isPendingApproval && <Ionicons name="ellipse-outline" size={12} color={Colors.accentSecondary} />}
                </View>

                <View style={styles.textContainer}>
                    {/* Pending Approval: "Suggested by TEEKS" label */}
                    {isPendingApproval && (
                        <DonnaText style={styles.aiSuggestedLabel}>SUGGESTED BY TEEKS</DonnaText>
                    )}

                    {/* Waiting For: Show waiting context */}
                    {isWaitingFor && (
                        <DonnaText style={styles.waitingForLabel}>WAITING FOR RESPONSE</DonnaText>
                    )}

                    <DonnaText
                        variant="bodyBase"
                        style={[styles.title, isCompleted && styles.completedText]}
                        numberOfLines={2}
                    >
                        {task.title}
                    </DonnaText>
                </View>

                {task.priority !== 'normal' && task.priority !== 'low' && (
                    <View style={[styles.priorityBadge, { backgroundColor: getPriorityColor(task.priority) + '15' }]}>
                        <DonnaText
                            variant="labelSmall"
                            style={{ color: getPriorityColor(task.priority), fontSize: 10, fontWeight: 'bold' }}
                        >
                            {task.priority.toUpperCase()}
                        </DonnaText>
                    </View>
                )}
            </View>
        </TouchableOpacity>
    );
};

const styles = StyleSheet.create({
    container: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.sm,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
        overflow: 'hidden',
    },
    completedContainer: {
        opacity: 0.6,
        borderColor: Colors.border,
        backgroundColor: Colors.bgBase,
    },
    // Pending Approval: Dashed border, subtle copper tint
    pendingApprovalContainer: {
        borderStyle: 'dashed',
        borderColor: Colors.accentSecondary,
        borderWidth: 1.5,
        backgroundColor: 'rgba(217, 119, 69, 0.03)', // Natural Copper at 3%
    },
    // Waiting For: Purple/Navy left accent, subtle background
    waitingForContainer: {
        borderColor: Colors.accentPrecision,
        borderLeftWidth: 0, // We use the bar instead
        backgroundColor: 'rgba(30, 58, 138, 0.04)', // Navy at 4%
        flexDirection: 'row',
    },
    waitingForBar: {
        width: 4,
        backgroundColor: Colors.accentPrecision,
        marginRight: Spacing.sm,
        marginLeft: -Spacing.sm,
        marginVertical: -Spacing.sm,
        borderTopLeftRadius: Radius.lg,
        borderBottomLeftRadius: Radius.lg,
    },
    content: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
    },
    checkbox: {
        width: 22,
        height: 22,
        borderRadius: 6,
        borderWidth: 1.5,
        borderColor: Colors.textMuted,
        justifyContent: 'center',
        alignItems: 'center',
    },
    checkedCheckbox: {
        backgroundColor: Colors.success,
        borderColor: Colors.success,
    },
    pendingCheckbox: {
        borderColor: Colors.accentSecondary,
        borderStyle: 'dashed',
    },
    textContainer: {
        flex: 1,
    },
    title: {
        color: Colors.textPrimary,
    },
    completedText: {
        textDecorationLine: 'line-through',
        color: Colors.textMuted,
    },
    aiSuggestedLabel: {
        fontSize: 9,
        fontWeight: '700',
        color: Colors.accentSecondary,
        letterSpacing: 0.8,
        marginBottom: 2,
    },
    waitingForLabel: {
        fontSize: 9,
        fontWeight: '700',
        color: Colors.accentPrecision,
        letterSpacing: 0.8,
        marginBottom: 2,
    },
    priorityBadge: {
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
    },
});

