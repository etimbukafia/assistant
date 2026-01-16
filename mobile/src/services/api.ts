import axios from 'axios';
import { Storage } from '../utils/Storage';
import { Platform } from 'react-native';

// Use localhost for iOS simulator, 10.0.2.2 for Android emulator
const DEV_API_URL = Platform.OS === 'android'
    ? 'http://10.0.2.2:8000/v1'
    : 'http://localhost:8000/v1';

export const api = axios.create({
    baseURL: process.env.EXPO_PUBLIC_API_URL || DEV_API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add auth interceptor
api.interceptors.request.use(async (config) => {
    try {
        const token = await Storage.getItem('auth_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    } catch (error) {
        console.error('Error attaching auth token', error);
    }
    return config;
});
