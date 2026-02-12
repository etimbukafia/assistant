import React from 'react';
import { StyleSheet, View, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '@/src/theme/Theme';
import { DonnaText } from '@/src/components/ui/DonnaText';

export interface SettingRowProps {
    icon: string;
    iconColor?: string;
    title: string;
    subtitle?: string;
    onPress?: () => void;
    showArrow?: boolean;
    rightElement?: React.ReactNode;
    destructive?: boolean;
}

export const SettingRow: React.FC<SettingRowProps> = ({
    icon,
    iconColor = Colors.textSecondary,
    title,
    subtitle,
    onPress,
    showArrow = true,
    rightElement,
    destructive,
}) => (
    <TouchableOpacity style={styles.settingRow} onPress={onPress} disabled={!onPress}>
        <View style={[styles.iconContainer, { backgroundColor: iconColor + '15' }]}>
            <Ionicons name={icon as any} size={20} color={iconColor} />
        </View>
        <View style={styles.settingTextContainer}>
            <DonnaText style={[styles.settingTitle, destructive && { color: Colors.error }]}>
                {title}
            </DonnaText>
            {subtitle && <DonnaText style={styles.settingSubtitle}>{subtitle}</DonnaText>}
        </View>
        {rightElement}
        {showArrow && !rightElement && (
            <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
        )}
    </TouchableOpacity>
);

const styles = StyleSheet.create({
    settingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        padding: Spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
    },
    iconContainer: {
        width: 36,
        height: 36,
        borderRadius: 10,
        justifyContent: 'center',
        alignItems: 'center',
    },
    settingTextContainer: {
        flex: 1,
    },
    settingTitle: {
        fontSize: 15,
        fontWeight: '500',
        color: Colors.textPrimary,
    },
    settingSubtitle: {
        fontSize: 12,
        color: Colors.textMuted,
        marginTop: 1,
    },
});
