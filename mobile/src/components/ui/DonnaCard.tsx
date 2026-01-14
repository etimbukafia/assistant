import React from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { Colors, Radius, Spacing } from '../../theme/Theme';
import { DonnaText } from './DonnaText';
import { DonnaButton } from './DonnaButton';

interface DonnaCardProps {
    title: string;
    sender: string;
    snippet: string;
    time: string;
    insight?: string;
    type: 'urgent' | 'insight' | 'fyi';
    suggestedAction?: string;
    onActionPress?: () => void;
    onPress?: () => void;
}

export const DonnaCard: React.FC<DonnaCardProps> = ({
    title,
    sender,
    snippet,
    time,
    insight,
    type,
    suggestedAction,
    onActionPress,
    onPress,
}) => {
    const getBorderColor = () => {
        switch (type) {
            case 'urgent': return Colors.accentPrimary;
            case 'insight': return Colors.accentPrecision;
            default: return 'transparent';
        }
    };

    return (
        <Pressable onPress={onPress} style={styles.container}>
            <View style={[styles.card, { borderLeftColor: getBorderColor(), borderLeftWidth: type === 'fyi' ? 0 : 4 }]}>
                <View style={styles.header}>
                    <DonnaText variant="labelSmall" color={Colors.textMuted}>{sender} • {time}</DonnaText>
                    {type === 'urgent' && (
                        <View style={styles.badge}>
                            <DonnaText variant="caption" color={Colors.accentPrimary}>URGENT</DonnaText>
                        </View>
                    )}
                </View>

                <DonnaText variant="h2" style={styles.title}>{title}</DonnaText>
                <DonnaText variant="bodyBase" color={Colors.textMuted} numberOfLines={2} style={styles.snippet}>
                    {snippet}
                </DonnaText>

                {insight && (
                    <View style={styles.insightBox}>
                        <DonnaText variant="caption" color={Colors.accentPrecision} style={styles.insightLabel}>
                            CERULEAN INSIGHT
                        </DonnaText>
                        <DonnaText variant="bodyBase" style={styles.insightText}>
                            {insight}
                        </DonnaText>
                    </View>
                )}

                {suggestedAction && (
                    <View style={styles.footer}>
                        <DonnaButton
                            title={suggestedAction}
                            onPress={onActionPress || (() => { })}
                            variant="secondary"
                            fullWidth
                        />
                    </View>
                )}
            </View>
        </Pressable>
    );
};

const styles = StyleSheet.create({
    container: {
        marginVertical: Spacing.sm,
        marginHorizontal: Spacing.md,
    },
    card: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.surface,
        padding: Spacing.md,
        borderWidth: 0.5,
        borderColor: Colors.border,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: Spacing.xs,
    },
    badge: {
        backgroundColor: 'rgba(230, 57, 70, 0.1)',
        paddingHorizontal: Spacing.xs,
        paddingVertical: 2,
        borderRadius: Radius.xs || 4,
    },
    title: {
        marginBottom: Spacing.xs,
    },
    snippet: {
        marginBottom: Spacing.md,
    },
    insightBox: {
        backgroundColor: 'rgba(0, 123, 167, 0.05)',
        padding: Spacing.sm,
        borderRadius: Radius.component,
        marginBottom: Spacing.md,
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
    footer: {
        marginTop: Spacing.xs,
    },
});
