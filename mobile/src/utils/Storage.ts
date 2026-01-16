import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

/**
 * A cross-platform wrapper for SecureStore.
 * Falls back to localStorage on web since SecureStore is not supported there.
 */
export const Storage = {
    setItem: async (key: string, value: string) => {
        if (Platform.OS === 'web') {
            try {
                localStorage.setItem(key, value);
            } catch (e) {
                console.error('LocalStorage setItem failed:', e);
            }
        } else {
            await SecureStore.setItemAsync(key, value);
        }
    },

    getItem: async (key: string) => {
        if (Platform.OS === 'web') {
            try {
                return localStorage.getItem(key);
            } catch (e) {
                console.error('LocalStorage getItem failed:', e);
                return null;
            }
        } else {
            return await SecureStore.getItemAsync(key);
        }
    },

    deleteItem: async (key: string) => {
        if (Platform.OS === 'web') {
            try {
                localStorage.removeItem(key);
            } catch (e) {
                console.error('LocalStorage removeItem failed:', e);
            }
        } else {
            await SecureStore.deleteItemAsync(key);
        }
    }
};
