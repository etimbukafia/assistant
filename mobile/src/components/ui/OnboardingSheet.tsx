import React, { useState } from 'react';
import { StyleSheet, TextInput, View, TouchableOpacity, ActivityIndicator } from 'react-native';
import BottomSheet, { BottomSheetView } from '@gorhom/bottom-sheet';
import { DonnaText } from './DonnaText';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { completeOnboarding } from '../../services/onboarding';

interface OnboardingSheetProps {
    isOpen: boolean;
    onComplete: () => void;
}

export function OnboardingSheet({ isOpen, onComplete }: OnboardingSheetProps) {
    const [name, setName] = useState('Donna');
    const queryClient = useQueryClient();

    const mutation = useMutation({
        mutationFn: () => completeOnboarding({ assistant_name: name.trim() || 'Donna' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['settings'] });
            onComplete();
        },
    });

    if (!isOpen) return null;

    return (
        <BottomSheet
            snapPoints={['50%']}
            enablePanDownToClose={false}
            index={0}
            backgroundStyle={{ backgroundColor: Colors.bgBase }}
            handleIndicatorStyle={{ backgroundColor: Colors.border }}
        >
            <BottomSheetView style={styles.content}>
                <View style={styles.header}>
                    <DonnaText variant="h2" style={styles.title}>
                        Welcome to Teeks Pro! 🎉
                    </DonnaText>
                    <DonnaText style={styles.subtitle}>
                        What would you like to call your assistant?
                    </DonnaText>
                </View>

                <View style={styles.inputContainer}>
                    <TextInput
                        style={styles.input}
                        value={name}
                        onChangeText={setName}
                        placeholder="Donna"
                        placeholderTextColor={Colors.textMuted}
                        maxLength={50}
                        autoCapitalize="words"
                        autoFocus
                    />
                </View>
                <DonnaText style={styles.hint}>
                    This name will be used everywhere in the app.
                </DonnaText>

                <TouchableOpacity
                    style={styles.button}
                    onPress={() => mutation.mutate()}
                    disabled={mutation.isPending}
                >
                    {mutation.isPending ? (
                        <ActivityIndicator color="#FFFFFF" />
                    ) : (
                        <DonnaText style={styles.buttonText}>Continue</DonnaText>
                    )}
                </TouchableOpacity>
            </BottomSheetView>
        </BottomSheet>
    );
}

const styles = StyleSheet.create({
    content: {
        flex: 1,
        padding: Spacing.xl,
    },
    header: {
        marginBottom: Spacing.xl,
    },
    title: {
        textAlign: 'center',
        marginBottom: Spacing.sm,
    },
    subtitle: {
        textAlign: 'center',
        color: Colors.textSecondary,
        fontSize: 16,
    },
    inputContainer: {
        backgroundColor: Colors.bgSurface,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: Colors.border,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.md,
        marginBottom: Spacing.sm,
    },
    input: {
        fontSize: 18,
        color: Colors.textPrimary,
        fontWeight: '500',
        textAlign: 'center',
    },
    hint: {
        textAlign: 'center',
        fontSize: 13,
        color: Colors.textMuted,
        marginBottom: Spacing.xl,
    },
    button: {
        backgroundColor: Colors.accentPrimary,
        paddingVertical: Spacing.lg,
        borderRadius: Radius.full,
        alignItems: 'center',
        justifyContent: 'center',
    },
    buttonText: {
        color: '#FFFFFF',
        fontSize: 16,
        fontWeight: '600',
    },
});
