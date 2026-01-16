import React from 'react';
import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { Colors } from '../../src/theme/Theme';
import { ChatButton } from '../../src/components/ui/ChatButton';
import { DonnaText } from '../../src/components/ui/DonnaText';
import { useAuth } from '../../src/context/AuthContext';
import { TouchableOpacity, View } from 'react-native';
import { useRouter } from 'expo-router';

function TabBarIcon(props: {
  name: React.ComponentProps<typeof Ionicons>['name'];
  color: string;
}) {
  return <Ionicons size={24} style={{ marginBottom: -3 }} {...props} />;
}

export default function TabLayout() {
  return (
    <>
      <Tabs
        screenOptions={{
          tabBarActiveTintColor: Colors.accentSecondary,
          tabBarInactiveTintColor: Colors.textMuted,
          tabBarStyle: {
            backgroundColor: Colors.bgElevated,
            borderTopColor: Colors.border,
            height: 85,
            paddingBottom: 25,
            paddingTop: 10,
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
          headerLeft: () => {
            const router = useRouter();
            const { user } = useAuth(); // Get user context
            const initial = user?.name?.[0] || '?';

            return (
              <TouchableOpacity
                onPress={() => router.push('/settings/profile' as any)}
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
            );
          },
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
          name="chat"
          options={{
            title: 'Chat',
            tabBarIcon: ({ color }) => <TabBarIcon name="chatbubbles-outline" color={color} />,
          }}
        />
      </Tabs>
      {/* Chat is now a tab, removed floating ChatButton */}
    </>
  );
}
