import React, { useState, useCallback, useMemo } from 'react';
import { StyleSheet, View, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, Dimensions } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from '../ui/DonnaText';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withTiming,
} from 'react-native-reanimated';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

type Tone = 'professional' | 'friendly' | 'brief';

interface DraftReplySheetProps {
    isVisible: boolean;
    onClose: () => void;
    onSend: (text: string, tone: Tone) => void;
    initialDraft?: string;
    recipientName?: string;
    subject?: string;
}

const TONES: { key: Tone; label: string; icon: string }[] = [
    { key: 'professional', label: 'Professional', icon: 'briefcase-outline' },
    { key: 'friendly', label: 'Friendly', icon: 'happy-outline' },
    { key: 'brief', label: 'Brief', icon: 'flash-outline' },
];

export const DraftReplySheet: React.FC<DraftReplySheetProps> = ({
    isVisible,
    onClose,
    onSend,
    initialDraft = '',
    recipientName = 'Recipient',
    subject = 'Re: Subject',
}) => {
    const [draftText, setDraftText] = useState(initialDraft);
    const [selectedTone, setSelectedTone] = useState<Tone>('professional');

    // Animation
    const translateY = useSharedValue(SCREEN_HEIGHT);
    const opacity = useSharedValue(0);

    React.useEffect(() => {
        if (isVisible) {
            translateY.value = withSpring(0, { damping: 20, stiffness: 90 });
            opacity.value = withTiming(1, { duration: 250 });
            setDraftText(initialDraft);
        } else {
            translateY.value = withSpring(SCREEN_HEIGHT, { damping: 25, stiffness: 120 });
            opacity.value = withTiming(0, { duration: 200 });
        }
    }, [isVisible, initialDraft]);

    const animatedSheetStyle = useAnimatedStyle(() => ({
        transform: [{ translateY: translateY.value }],
    }));

    const backdropStyle = useAnimatedStyle(() => ({
        opacity: opacity.value,
    }));

    const handleSend = useCallback(() => {
        if (draftText.trim()) {
            onSend(draftText, selectedTone);
            onClose();
        }
    }, [draftText, selectedTone, onSend, onClose]);

    const regenerateDraft = useCallback(() => {
        // Mock: In real app, this would call AI to regenerate with selected tone
        const toneMessages = {
            professional: `Dear ${recipientName},\n\nThank you for your email regarding ${subject}. I have reviewed the matter and would be happy to discuss further.\n\nBest regards`,
            friendly: `Hey ${recipientName}!\n\nThanks for reaching out about ${subject}. Sounds great to me! Let me know if you need anything else.\n\nCheers`,
            brief: `Hi,\n\nConfirmed. Will follow up by EOD.\n\nThanks`,
        };
        setDraftText(toneMessages[selectedTone]);
    }, [selectedTone, recipientName, subject]);

    if (!isVisible && translateY.value >= SCREEN_HEIGHT) {
        return null;
    }

    return (
        <>
            {/* Backdrop */}
            <Animated.View style={[styles.backdrop, backdropStyle]} pointerEvents={isVisible ? 'auto' : 'none'}>
                <TouchableOpacity style={styles.backdropTouch} onPress={onClose} activeOpacity={1} />
            </Animated.View>

            {/* Sheet */}
            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                style={styles.container}
                pointerEvents="box-none"
            >
                <Animated.View style={[styles.sheet, animatedSheetStyle]}>
                    <BlurView intensity={95} tint="light" style={styles.blurView}>
                        {/* Handle */}
                        <View style={styles.handle}>
                            <View style={styles.handleBar} />
                        </View>

                        {/* Header */}
                        <View style={styles.header}>
                            <TouchableOpacity onPress={onClose}>
                                <DonnaText style={styles.cancelText}>Cancel</DonnaText>
                            </TouchableOpacity>
                            <DonnaText style={styles.title}>Draft Reply</DonnaText>
                            <TouchableOpacity onPress={handleSend} disabled={!draftText.trim()}>
                                <DonnaText style={[styles.sendText, !draftText.trim() && styles.sendDisabled]}>Send</DonnaText>
                            </TouchableOpacity>
                        </View>

                        {/* Recipient Info */}
                        <View style={styles.recipientRow}>
                            <DonnaText style={styles.recipientLabel}>To:</DonnaText>
                            <DonnaText style={styles.recipientName}>{recipientName}</DonnaText>
                        </View>

                        {/* Tone Selector */}
                        <View style={styles.toneContainer}>
                            <DonnaText style={styles.toneLabel}>TONE</DonnaText>
                            <View style={styles.toneButtons}>
                                {TONES.map(tone => (
                                    <TouchableOpacity
                                        key={tone.key}
                                        style={[
                                            styles.toneButton,
                                            selectedTone === tone.key && styles.toneButtonActive
                                        ]}
                                        onPress={() => setSelectedTone(tone.key)}
                                    >
                                        <Ionicons
                                            name={tone.icon as any}
                                            size={16}
                                            color={selectedTone === tone.key ? Colors.accentSecondary : Colors.textMuted}
                                        />
                                        <DonnaText style={[
                                            styles.toneButtonText,
                                            selectedTone === tone.key && styles.toneButtonTextActive
                                        ]}>
                                            {tone.label}
                                        </DonnaText>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>

                        {/* Draft Input */}
                        <View style={styles.inputContainer}>
                            <TextInput
                                style={styles.input}
                                value={draftText}
                                onChangeText={setDraftText}
                                placeholder="Type your reply..."
                                placeholderTextColor={Colors.textMuted}
                                multiline
                                textAlignVertical="top"
                            />
                        </View>

                        {/* Regenerate Button */}
                        <TouchableOpacity style={styles.regenerateButton} onPress={regenerateDraft}>
                            <Ionicons name="sparkles" size={18} color={Colors.accentSecondary} />
                            <DonnaText style={styles.regenerateText}>Regenerate with {selectedTone} tone</DonnaText>
                        </TouchableOpacity>

                    </BlurView>
                </Animated.View>
            </KeyboardAvoidingView>
        </>
    );
};

const styles = StyleSheet.create({
    backdrop: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'rgba(0,0,0,0.3)',
        zIndex: 900,
    },
    backdropTouch: {
        flex: 1,
    },
    container: {
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 901,
    },
    sheet: {
        maxHeight: SCREEN_HEIGHT * 0.85,
        borderTopLeftRadius: Radius.xl,
        borderTopRightRadius: Radius.xl,
        overflow: 'hidden',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: -5 },
        shadowOpacity: 0.15,
        shadowRadius: 20,
        elevation: 15,
    },
    blurView: {
        backgroundColor: 'rgba(255, 255, 255, 0.92)',
        paddingBottom: 40, // Safe area
    },
    handle: {
        alignItems: 'center',
        paddingVertical: Spacing.sm,
    },
    handleBar: {
        width: 36,
        height: 4,
        borderRadius: 2,
        backgroundColor: 'rgba(0,0,0,0.15)',
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingBottom: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(0,0,0,0.05)',
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
    sendText: {
        color: Colors.accentSecondary,
        fontSize: 16,
        fontWeight: '600',
    },
    sendDisabled: {
        opacity: 0.4,
    },
    recipientRow: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(0,0,0,0.05)',
    },
    recipientLabel: {
        color: Colors.textMuted,
        fontSize: 14,
        marginRight: Spacing.xs,
    },
    recipientName: {
        color: Colors.textPrimary,
        fontSize: 14,
        fontWeight: '500',
    },
    toneContainer: {
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(0,0,0,0.05)',
    },
    toneLabel: {
        fontSize: 11,
        fontWeight: '600',
        color: Colors.textMuted,
        letterSpacing: 1,
        marginBottom: Spacing.sm,
    },
    toneButtons: {
        flexDirection: 'row',
        gap: Spacing.sm,
    },
    toneButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
        paddingVertical: 8,
        paddingHorizontal: 12,
        borderRadius: Radius.full,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.bgSurface,
    },
    toneButtonActive: {
        borderColor: Colors.accentSecondary,
        backgroundColor: 'rgba(217, 119, 69, 0.08)',
    },
    toneButtonText: {
        fontSize: 13,
        color: Colors.textSecondary,
    },
    toneButtonTextActive: {
        color: Colors.accentSecondary,
        fontWeight: '600',
    },
    inputContainer: {
        padding: Spacing.md,
        minHeight: 200,
    },
    input: {
        fontFamily: 'Inter_400Regular',
        fontSize: 16,
        color: Colors.textPrimary,
        lineHeight: 24,
        minHeight: 180,
    },
    regenerateButton: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.xs,
        paddingVertical: Spacing.md,
        marginHorizontal: Spacing.md,
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
        borderStyle: 'dashed',
    },
    regenerateText: {
        color: Colors.accentSecondary,
        fontSize: 14,
        fontWeight: '500',
    },
});

export default DraftReplySheet;
