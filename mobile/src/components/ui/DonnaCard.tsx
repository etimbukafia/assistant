import React from 'react';
import { View, StyleSheet, Pressable, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Spacing } from '../../theme/Theme';
import { DonnaText } from './DonnaText';
import { Task } from '../../services/messages';
import { GlassCard } from './GlassCard';

interface DonnaCardProps {
    title: string;
    sender: string;
    time: string;
    insight?: string;
    type: 'urgent' | 'insight' | 'fyi';
    tasks?: Task[];
    extractedTasks?: string[];
    onApproveTask?: (taskId: number) => void;
    onDismissTask?: (taskId: number) => void;
    onPress?: () => void;
}

export const DonnaCard: React.FC<DonnaCardProps> = ({
    title,
    sender,
    time,
    insight,
    type,
    tasks,
    extractedTasks,
    onApproveTask,
    onDismissTask,
    onPress,
}) => {
    const getBorderColor = () => {
        switch (type) {
            case 'urgent': return Colors.accentPrimary;
            case 'insight': return Colors.accentPrecision;
            default: return 'transparent';
        }
    };

    // Structured tasks: show pending_approval, approved, in_progress
    const inlineTasks = (tasks || []).filter(
        t => t.status === 'pending_approval' || t.status === 'approved' || t.status === 'in_progress'
    );
    // Only show extracted tasks when no structured tasks exist
    const showExtracted = inlineTasks.length === 0 && (extractedTasks || []).length > 0;

    return (
        <Pressable onPress={onPress}>
            <GlassCard
                variant={type === 'urgent' ? 'warm' : 'default'}
                style={[styles.container, styles.card, { borderLeftColor: getBorderColor(), borderLeftWidth: type === 'fyi' ? 0 : 4 }]}
            >
                <View style={styles.content}>
                    <View style={styles.header}>
                        <DonnaText variant="labelSmall" color={Colors.textMuted}>{sender} • {time}</DonnaText>
                        {type === 'urgent' && (
                            <View style={styles.badge}>
                                <DonnaText variant="caption" color={Colors.accentPrimary}>URGENT</DonnaText>
                            </View>
                        )}
                    </View>

                    <DonnaText variant="h2" style={styles.title} numberOfLines={1}>{title}</DonnaText>

                    {insight && (
                        <View style={styles.insightBox}>
                            <DonnaText variant="caption" color={Colors.accentPrecision} style={styles.insightLabel}>
                                DONNA'S SUMMARY
                            </DonnaText>
                            <DonnaText variant="bodyBase" style={styles.insightText}>
                                {insight}
                            </DonnaText>
                        </View>
                    )}

                    {/* Structured tasks with approve/dismiss */}
                    {inlineTasks.length > 0 && (
                        <View style={styles.tasksSection}>
                            {inlineTasks.map(task => (
                                <View key={task.id} style={[
                                    styles.taskItem,
                                    task.status === 'pending_approval' && styles.taskItemPending,
                                ]}>
                                    <View style={[
                                        styles.taskCheckbox,
                                        task.status === 'pending_approval' && styles.taskCheckboxPending,
                                        task.status === 'approved' && styles.taskCheckboxApproved,
                                    ]}>
                                        {task.status === 'pending_approval' && (
                                            <Ionicons name="sparkles" size={10} color={Colors.accentSecondary} />
                                        )}
                                        {(task.status === 'approved' || task.status === 'in_progress') && (
                                            <Ionicons name="checkmark" size={12} color={Colors.success} />
                                        )}
                                    </View>
                                    <View style={styles.taskTextContainer}>
                                        {task.status === 'pending_approval' && (
                                            <DonnaText style={styles.taskAiLabel}>SUGGESTED BY AI</DonnaText>
                                        )}
                                        <DonnaText variant="bodyBase" numberOfLines={1} style={styles.taskTitle}>
                                            {task.title}
                                        </DonnaText>
                                    </View>
                                    {task.status === 'pending_approval' && (
                                        <View style={styles.taskActions}>
                                            <TouchableOpacity
                                                style={styles.taskApproveBtn}
                                                onPress={(e) => { e.stopPropagation(); onApproveTask?.(task.id); }}
                                            >
                                                <Ionicons name="checkmark" size={14} color={Colors.success} />
                                            </TouchableOpacity>
                                            <TouchableOpacity
                                                style={styles.taskDismissBtn}
                                                onPress={(e) => { e.stopPropagation(); onDismissTask?.(task.id); }}
                                            >
                                                <Ionicons name="close" size={14} color={Colors.textMuted} />
                                            </TouchableOpacity>
                                        </View>
                                    )}
                                    {task.priority === 'urgent' || task.priority === 'high' ? (
                                        <View style={[styles.taskPriority, {
                                            backgroundColor: (task.priority === 'urgent' ? Colors.error : Colors.accentPrimary) + '15'
                                        }]}>
                                            <DonnaText style={{
                                                fontSize: 9,
                                                fontWeight: '700',
                                                color: task.priority === 'urgent' ? Colors.error : Colors.accentPrimary,
                                            }}>
                                                {task.priority.toUpperCase()}
                                            </DonnaText>
                                        </View>
                                    ) : null}
                                </View>
                            ))}
                        </View>
                    )}

                    {/* Extracted tasks (shown only when no structured tasks) */}
                    {showExtracted && (
                        <View style={styles.tasksSection}>
                            {(extractedTasks || []).map((taskText, idx) => (
                                <View key={idx} style={[styles.taskItem, styles.taskItemExtracted]}>
                                    <Ionicons name="sparkles" size={12} color={Colors.textMuted} />
                                    <DonnaText variant="bodyBase" numberOfLines={1} style={styles.extractedTaskText}>
                                        {taskText}
                                    </DonnaText>
                                </View>
                            ))}
                        </View>
                    )}
                </View>
            </GlassCard>
        </Pressable>
    );
};

