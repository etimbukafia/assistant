import FontAwesome from '@expo/vector-icons/FontAwesome';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import 'react-native-reanimated';
import { Colors } from '../src/theme/Theme';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

// Google Fonts
import {
  PlayfairDisplay_400Regular,
  PlayfairDisplay_600SemiBold,
} from '@expo-google-fonts/playfair-display';
import {
  Inter_400Regular,
} from '@expo-google-fonts/inter';
import { AuthProvider } from '../src/context/AuthContext';
import { ChatProvider, useChat } from '../src/context/ChatContext';
import { SyncCTAProvider } from '../src/context/SyncCTAContext';
import { OmniChatOverlay } from '../src/components/chat/OmniChatOverlay';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '../src/utils/queryClient';

export {
  // Catch any errors thrown by the Layout component.
  ErrorBoundary,
} from 'expo-router';

export const unstable_settings = {
  // Ensure that reloading on `/modal` keeps a back button present.
  initialRouteName: 'index',
};

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();

const DonnaTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: Colors.accentPrimary,
    background: Colors.bgBase,
    card: Colors.bgElevated,
    text: Colors.textPrimary,
    border: Colors.border,
    notification: Colors.accentPrimary,
  },
};

// Wrapper component to consume chat context
function GlobalChatOverlay() {
  const { isChatOpen, closeChat } = useChat();
  return <OmniChatOverlay isVisible={isChatOpen} onClose={closeChat} />;
}

import { CustomSplashScreen } from '../src/components/ui/CustomSplashScreen';
import { useState } from 'react';

export default function RootLayout() {
  const [appReady, setAppReady] = useState(false);
  const [loaded, error] = useFonts({
    PlayfairDisplay_600SemiBold,
    PlayfairDisplay_400Regular,
    Inter_400Regular,
    ...FontAwesome.font,
  });

  // Expo Router uses Error Boundaries to catch errors in the navigation tree.
  useEffect(() => {
    if (error) throw error;
  }, [error]);

  useEffect(() => {
    const prepare = async () => {
      if (loaded) {
        // Enforce minimum splash duration for branding impact
        await new Promise(resolve => setTimeout(resolve, 2000));

        try {
          await SplashScreen.hideAsync();
        } catch (e) {
          // Ignore
        } finally {
          setAppReady(true);
        }
      }
    };
    prepare();
  }, [loaded]);

  if (!appReady) {
    return <CustomSplashScreen />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ChatProvider>
        <AuthProvider>
          <SyncCTAProvider>
            <ThemeProvider value={DonnaTheme}>
              <GestureHandlerRootView style={{ flex: 1 }}>
                <Stack screenOptions={{ headerShown: false }}>
                  <Stack.Screen name="index" />
                  <Stack.Screen name="login" />
                  <Stack.Screen name="auth/welcome" />
                  <Stack.Screen name="auth/google/choose-account" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="auth/google/consent" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="auth/activation-explanation" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="chat" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="settings/profile" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="settings/activate_trial" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="settings/privacy" options={{ presentation: 'modal' }} />
                  <Stack.Screen name="(tabs)" options={{
                    headerShown: false,
                    presentation: 'card',
                    gestureEnabled: false,
                    animation: 'fade',
                  }} />
                </Stack>
                {/* Global OmniChat Overlay - appears on ALL screens */}
                <GlobalChatOverlay />
              </GestureHandlerRootView>
            </ThemeProvider>
          </SyncCTAProvider>
        </AuthProvider>
      </ChatProvider>
    </QueryClientProvider>
  );
}
