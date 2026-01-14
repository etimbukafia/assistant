import React from 'react';
import { Text, TextProps, StyleSheet } from 'react-native';
import { Colors, Typography } from '../../theme/Theme';

interface DonnaTextProps extends TextProps {
    variant?: keyof typeof Typography;
    color?: string;
}

export const DonnaText: React.FC<DonnaTextProps> = ({
    variant = 'bodyBase',
    color = Colors.textPrimary,
    style,
    children,
    ...props
}) => {
    return (
        <Text
            style={[
                Typography[variant],
                { color },
                style
            ]}
            {...props}
        >
            {children}
        </Text>
    );
};
