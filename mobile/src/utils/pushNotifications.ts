/**
 * Push notification utilities
 *
 * Handles permission requests, token retrieval, and notification setup.
 * Uses Expo Push Notifications (not Firebase directly).
 */

import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Configure notification behavior when app is foregrounded
Notifications.setNotificationHandler({
    handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: false,
        shouldSetBadge: true,
    }),
});

/**
 * Request permission and get Expo push token.
 * Returns null if permissions denied or not a physical device.
 */
export async function getExpoPushToken(): Promise<string | null> {
    if (!Device.isDevice) {
        console.log('Push notifications require a physical device');
        return null;
    }

    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
    }

    if (finalStatus !== 'granted') {
        console.log('Push notification permission denied');
        return null;
    }

    if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
            name: 'Default',
            importance: Notifications.AndroidImportance.HIGH,
            vibrationPattern: [0, 250, 250, 250],
            lightColor: '#D97745',
        });
    }

    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    const tokenData = await Notifications.getExpoPushTokenAsync({
        projectId,
    });

    return tokenData.data;
}

/**
 * Get device info for token registration.
 */
export function getDeviceInfo(): { device_name: string; platform: string } {
    return {
        device_name: Device.modelName || 'Unknown',
        platform: Platform.OS,
    };
}
