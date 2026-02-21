import axios, { AxiosError } from "axios";
import { createClient } from "@/utils/supabase/client";

const DEV_API_URL = "http://localhost:8000/v1";
const resolvedBaseURL = process.env.NEXT_PUBLIC_API_URL || DEV_API_URL;

export const api = axios.create({
    baseURL: resolvedBaseURL,
    timeout: 30000,
    headers: {
        "Content-Type": "application/json",
    },
});

let accessTokenCache: { token: string; expiresAtMs: number } | null = null;
let sessionReadInFlight: Promise<string | null> | null = null;
let refreshInFlight: Promise<string | null> | null = null;

function cacheToken(token: string, expiresAtSeconds?: number | null) {
    const fallbackExpiry = Date.now() + 45 * 60 * 1000;
    const expiresAtMs = expiresAtSeconds ? expiresAtSeconds * 1000 : fallbackExpiry;
    accessTokenCache = { token, expiresAtMs };
}

function getCachedToken(): string | null {
    if (!accessTokenCache) return null;
    if (Date.now() >= accessTokenCache.expiresAtMs - 30_000) {
        accessTokenCache = null;
        return null;
    }
    return accessTokenCache.token;
}

async function readSessionToken(): Promise<string | null> {
    const cached = getCachedToken();
    if (cached) return cached;

    if (!sessionReadInFlight) {
        sessionReadInFlight = (async () => {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                if (session?.access_token) {
                    cacheToken(session.access_token, session.expires_at ?? null);
                    return session.access_token;
                }
                return null;
            } finally {
                sessionReadInFlight = null;
            }
        })();
    }

    return sessionReadInFlight;
}

async function refreshTokenOnce(): Promise<string | null> {
    if (!refreshInFlight) {
        refreshInFlight = (async () => {
            try {
                const supabase = createClient();
                const { data: { session }, error } = await supabase.auth.refreshSession();
                if (error || !session?.access_token) return null;
                cacheToken(session.access_token, session.expires_at ?? null);
                return session.access_token;
            } finally {
                refreshInFlight = null;
            }
        })();
    }
    return refreshInFlight;
}

api.interceptors.request.use(async (config) => {
    if (config.headers.Authorization) return config;

    try {
        const token = await readSessionToken();
        if (token) config.headers.Authorization = `Bearer ${token}`;
    } catch (error) {
        console.error("Error attaching auth token:", error);
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as any;

        if (!error.response && error.code !== "ERR_CANCELED") {
            const networkError = new AxiosError(
                "Unable to connect. Please check your internet connection.",
                "NETWORK_ERROR",
                error.config,
                error.request
            );
            return Promise.reject(networkError);
        }

        if (error.response?.status === 401 && !originalRequest?._retry) {
            originalRequest._retry = true;

            try {
                const refreshed = await refreshTokenOnce();
                if (refreshed) {
                    originalRequest.headers.Authorization = `Bearer ${refreshed}`;
                    return api(originalRequest);
                }
            } catch (refreshError) {
                console.error("Session refresh failed:", refreshError);
            }
        }

        return Promise.reject(error);
    }
);

