import React from 'react';
import { StyleSheet, View, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';
import { Task } from '../../types/api';

interface InlineTaskItemProps {
    task: Task;
    onUpdate: (task: Task) => void;
}

export const InlineTaskItem: React.FC<InlineTaskItemProps> = ({ task, onUpdate }) => {
    const isCompleted = task.status === 'completed';

    const getPriorityColor = (priority: string) => {
        switch (priority) {
            case 'urgent': return Colors.accentPrimary;
            case 'high': return Colors.accentPrimary;
            case 'normal': return Colors.accentPrecision;
            case 'low': return Colors.textMuted;
            default: return Colors.textMuted;
        }
    };

    return (
        <TouchableOpacity
            style={[styles.container, isCompleted && styles.completedContainer]}
            onPress={() => onUpdate({ ...task, status: isCompleted ? 'pending_approval' : 'completed' })}
            activeOpacity={0.7}
        >
            <View style={styles.content}>
                <View style={[styles.checkbox, isCompleted && styles.checkedCheckbox]}>
                    {isCompleted && <Ionicons name="checkmark" size={14} color="#FFF" />}
                </View>

                <View style={styles.textContainer}>
                    <DonnaText
                        variant="bodyBase"
                        style={[styles.title, isCompleted && styles.completedText]}
                        numberOfLines={1}
                    >
                        {task.title}
                    </DonnaText>
                </View>

                {task.priority !== 'normal' && task.priority !== 'low' && (
                    <View style={[styles.priorityBadge, { backgroundColor: getPriorityColor(task.priority) + '20' }]}>
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
        borderRadius: Radius.surface,
        padding: Spacing.sm,
        marginBottom: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    completedContainer: {
        opacity: 0.6,
        borderColor: Colors.border,
        backgroundColor: Colors.bgBase,
    },
    content: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
    },
    checkbox: {
        width: 20,
        height: 20,
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
    priorityBadge: {
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
    },
});
