import React from 'react';
import { StyleSheet, View, TouchableOpacity, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from './DonnaText';

type ErrorVariant = 'network' | 'auth' | 'notFound' | 'server' | 'permission' | 'generic';

interface ErrorStateProps {
    variant?: ErrorVariant;
    title?: string;
    message?: string;
    onRetry?: () => void;
    onGoBack?: () => void;
    secondaryAction?: { label: string; onPress: () => void };
    style?: ViewStyle;
}

const VARIANTS: Record<ErrorVariant, { icon: string; title: string; message: string; color: string }> = {
    network: {
        icon: 'cloud-offline-outline',
        title: 'No Connection',
        message: 'Please check your internet connection and try again.',
        color: Colors.textMuted,
    },
    auth: {
        icon: 'lock-closed-outline',
        title: 'Session Expired',
        message: 'Your session has expired. Please sign in again.',
        color: Colors.accentSecondary,
    },
    notFound: {
        icon: 'help-circle-outline',
        title: 'Not Found',
        message: 'The content you\'re looking for doesn\'t exist or has been moved.',
        color: Colors.textMuted,
    },
    server: {
        icon: 'alert-circle-outline',
        title: 'Something Went Wrong',
        message: 'We\'re having trouble connecting to our servers. Please try again.',
        color: Colors.error,
    },
    permission: {
        icon: 'shield-outline',
        title: 'Access Denied',
        message: 'You don\'t have permission to view this content.',
        color: Colors.accentPrimary,
    },
    generic: {
        icon: 'warning-outline',
        title: 'Oops!',
        message: 'Something unexpected happened. Please try again.',
        color: Colors.error,
    },
};

export const ErrorState: React.FC<ErrorStateProps> = ({
    variant = 'generic',
    title,
    message,
    onRetry,
    onGoBack,
    secondaryAction,
    style,
}) => {
    const config = VARIANTS[variant];
    const displayTitle = title || config.title;
    const displayMessage = message || config.message;

    return (
        <View style={[styles.container, style]}>
            <View style={[styles.iconCircle, { backgroundColor: config.color + '12' }]}>
                <Ionicons name={config.icon as any} size={48} color={config.color} />
            </View>

            <DonnaText variant="h2" style={styles.title}>
                {displayTitle}
            </DonnaText>

            <DonnaText style={styles.message}>
                {displayMessage}
            </DonnaText>

            <View style={styles.actions}>
                {onRetry && (
                    <TouchableOpacity style={styles.primaryButton} onPress={onRetry}>
                        <Ionicons name="refresh" size={18} color="#FFF" />
                        <DonnaText style={styles.primaryButtonText}>Try Again</DonnaText>
                    </TouchableOpacity>
                )}

                {onGoBack && (
                    <TouchableOpacity style={styles.secondaryButton} onPress={onGoBack}>
                        <Ionicons name="arrow-back" size={18} color={Colors.textSecondary} />
                        <DonnaText style={styles.secondaryButtonText}>Go Back</DonnaText>
                    </TouchableOpacity>
                )}

                {secondaryAction && (
                    <TouchableOpacity style={styles.secondaryButton} onPress={secondaryAction.onPress}>
                        <DonnaText style={styles.secondaryButtonText}>{secondaryAction.label}</DonnaText>
                    </TouchableOpacity>
                )}
            </View>
        </View>
    );
};

// Specific error states
export const NetworkErrorState: React.FC<{ onRetry?: () => void; style?: ViewStyle }> = ({ onRetry, style }) => (
    <ErrorState variant="network" onRetry={onRetry} style={style} />
);

export const AuthErrorState: React.FC<{ onSignIn?: () => void; style?: ViewStyle }> = ({ onSignIn, style }) => (
    <ErrorState
        variant="auth"
        onRetry={onSignIn}
        style={style}
    />
);

export const NotFoundState: React.FC<{ onGoBack?: () => void; style?: ViewStyle }> = ({ onGoBack, style }) => (
    <ErrorState variant="notFound" onGoBack={onGoBack} style={style} />
);

export const ServerErrorState: React.FC<{ onRetry?: () => void; style?: ViewStyle }> = ({ onRetry, style }) => (
    <ErrorState variant="server" onRetry={onRetry} style={style} />
);

// Inline error banner (for less intrusive errors)
interface ErrorBannerProps {
    message: string;
    onDismiss?: () => void;
    onRetry?: () => void;
    style?: ViewStyle;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
    message,
    onDismiss,
    onRetry,
    style,
}) => (
    <View style={[styles.banner, style]}>
        <Ionicons name="alert-circle" size={20} color={Colors.error} />
        <DonnaText style={styles.bannerText}>{message}</DonnaText>
        {onRetry && (
            <TouchableOpacity onPress={onRetry} style={styles.bannerAction}>
                <DonnaText style={styles.bannerActionText}>Retry</DonnaText>
            </TouchableOpacity>
        )}
        {onDismiss && (
            <TouchableOpacity onPress={onDismiss}>
                <Ionicons name="close" size={18} color={Colors.textMuted} />
            </TouchableOpacity>
        )}
    </View>
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
    actions: {
        marginTop: Spacing.xl,
        gap: Spacing.md,
        alignItems: 'center',
    },
    primaryButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        paddingVertical: 12,
        paddingHorizontal: 24,
        backgroundColor: Colors.accentSecondary,
        borderRadius: Radius.full,
    },
    primaryButtonText: {
        color: '#FFF',
        fontWeight: '600',
        fontSize: 15,
    },
    secondaryButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        paddingVertical: 10,
        paddingHorizontal: 20,
    },
    secondaryButtonText: {
        color: Colors.textSecondary,
        fontSize: 15,
    },
    banner: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        padding: Spacing.md,
        backgroundColor: 'rgba(186, 73, 73, 0.08)',
        borderRadius: Radius.component,
        borderWidth: 1,
        borderColor: Colors.error + '30',
    },
    bannerText: {
        flex: 1,
        color: Colors.error,
        fontSize: 14,
    },
    bannerAction: {
        paddingHorizontal: Spacing.sm,
    },
    bannerActionText: {
        color: Colors.error,
        fontWeight: '600',
        fontSize: 14,
    },
});

export default ErrorState;
