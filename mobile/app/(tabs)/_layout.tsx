import React, { useState, useCallback } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { Tabs, usePathname, useRouter } from 'expo-router';
import { Colors, Spacing, Radius } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { TrialBadge } from '../../src/components/ui/TrialBadge';
import { useAuth } from '../../src/context/AuthContext';
import { useChat } from '../../src/context/ChatContext';
import { useUnreadCount, usePushNotificationSetup } from '../../src/hooks/useNotifications';
import { TouchableOpacity, View, Dimensions, StyleSheet } from 'react-native';
import { AdaptivePillNav } from '../../src/components/navigation/AdaptivePillNav';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { runOnJS } from 'react-native-reanimated';

import { OnboardingSheet } from '../../src/components/ui/OnboardingSheet';
import { useFocusEffect } from 'expo-router';

const SCREEN_WIDTH = Dimensions.get('window').width;
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.25; // 25% of screen width

const TAB_ROUTES = ['index', 'focus', 'calendar', 'chat'];

function TabBarIcon(props: {
  name: React.ComponentProps<typeof Ionicons>['name'];
  color: string;
}) {
  return <Ionicons size={24} style={{ marginBottom: -3 }} {...props} />;
}

export default function TabLayout() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const { openChat } = useChat(); // Use global context
  const { unreadCount } = useUnreadCount();
  const { subscriptionTier, onboardingCompleted, refreshProfile } = useAuth();

  const [showOnboarding, setShowOnboarding] = useState(false);

  // Check for pending onboarding when screen focuses or auth state changes
  React.useEffect(() => {
    if (subscriptionTier === 'pro' && !onboardingCompleted) {
      setShowOnboarding(true);
    }
  }, [subscriptionTier, onboardingCompleted]);

  const handleOnboardingComplete = async () => {
    await refreshProfile();
    setShowOnboarding(false);
  };

  usePushNotificationSetup();

  // Determine current tab index from pathname
  const getCurrentIndex = useCallback(() => {
    const currentRoute = pathname.split('/').pop() || 'index';
    const index = TAB_ROUTES.indexOf(currentRoute);
    return index >= 0 ? index : 0;
  }, [pathname]);

  const [currentIndex, setCurrentIndex] = useState(getCurrentIndex());

  // Update index when pathname changes
  React.useEffect(() => {
    setCurrentIndex(getCurrentIndex());
  }, [pathname, getCurrentIndex]);

  const handleTabChange = useCallback((index: number) => {
    const route = TAB_ROUTES[index];

    setCurrentIndex(index);
    // For index (Inbox), navigate to root of tabs group
    if (route === 'index') {
      router.replace('/(tabs)' as any);
    } else {
      router.replace(`/(tabs)/${route}` as any);
    }
  }, [router]);

  // Handle swipe to navigate between tabs
  const handleSwipe = useCallback((direction: 'left' | 'right') => {
    if (direction === 'left' && currentIndex < TAB_ROUTES.length - 1) {
      handleTabChange(currentIndex + 1);
    } else if (direction === 'right' && currentIndex > 0) {
      handleTabChange(currentIndex - 1);
    }
  }, [currentIndex, handleTabChange]);

  // Screen-level swipe gesture for tab navigation
  const screenSwipeGesture = Gesture.Pan()
    .activeOffsetX([-20, 20]) // Minimum horizontal movement to activate
    .failOffsetY([-20, 20]) // Cancel if vertical movement exceeds this
    .onEnd((event) => {
      if (event.translationX < -SWIPE_THRESHOLD) {
        runOnJS(handleSwipe)('left');
      } else if (event.translationX > SWIPE_THRESHOLD) {
        runOnJS(handleSwipe)('right');
      }
    });

  // Get user initial from Supabase user_metadata (populated by Google OAuth)
  const userName = user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email;
  const initial = userName?.[0]?.toUpperCase() || '?';

  return (
    <GestureDetector gesture={screenSwipeGesture}>
      <Animated.View style={{ flex: 1 }}>
        <Tabs
          screenOptions={{
            tabBarActiveTintColor: Colors.accentSecondary,
            tabBarInactiveTintColor: Colors.textMuted,
            // Hide the default tab bar - we use AdaptivePillNav instead
            tabBarStyle: {
              display: 'none',
            },
            headerStyle: {
              backgroundColor: Colors.bgBase,
            },
            headerTitleStyle: {
              color: Colors.textPrimary,
              fontFamily: 'PlayfairDisplay_600SemiBold',
              fontSize: 20,
            },
            headerTitle: '',
            headerTitleAlign: 'center',
            headerLeft: () => (
              <TouchableOpacity
                onPress={() => router.push('/(tabs)/settings' as any)}
                style={{ marginLeft: 16 }}
              >
                <View style={{
                  width: 32,
                  height: 32,
                  borderRadius: 16,
                  backgroundColor: Colors.accentSecondary,
                  justifyContent: 'center',
                  alignItems: 'center'
                }}>
                  <DonnaText style={{ color: 'white', fontSize: 16, fontFamily: 'PlayfairDisplay_600SemiBold' }}>{initial}</DonnaText>
                </View>
              </TouchableOpacity>
            ),
            headerRight: () => (
              <View style={{ flexDirection: 'row', marginRight: 16, gap: 12, alignItems: 'center' }}>
                <TrialBadge />
                <TouchableOpacity onPress={() => router.push('/notifications' as any)}>
                  <Ionicons name="notifications-outline" size={22} color={Colors.textPrimary} />
                  {unreadCount > 0 && (
                    <View style={{
                      position: 'absolute',
                      top: -4,
                      right: -6,
                      minWidth: 16,
                      height: 16,
                      borderRadius: 8,
                      backgroundColor: Colors.error,
                      justifyContent: 'center',
                      alignItems: 'center',
                      paddingHorizontal: 3,
                    }}>
                      <DonnaText style={{ color: '#FFF', fontSize: 10, fontWeight: '700' }}>
                        {unreadCount > 99 ? '99+' : unreadCount}
                      </DonnaText>
                    </View>
                  )}
                </TouchableOpacity>
              </View>
            ),
          }}>
          <Tabs.Screen
            name="index"
            options={{
              title: 'Inbox',
              tabBarIcon: ({ color }) => <TabBarIcon name="mail" color={color} />,
              headerShown: true,
            }}
          />
          <Tabs.Screen
            name="focus"
            options={{
              title: 'Focus',
              tabBarIcon: ({ color }) => <TabBarIcon name="flash" color={color} />,
            }}
          />
          <Tabs.Screen
            name="calendar"
            options={{
              title: 'Schedule',
              tabBarIcon: ({ color }) => <TabBarIcon name="calendar" color={color} />,
            }}
          />
          <Tabs.Screen
            name="settings"
            options={{
              title: 'Settings',
              tabBarIcon: ({ color }) => <TabBarIcon name="settings-outline" color={color} />,
              href: null, // Hide from tab bar - access via avatar only
            }}
          />
          <Tabs.Screen
            name="chat"
            options={{
              title: 'Chat',
              tabBarIcon: ({ color }) => <TabBarIcon name="chatbubbles" color={color} />,
            }}
          />
        </Tabs>

        {/* Adaptive Pill Navigation */}
        <AdaptivePillNav
          currentIndex={currentIndex}
          onTabChange={handleTabChange}
        />

        {/* Chat FAB */}
        <TouchableOpacity style={styles.chatFab} onPress={openChat}>
          <Ionicons name="sparkles" size={24} color="#FFF" />
        </TouchableOpacity>

        <OnboardingSheet
          isOpen={showOnboarding}
          onComplete={handleOnboardingComplete}
        />
      </Animated.View>
    </GestureDetector >
  );
}

const styles = StyleSheet.create({
  chatFab: {
    position: 'absolute',
    bottom: 100,
    right: Spacing.md,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.accentSecondary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 6,
    zIndex: 50,
  },
});
