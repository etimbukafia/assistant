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
    // Skip if caller already set Authorization (e.g. fetchSettings with explicit token)
    if (config.headers.Authorization) return config;

    try {
        const supabase = createClient();
        let { data: { session } } = await supabase.auth.getSession();

        // Supabase loads the session from storage asynchronously on first render.
        // If we get null, wait briefly and retry before sending a tokenless request
        // (which would cause a 401 → refresh → retry cycle and slow down page load).
        if (!session?.access_token) {
            await new Promise(r => setTimeout(r, 300));
            const { data: { session: retried } } = await supabase.auth.getSession();
            session = retried;
        }

        // Still no session - try a full refresh before giving up
        if (!session?.access_token) {
            const { data: { session: refreshed } } = await supabase.auth.refreshSession();
            session = refreshed;
        }

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