const styles = StyleSheet.create({
    container: {
        marginVertical: Spacing.sm,
        marginHorizontal: Spacing.md,
    },
    card: {
        // GlassCard handles background and borders now
    },
    content: {
        padding: Spacing.md,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: Spacing.xs,
    },
    badge: {
        backgroundColor: 'rgba(128, 0, 32, 0.1)', // Subtle Burgundy
        paddingHorizontal: Spacing.xs,
        paddingVertical: 2,
        borderRadius: Radius.xs || 4,
    },
    title: {
        marginBottom: Spacing.sm,
    },
    insightBox: {
        backgroundColor: 'rgba(30, 58, 138, 0.05)', // Subtle Navy
        padding: Spacing.sm,
        borderRadius: Radius.component,
        marginBottom: Spacing.sm,
        borderLeftWidth: 2,
        borderLeftColor: Colors.accentPrecision,
    },
    insightLabel: {
        marginBottom: 2,
        fontWeight: 'bold',
    },
    insightText: {
        fontSize: 14,
        fontStyle: 'italic',
    },
    // Tasks section
    tasksSection: {
        gap: Spacing.xs,
    },
    taskItem: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: Spacing.sm,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.bgElevated,
        gap: Spacing.sm,
    },
    taskItemPending: {
        borderStyle: 'dashed',
        borderColor: Colors.accentSecondary,
        borderWidth: 1.5,
        backgroundColor: 'rgba(217, 119, 69, 0.03)',
    },
    taskItemExtracted: {
        borderStyle: 'dashed',
        borderColor: Colors.textMuted,
        backgroundColor: Colors.bgBase,
    },
    taskCheckbox: {
        width: 20,
        height: 20,
        borderRadius: 5,
        borderWidth: 1.5,
        borderColor: Colors.textMuted,
        justifyContent: 'center',
        alignItems: 'center',
    },
    taskCheckboxPending: {
        borderColor: Colors.accentSecondary,
        borderStyle: 'dashed',
    },
    taskCheckboxApproved: {
        backgroundColor: Colors.success,
        borderColor: Colors.success,
    },
    taskTextContainer: {
        flex: 1,
    },
    taskAiLabel: {
        fontSize: 8,
        fontWeight: '700',
        color: Colors.accentSecondary,
        letterSpacing: 0.8,
        marginBottom: 1,
    },
    taskTitle: {
        color: Colors.textPrimary,
        fontSize: 13,
    },
    taskActions: {
        flexDirection: 'row',
        gap: 6,
    },
    taskApproveBtn: {
        width: 26,
        height: 26,
        borderRadius: 13,
        backgroundColor: 'rgba(138, 154, 91, 0.15)', // Sage at 15%
        justifyContent: 'center',
        alignItems: 'center',
    },
    taskDismissBtn: {
        width: 26,
        height: 26,
        borderRadius: 13,
        backgroundColor: 'rgba(107, 114, 128, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    taskPriority: {
        paddingHorizontal: 5,
        paddingVertical: 2,
        borderRadius: 4,
    },
    extractedTaskText: {
        flex: 1,
        color: Colors.textSecondary,
        fontSize: 13,
        fontStyle: 'italic',
    },
});
