import React from 'react';
import { StyleSheet, View, ActivityIndicator, ViewStyle, TouchableOpacity, TouchableOpacityProps } from 'react-native';
import { BlurView } from 'expo-blur';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

// Full screen loading overlay
interface LoadingOverlayProps {
    visible: boolean;
    message?: string;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
    visible,
    message = 'Loading...',
}) => {
    if (!visible) return null;

    return (
        <View style={styles.overlay}>
            <BlurView intensity={60} tint="light" style={styles.blurContainer}>
                <View style={styles.loadingCard}>
                    <ActivityIndicator size="large" color={Colors.accentSecondary} />
                    <DonnaText style={styles.loadingText}>{message}</DonnaText>
                </View>
            </BlurView>
        </View>
    );
};

// Inline loading spinner
interface SpinnerProps {
    size?: 'small' | 'large';
    color?: string;
    style?: ViewStyle;
}

export const Spinner: React.FC<SpinnerProps> = ({
    size = 'small',
    color = Colors.accentSecondary,
    style,
}) => (
    <View style={[styles.spinnerContainer, style]}>
        <ActivityIndicator size={size} color={color} />
    </View>
);

// Button with loading state
interface LoadingButtonProps extends TouchableOpacityProps {
    loading?: boolean;
    title: string;
    variant?: 'primary' | 'secondary' | 'outline';
}

export const LoadingButton: React.FC<LoadingButtonProps> = ({
    loading = false,
    title,
    variant = 'primary',
    disabled,
    style,
    ...props
}) => {
    const buttonStyle = [
        styles.button,
        variant === 'primary' && styles.buttonPrimary,
        variant === 'secondary' && styles.buttonSecondary,
        variant === 'outline' && styles.buttonOutline,
        (disabled || loading) && styles.buttonDisabled,
        style,
    ];

    const textStyle = [
        styles.buttonText,
        variant === 'primary' && styles.buttonTextPrimary,
        variant === 'secondary' && styles.buttonTextSecondary,
        variant === 'outline' && styles.buttonTextOutline,
    ];

    return (
        <TouchableOpacity
            style={buttonStyle}
            disabled={disabled || loading}
            {...props}
        >
            {loading ? (
                <ActivityIndicator
                    size="small"
                    color={variant === 'primary' ? '#FFF' : Colors.accentSecondary}
                />
            ) : (
                <DonnaText style={textStyle}>{title}</DonnaText>
            )}
        </TouchableOpacity>
    );
};

// Pull to refresh indicator (custom styling)
interface RefreshIndicatorProps {
    refreshing: boolean;
}

export const RefreshIndicator: React.FC<RefreshIndicatorProps> = ({ refreshing }) => {
    if (!refreshing) return null;

    return (
        <View style={styles.refreshContainer}>
            <ActivityIndicator size="small" color={Colors.accentSecondary} />
            <DonnaText style={styles.refreshText}>Refreshing...</DonnaText>
        </View>
    );
};

// Inline loading state for lists
interface ListLoadingFooterProps {
    loading: boolean;
    message?: string;
}

export const ListLoadingFooter: React.FC<ListLoadingFooterProps> = ({
    loading,
    message = 'Loading more...',
}) => {
    if (!loading) return null;

    return (
        <View style={styles.listFooter}>
            <ActivityIndicator size="small" color={Colors.accentSecondary} />
            <DonnaText style={styles.listFooterText}>{message}</DonnaText>
        </View>
    );
};

const styles = StyleSheet.create({
    overlay: {
        ...StyleSheet.absoluteFillObject,
        zIndex: 999,
    },
    blurContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.5)',
    },
    loadingCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.xl,
        padding: Spacing.xl,
        alignItems: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 12,
        elevation: 8,
    },
    loadingText: {
        marginTop: Spacing.md,
        color: Colors.textSecondary,
        fontSize: 15,
    },
    spinnerContainer: {
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.lg,
    },
    button: {
        paddingVertical: 14,
        paddingHorizontal: 24,
        borderRadius: Radius.full,
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 48,
    },
    buttonPrimary: {
        backgroundColor: Colors.accentSecondary,
    },
    buttonSecondary: {
        backgroundColor: Colors.bgElevated,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    buttonOutline: {
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderColor: Colors.accentSecondary,
    },
    buttonDisabled: {
        opacity: 0.5,
    },
    buttonText: {
        fontSize: 16,
        fontWeight: '600',
    },
    buttonTextPrimary: {
        color: '#FFF',
    },
    buttonTextSecondary: {
        color: Colors.textPrimary,
    },
    buttonTextOutline: {
        color: Colors.accentSecondary,
    },
    refreshContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        paddingVertical: Spacing.md,
    },
    refreshText: {
        color: Colors.textMuted,
        fontSize: 13,
    },
    listFooter: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: Spacing.sm,
        paddingVertical: Spacing.lg,
    },
    listFooterText: {
        color: Colors.textMuted,
        fontSize: 13,
    },
});

export default LoadingOverlay;
