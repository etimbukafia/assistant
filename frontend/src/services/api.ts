import axios, { AxiosError } from 'axios';
import { createClient } from '@/utils/supabase/client';

// Use localhost for development, environment variable for production
const DEV_API_URL = 'http://localhost:8000/v1';
const resolvedBaseURL = process.env.NEXT_PUBLIC_API_URL || DEV_API_URL;

export const api = axios.create({
    baseURL: resolvedBaseURL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add auth interceptor using Supabase session
api.interceptors.request.use(async (config) => {
    try {
        const supabase = createClient();
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
                const supabase = createClient();
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
