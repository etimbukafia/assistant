/**
 * API service configured to use Supabase authentication
 *
 * Automatically attaches JWT tokens from Supabase auth to all requests.
 */

import axios, { AxiosError } from 'axios';
import { Platform } from 'react-native';
import { supabase } from '../utils/supabase';

// Use localhost for iOS simulator, 10.0.2.2 for Android emulator
const DEV_API_URL = Platform.OS === 'android'
    ? 'http://10.0.2.2:8000/v1'
    : 'http://localhost:8000/v1';

export const api = axios.create({
    baseURL: process.env.EXPO_PUBLIC_API_URL || DEV_API_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add auth interceptor using Supabase session
api.interceptors.request.use(async (config) => {
    try {
        const { data: { session } } = await supabase.auth.getSession();

        if (session?.access_token) {
            config.headers.Authorization = `Bearer ${session.access_token}`;
        }
    } catch (error) {
        console.error('Error attaching auth token:', error);
    }
    return config;
});

// Handle errors - refresh on 401, detect network issues
api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // Network error detection (no response = offline or server unreachable)
        if (!error.response && error.code !== 'ERR_CANCELED') {
            const networkError = new AxiosError(
                'Unable to connect. Please check your internet connection.',
                'NETWORK_ERROR',
                error.config,
                error.request
            );
            return Promise.reject(networkError);
        }

        // Handle 401 - try to refresh session
        if (error.response?.status === 401 && !originalRequest?._retry) {
            originalRequest._retry = true;

            try {
                const { data: { session }, error: refreshError } =
                    await supabase.auth.refreshSession();

                if (session && !refreshError) {
                    originalRequest.headers.Authorization = `Bearer ${session.access_token}`;
                    return api(originalRequest);
                }
            } catch (refreshError) {
                console.error('Session refresh failed:', refreshError);
            }
        }

        return Promise.reject(error);
    }
);
