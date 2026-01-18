import React, { useState } from 'react';
import { StyleSheet, View, TextInput, TouchableOpacity, Modal, Pressable, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from '../ui/DonnaText';
import DateTimePicker from '@react-native-community/datetimepicker';

type TaskPriority = 'low' | 'normal' | 'high' | 'urgent';

interface CreateTaskModalProps {
    isVisible: boolean;
    onClose: () => void;
    onCreate: (task: { title: string; description: string; priority: TaskPriority; deadline?: Date }) => void;
}

const PRIORITIES: { key: TaskPriority; label: string; color: string }[] = [
    { key: 'low', label: 'Low', color: Colors.textMuted },
    { key: 'normal', label: 'Normal', color: Colors.accentPrecision },
    { key: 'high', label: 'High', color: Colors.accentPrimary },
    { key: 'urgent', label: 'Urgent', color: Colors.error },
];

export const CreateTaskModal: React.FC<CreateTaskModalProps> = ({
    isVisible,
    onClose,
    onCreate,
}) => {
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [priority, setPriority] = useState<TaskPriority>('normal');
    const [deadline, setDeadline] = useState<Date | undefined>(undefined);
    const [showDatePicker, setShowDatePicker] = useState(false);

    const resetForm = () => {
        setTitle('');
        setDescription('');
        setPriority('normal');
        setDeadline(undefined);
    };

    const handleCreate = () => {
        if (title.trim()) {
            onCreate({ title, description, priority, deadline });
            resetForm();
            onClose();
        }
    };

    const handleCancel = () => {
        resetForm();
        onClose();
    };

    const handleDateChange = (event: any, selectedDate?: Date) => {
        setShowDatePicker(Platform.OS === 'ios');
        if (selectedDate) {
            setDeadline(selectedDate);
        }
    };

    const selectedPriorityColor = PRIORITIES.find(p => p.key === priority)?.color || Colors.textMuted;

    return (
        <Modal
            visible={isVisible}
            animationType="slide"
            presentationStyle="pageSheet"
            onRequestClose={handleCancel}
        >
            <View style={styles.container}>
                {/* Header */}
                <View style={styles.header}>
                    <TouchableOpacity onPress={handleCancel}>
                        <DonnaText style={styles.cancelText}>Cancel</DonnaText>
                    </TouchableOpacity>
                    <DonnaText style={styles.title}>New Task</DonnaText>
                    <TouchableOpacity onPress={handleCreate} disabled={!title.trim()}>
                        <DonnaText style={[styles.createText, !title.trim() && styles.createDisabled]}>Create</DonnaText>
                    </TouchableOpacity>
                </View>

                {/* Form */}
                <View style={styles.form}>
                    {/* Title */}
                    <View style={styles.inputGroup}>
                        <DonnaText style={styles.label}>TITLE *</DonnaText>
                        <TextInput
                            style={styles.titleInput}
                            value={title}
                            onChangeText={setTitle}
                            placeholder="What needs to be done?"
                            placeholderTextColor={Colors.textMuted}
                            autoFocus
                        />
                    </View>

                    {/* Description */}
                    <View style={styles.inputGroup}>
                        <DonnaText style={styles.label}>DESCRIPTION</DonnaText>
                        <TextInput
                            style={styles.descriptionInput}
                            value={description}
                            onChangeText={setDescription}
                            placeholder="Add details..."
                            placeholderTextColor={Colors.textMuted}
                            multiline
                            textAlignVertical="top"
                        />
                    </View>

                    {/* Priority Selector */}
                    <View style={styles.inputGroup}>
                        <DonnaText style={styles.label}>PRIORITY</DonnaText>
                        <View style={styles.priorityContainer}>
                            {PRIORITIES.map(p => (
                                <TouchableOpacity
                                    key={p.key}
                                    style={[
                                        styles.priorityButton,
                                        priority === p.key && { borderColor: p.color, backgroundColor: p.color + '12' }
                                    ]}
                                    onPress={() => setPriority(p.key)}
                                >
                                    <View style={[styles.priorityDot, { backgroundColor: p.color }]} />
                                    <DonnaText style={[
                                        styles.priorityText,
                                        priority === p.key && { color: p.color, fontWeight: '600' }
                                    ]}>
                                        {p.label}
                                    </DonnaText>
                                </TouchableOpacity>
                            ))}
                        </View>
                    </View>

                    {/* Deadline Picker */}
                    <View style={styles.inputGroup}>
                        <DonnaText style={styles.label}>DEADLINE</DonnaText>
                        <TouchableOpacity
                            style={styles.dateButton}
                            onPress={() => setShowDatePicker(true)}
                        >
                            <Ionicons name="calendar-outline" size={20} color={Colors.textSecondary} />
                            <DonnaText style={styles.dateText}>
                                {deadline ? deadline.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) : 'Set deadline (optional)'}
                            </DonnaText>
                            {deadline && (
                                <TouchableOpacity onPress={() => setDeadline(undefined)}>
                                    <Ionicons name="close-circle" size={18} color={Colors.textMuted} />
                                </TouchableOpacity>
                            )}
                        </TouchableOpacity>
                    </View>

                    {showDatePicker && (
                        <DateTimePicker
                            value={deadline || new Date()}
                            mode="date"
                            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                            onChange={handleDateChange}
                            minimumDate={new Date()}
                        />
                    )}
                </View>

                {/* Preview */}
                <View style={styles.previewSection}>
                    <DonnaText style={styles.previewLabel}>PREVIEW</DonnaText>
                    <View style={[styles.previewCard, { borderLeftColor: selectedPriorityColor }]}>
                        <DonnaText style={styles.previewTitle} numberOfLines={1}>
                            {title || 'Task title...'}
                        </DonnaText>
                        {description ? (
                            <DonnaText style={styles.previewDescription} numberOfLines={2}>
                                {description}
                            </DonnaText>
                        ) : null}
                        <View style={styles.previewMeta}>
                            <View style={[styles.previewPriorityBadge, { backgroundColor: selectedPriorityColor + '15' }]}>
                                <DonnaText style={[styles.previewPriorityText, { color: selectedPriorityColor }]}>
                                    {priority.toUpperCase()}
                                </DonnaText>
                            </View>
                            {deadline && (
                                <DonnaText style={styles.previewDeadline}>
                                    Due: {deadline.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                </DonnaText>
                            )}
                        </View>
                    </View>
                </View>
            </View>
        </Modal>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.bgBase,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
        backgroundColor: Colors.bgElevated,
    },
    cancelText: {
        color: Colors.textSecondary,
        fontSize: 16,
    },
    title: {
        fontSize: 17,
        fontWeight: '600',
        color: Colors.textPrimary,
    },
    createText: {
        color: Colors.accentSecondary,
        fontSize: 16,
        fontWeight: '600',
    },
    createDisabled: {
        opacity: 0.4,
    },
    form: {
        padding: Spacing.md,
    },
    inputGroup: {
        marginBottom: Spacing.lg,
    },
    label: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
    },
    titleInput: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 22,
        color: Colors.textPrimary,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
        paddingBottom: Spacing.sm,
    },
    descriptionInput: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: Colors.textPrimary,
        minHeight: 80,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.component,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    priorityContainer: {
        flexDirection: 'row',
        gap: Spacing.sm,
    },
    priorityButton: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        paddingVertical: 10,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.bgElevated,
    },
    priorityDot: {
        width: 8,
        height: 8,
        borderRadius: 4,
    },
    priorityText: {
        fontSize: 13,
        color: Colors.textSecondary,
    },
    dateButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        paddingVertical: 12,
        paddingHorizontal: Spacing.md,
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    dateText: {
        flex: 1,
        fontSize: 15,
        color: Colors.textSecondary,
    },
    previewSection: {
        padding: Spacing.md,
        marginTop: Spacing.lg,
    },
    previewLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
    },
    previewCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderLeftWidth: 4,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 8,
        elevation: 2,
    },
    previewTitle: {
        fontFamily: 'PlayfairDisplay_600SemiBold',
        fontSize: 16,
        color: Colors.textPrimary,
        marginBottom: 4,
    },
    previewDescription: {
        fontSize: 14,
        color: Colors.textSecondary,
        marginBottom: Spacing.sm,
    },
    previewMeta: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
    },
    previewPriorityBadge: {
        paddingHorizontal: 8,
        paddingVertical: 3,
        borderRadius: 4,
    },
    previewPriorityText: {
        fontSize: 10,
        fontWeight: '700',
        letterSpacing: 0.5,
    },
    previewDeadline: {
        fontSize: 12,
        color: Colors.textMuted,
    },
});

export default CreateTaskModal;
