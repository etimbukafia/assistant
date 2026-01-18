import React, { useEffect } from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withRepeat,
    withTiming,
    interpolate,
} from 'react-native-reanimated';
import { Colors, Spacing, Radius } from '../../theme/Theme';

interface SkeletonProps {
    width?: number | string;
    height?: number;
    borderRadius?: number;
    style?: ViewStyle;
}

export const Skeleton: React.FC<SkeletonProps> = ({
    width = '100%',
    height = 16,
    borderRadius = 6,
    style,
}) => {
    const shimmer = useSharedValue(0);

    useEffect(() => {
        shimmer.value = withRepeat(
            withTiming(1, { duration: 1200 }),
            -1,
            false
        );
    }, []);

    const animatedStyle = useAnimatedStyle(() => ({
        opacity: interpolate(shimmer.value, [0, 0.5, 1], [0.3, 0.7, 0.3]),
    }));

    return (
        <Animated.View
            style={[
                styles.skeleton,
                { width: width as any, height, borderRadius },
                animatedStyle,
                style,
            ]}
        />
    );
};

// Pre-built skeleton layouts
export const SkeletonCard: React.FC<{ style?: ViewStyle }> = ({ style }) => (
    <View style={[styles.card, style]}>
        <View style={styles.cardHeader}>
            <Skeleton width={40} height={40} borderRadius={20} />
            <View style={styles.cardHeaderText}>
                <Skeleton width="60%" height={14} />
                <Skeleton width="40%" height={12} style={{ marginTop: 6 }} />
            </View>
        </View>
        <Skeleton width="100%" height={12} style={{ marginTop: Spacing.md }} />
        <Skeleton width="80%" height={12} style={{ marginTop: 6 }} />
        <Skeleton width="45%" height={12} style={{ marginTop: 6 }} />
    </View>
);

export const SkeletonMessageCard: React.FC<{ style?: ViewStyle }> = ({ style }) => (
    <View style={[styles.messageCard, style]}>
        <View style={styles.messageHeader}>
            <Skeleton width={36} height={36} borderRadius={18} />
            <View style={{ flex: 1, marginLeft: Spacing.sm }}>
                <Skeleton width="50%" height={14} />
                <Skeleton width="70%" height={12} style={{ marginTop: 4 }} />
            </View>
            <Skeleton width={50} height={12} />
        </View>
        <Skeleton width="90%" height={14} style={{ marginTop: Spacing.md }} />
        <Skeleton width="100%" height={12} style={{ marginTop: 6 }} />
        <Skeleton width="60%" height={12} style={{ marginTop: 6 }} />
    </View>
);

export const SkeletonTaskCard: React.FC<{ style?: ViewStyle }> = ({ style }) => (
    <View style={[styles.taskCard, style]}>
        <Skeleton width={20} height={20} borderRadius={6} />
        <View style={{ flex: 1, marginLeft: Spacing.sm }}>
            <Skeleton width="75%" height={14} />
        </View>
        <Skeleton width={50} height={18} borderRadius={9} />
    </View>
);

export const SkeletonEventCard: React.FC<{ style?: ViewStyle }> = ({ style }) => (
    <View style={[styles.eventCard, style]}>
        <View style={styles.eventTime}>
            <Skeleton width={60} height={16} />
            <Skeleton width={40} height={12} style={{ marginTop: 4 }} />
        </View>
        <View style={styles.eventDetails}>
            <Skeleton width="70%" height={16} />
            <Skeleton width="50%" height={12} style={{ marginTop: 6 }} />
            <View style={styles.eventParticipants}>
                <Skeleton width={24} height={24} borderRadius={12} />
                <Skeleton width={24} height={24} borderRadius={12} style={{ marginLeft: -8 }} />
                <Skeleton width={24} height={24} borderRadius={12} style={{ marginLeft: -8 }} />
            </View>
        </View>
    </View>
);

// Full screen skeleton for lists
export const SkeletonList: React.FC<{ count?: number; type?: 'message' | 'task' | 'event' }> = ({
    count = 5,
    type = 'message',
}) => {
    const CardComponent = type === 'task' ? SkeletonTaskCard :
        type === 'event' ? SkeletonEventCard :
            SkeletonMessageCard;

    return (
        <View style={styles.listContainer}>
            {Array.from({ length: count }).map((_, i) => (
                <CardComponent key={i} style={{ marginBottom: Spacing.sm }} />
            ))}
        </View>
    );
};

const styles = StyleSheet.create({
    skeleton: {
        backgroundColor: Colors.border,
    },
    card: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    cardHeader: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    cardHeaderText: {
        flex: 1,
        marginLeft: Spacing.sm,
    },
    messageCard: {
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    messageHeader: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    taskCard: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.sm,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    eventCard: {
        flexDirection: 'row',
        backgroundColor: Colors.bgElevated,
        borderRadius: Radius.lg,
        padding: Spacing.md,
        borderWidth: 1,
        borderColor: Colors.border,
    },
    eventTime: {
        width: 70,
        borderRightWidth: 1,
        borderRightColor: Colors.border,
        paddingRight: Spacing.md,
    },
    eventDetails: {
        flex: 1,
        paddingLeft: Spacing.md,
    },
    eventParticipants: {
        flexDirection: 'row',
        marginTop: Spacing.sm,
    },
    listContainer: {
        padding: Spacing.md,
    },
});

export default Skeleton;
