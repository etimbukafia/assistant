import React, { useState } from 'react';
import { StyleSheet, View, TouchableOpacity, Pressable } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius } from '../../theme/Theme';
import { DonnaText } from '../ui/DonnaText';
import Animated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withTiming,
    runOnJS,
} from 'react-native-reanimated';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';

interface Tab {
    name: string;
    icon: keyof typeof Ionicons.glyphMap;
    route: string;
}

const TABS: Tab[] = [
    { name: 'Inbox', icon: 'mail', route: 'index' },
    { name: 'Focus', icon: 'flash', route: 'focus' },
    { name: 'Schedule', icon: 'calendar', route: 'calendar' },
    { name: 'Settings', icon: 'settings-outline', route: 'settings' },
];

interface AdaptivePillNavProps {
    currentIndex: number;
    onTabChange: (index: number) => void;
}

export const AdaptivePillNav: React.FC<AdaptivePillNavProps> = ({
    currentIndex,
    onTabChange,
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const translateX = useSharedValue(0);
    const expandScale = useSharedValue(1);
    const SWIPE_THRESHOLD = 50;

    const handleSwipe = (direction: 'left' | 'right') => {
        if (direction === 'left' && currentIndex < TABS.length - 1) {
            onTabChange(currentIndex + 1);
        } else if (direction === 'right' && currentIndex > 0) {
            onTabChange(currentIndex - 1);
        }
    };

    const handleTabSelect = (index: number) => {
        onTabChange(index);
        setIsExpanded(false);
        expandScale.value = withSpring(1);
    };

    const toggleExpand = () => {
        setIsExpanded(!isExpanded);
        expandScale.value = withSpring(isExpanded ? 1 : 1.02);
    };

    const panGesture = Gesture.Pan()
        .onUpdate((event) => {
            if (!isExpanded) {
                translateX.value = event.translationX * 0.3;
            }
        })
        .onEnd((event) => {
            if (!isExpanded) {
                if (event.translationX < -SWIPE_THRESHOLD) {
                    runOnJS(handleSwipe)('left');
                } else if (event.translationX > SWIPE_THRESHOLD) {
                    runOnJS(handleSwipe)('right');
                }
            }
            translateX.value = withSpring(0, { damping: 15, stiffness: 150 });
        });

    const animatedStyle = useAnimatedStyle(() => ({
        transform: [
            { translateX: translateX.value },
            { scale: expandScale.value },
        ],
    }));

    const currentTab = TABS[currentIndex];
    const canGoLeft = currentIndex > 0;
    const canGoRight = currentIndex < TABS.length - 1;

    return (
        <View style={styles.container}>
            <GestureDetector gesture={panGesture}>
                <Animated.View style={[styles.pillWrapper, animatedStyle]}>
                    <BlurView intensity={80} tint="light" style={styles.blurView}>
                        {isExpanded ? (
                            // Expanded: Show all tabs
                            <View style={styles.expandedContent}>
                                {TABS.map((tab, index) => (
                                    <TouchableOpacity
                                        key={tab.route}
                                        style={[
                                            styles.expandedTab,
                                            index === currentIndex && styles.expandedTabActive,
                                        ]}
                                        onPress={() => handleTabSelect(index)}
                                    >
                                        <Ionicons
                                            name={tab.icon}
                                            size={20}
                                            color={index === currentIndex ? Colors.accentSecondary : Colors.textSecondary}
                                        />
                                        <DonnaText
                                            style={[
                                                styles.expandedTabLabel,
                                                index === currentIndex && styles.expandedTabLabelActive,
                                            ]}
                                        >
                                            {tab.name}
                                        </DonnaText>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        ) : (
                            // Collapsed: Show current tab with arrows
                            <View style={styles.pillContent}>
                                {/* Left Arrow */}
                                <TouchableOpacity
                                    onPress={() => canGoLeft && onTabChange(currentIndex - 1)}
                                    style={styles.arrowButton}
                                    disabled={!canGoLeft}
                                >
                                    <Ionicons
                                        name="chevron-back"
                                        size={18}
                                        color={canGoLeft ? Colors.textSecondary : Colors.border}
                                    />
                                </TouchableOpacity>

                                {/* Active Tab - Tap to expand */}
                                <Pressable
                                    onPress={toggleExpand}
                                    style={styles.tabDisplay}
                                >
                                    <Ionicons
                                        name={currentTab.icon}
                                        size={20}
                                        color={Colors.accentSecondary}
                                    />
                                    <DonnaText style={styles.tabLabel}>
                                        {currentTab.name}
                                    </DonnaText>
                                    <Ionicons
                                        name="chevron-down"
                                        size={14}
                                        color={Colors.textMuted}
                                        style={{ marginLeft: 2 }}
                                    />
                                </Pressable>

                                {/* Right Arrow */}
                                <TouchableOpacity
                                    onPress={() => canGoRight && onTabChange(currentIndex + 1)}
                                    style={styles.arrowButton}
                                    disabled={!canGoRight}
                                >
                                    <Ionicons
                                        name="chevron-forward"
                                        size={18}
                                        color={canGoRight ? Colors.textSecondary : Colors.border}
                                    />
                                </TouchableOpacity>
                            </View>
                        )}
                    </BlurView>
                </Animated.View>
            </GestureDetector>

            {/* Tap outside to collapse */}
            {isExpanded && (
                <Pressable
                    style={styles.overlay}
                    onPress={() => {
                        setIsExpanded(false);
                        expandScale.value = withSpring(1);
                    }}
                />
            )}

            {/* Tab Dots Indicator - only when collapsed */}
            {!isExpanded && (
                <View style={styles.dotsContainer}>
                    {TABS.map((_, index) => (
                        <TouchableOpacity
                            key={index}
                            onPress={() => onTabChange(index)}
                            style={[
                                styles.dot,
                                index === currentIndex && styles.dotActive,
                            ]}
                        />
                    ))}
                </View>
            )}
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        position: 'absolute',
        bottom: 30,
        left: 0,
        right: 0,
        alignItems: 'center',
        zIndex: 100,
    },
    overlay: {
        position: 'absolute',
        top: -1000,
        left: -1000,
        right: -1000,
        bottom: -1000,
        zIndex: -1,
    },
    pillWrapper: {
        borderRadius: Radius.full,
        overflow: 'hidden',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.15,
        shadowRadius: 12,
        elevation: 8,
    },
    blurView: {
        borderRadius: Radius.full,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.4)',
    },
    pillContent: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm + 4,
        backgroundColor: 'rgba(255, 255, 255, 0.6)',
    },
    arrowButton: {
        padding: Spacing.xs,
    },
    tabDisplay: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        paddingHorizontal: Spacing.md,
    },
    tabLabel: {
        fontSize: 15,
        fontWeight: '600',
        color: Colors.textPrimary,
        fontFamily: 'Inter_600SemiBold',
    },
    // Expanded styles
    expandedContent: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: Spacing.sm,
        paddingVertical: Spacing.sm,
        backgroundColor: 'rgba(255, 255, 255, 0.85)',
        gap: Spacing.xs,
    },
    expandedTab: {
        flexDirection: 'column',
        alignItems: 'center',
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderRadius: Radius.component,
        gap: 4,
    },
    expandedTabActive: {
        backgroundColor: 'rgba(217, 119, 69, 0.1)', // Natural Copper at 10%
    },
    expandedTabLabel: {
        fontSize: 11,
        fontWeight: '500',
        color: Colors.textSecondary,
    },
    expandedTabLabelActive: {
        color: Colors.accentSecondary,
        fontWeight: '600',
    },
    // Dots
    dotsContainer: {
        flexDirection: 'row',
        gap: 6,
        marginTop: Spacing.sm,
    },
    dot: {
        width: 6,
        height: 6,
        borderRadius: 3,
        backgroundColor: Colors.border,
    },
    dotActive: {
        backgroundColor: Colors.accentSecondary,
        width: 18,
    },
});

export default AdaptivePillNav;
