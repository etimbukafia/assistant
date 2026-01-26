import React, { useState, useCallback } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { Tabs, usePathname, useRouter } from 'expo-router';
import { Colors } from '../../src/theme/Theme';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { useChat } from '../../src/context/ChatContext';
import { TouchableOpacity, View } from 'react-native';
import { AdaptivePillNav } from '../../src/components/navigation/AdaptivePillNav';

const TAB_ROUTES = ['index', 'focus', 'calendar', 'settings'];

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

  const handleTabChange = (index: number) => {
    const route = TAB_ROUTES[index];

    // If Chat tab selected (not in routes anymore but just for safety)
    if (route === 'chat') {
      openChat();
      return;
    }

    setCurrentIndex(index);
    // For index (Inbox), navigate to root of tabs group
    if (route === 'index') {
      router.replace('/(tabs)' as any);
    } else {
      router.replace(`/(tabs)/${route}` as any);
    }
  };

  // Get user initial from Supabase user_metadata (populated by Google OAuth)
  const userName = user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email;
  const initial = userName?.[0]?.toUpperCase() || '?';

  return (
    <View style={{ flex: 1 }}>
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
            <View style={{ flexDirection: 'row', marginRight: 16, gap: 16 }}>
              <TouchableOpacity><Ionicons name="search" size={22} color={Colors.textPrimary} /></TouchableOpacity>
              <TouchableOpacity><Ionicons name="notifications-outline" size={22} color={Colors.textPrimary} /></TouchableOpacity>
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
          }}
        />
        <Tabs.Screen
          name="chat"
          options={{
            title: 'Chat',
            tabBarIcon: ({ color }) => <TabBarIcon name="chatbubbles-outline" color={color} />,
            href: null, // Hide from tab bar
          }}
        />
      </Tabs>

      {/* Adaptive Pill Navigation */}
      <AdaptivePillNav
        currentIndex={currentIndex}
        onTabChange={handleTabChange}
      />
    </View>
  );
}
