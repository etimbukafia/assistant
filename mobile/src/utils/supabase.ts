/**
 * Supabase client configuration for React Native
 * 
 * Security: Uses expo-secure-store for encrypted token storage
 * instead of AsyncStorage (which is unencrypted).
 */

import 'react-native-url-polyfill/auto';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Environment variables - must be prefixed with EXPO_PUBLIC_
const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || '';

// Flag to check if Supabase is properly configured
export const isSupabaseConfigured = !!(SUPABASE_URL && SUPABASE_ANON_KEY);

if (!isSupabaseConfigured) {
    console.warn(
        'Supabase credentials not configured. Using mock auth mode. ' +
        'Set EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY in your .env file for real auth.'
    );
}

/**
 * Custom storage adapter using expo-secure-store for encrypted persistence.
 * 
 * Note: expo-secure-store has a 2KB limit per key, which is sufficient
 * for JWT tokens but may require chunking for larger data.
 */
const SecureStoreAdapter = {
    getItem: async (key: string): Promise<string | null> => {
        try {
            // Web compatibility
            if (Platform.OS === 'web') {
                if (typeof localStorage !== 'undefined') {
                    return localStorage.getItem(key);
                }
                return null; // Return null if localStorage unavailable on web
            }
            // Native
            return await SecureStore.getItemAsync(key);
        } catch (error) {
            console.error('SecureStore getItem error:', error);
            return null;
        }
    },

    setItem: async (key: string, value: string): Promise<void> => {
        try {
            if (Platform.OS === 'web') {
                if (typeof localStorage !== 'undefined') {
                    localStorage.setItem(key, value);
                }
                return;
            }
            await SecureStore.setItemAsync(key, value);
        } catch (error) {
            console.error('SecureStore setItem error:', error);
        }
    },

    removeItem: async (key: string): Promise<void> => {
        try {
            if (Platform.OS === 'web') {
                if (typeof localStorage !== 'undefined') {
                    localStorage.removeItem(key);
                }
                return;
            }
            await SecureStore.deleteItemAsync(key);
        } catch (error) {
            console.error('SecureStore removeItem error:', error);
        }
    },
};

// Only create real Supabase client if configured, otherwise use a mock-safe placeholder
let supabase: SupabaseClient;

if (isSupabaseConfigured) {
    supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        auth: {
            storage: SecureStoreAdapter,
            autoRefreshToken: true,
            persistSession: true,
            // On web/PWA, Supabase must detect the OAuth tokens in the URL hash
            // and clean them up. On native, this must be false to avoid conflicts
            // with Expo deep linking (tokens are handled by expo-auth-session).
            detectSessionInUrl: Platform.OS === 'web',
        },
    });
} else {
    // Create a placeholder client with dummy URL for mock mode
    // This won't make real API calls but prevents crashes
    supabase = createClient('https://placeholder.supabase.co', 'placeholder-key', {
        auth: {
            storage: SecureStoreAdapter,
            autoRefreshToken: false,
            persistSession: false,
            detectSessionInUrl: false,
        },
    });
}

export { supabase, SUPABASE_URL, SUPABASE_ANON_KEY };
