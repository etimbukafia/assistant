import { API_BASE_URL } from './constants';
import { supabase } from './supabase';

/**
 * Authenticated fetch wrapper that automatically adds the Authorization header.
 *
 * @param {string} endpoint - API endpoint (without base URL)
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>} - Fetch response
 */
export async function apiFetch(endpoint, options = {}) {
    // Get current session
    const { data: { session } } = await supabase.auth.getSession();

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    // Add auth header if we have a session
    if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
    }

    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
        ...options,
        headers,
    });

    // Handle 401 - session might have expired
    if (response.status === 401) {
        // Try to refresh the session
        const { data: { session: newSession }, error } = await supabase.auth.refreshSession();

        if (newSession && !error) {
            // Retry with new token
            headers['Authorization'] = `Bearer ${newSession.access_token}`;
            return fetch(url, { ...options, headers });
        }

        // If refresh failed, the auth state listener will handle sign out
    }

    // Handle 402 - Subscription required
    if (response.status === 402) {
        try {
            const data = await response.clone().json();
            window.dispatchEvent(new CustomEvent('subscription-required', {
                detail: {
                    error: data.detail?.error || 'subscription_required',
                    message: data.detail?.message || 'This feature requires an active subscription.',
                    tier: data.detail?.tier,
                    status: data.detail?.status
                }
            }));
        } catch (e) {
            window.dispatchEvent(new CustomEvent('subscription-required', {
                detail: { error: 'subscription_required', message: 'Subscription required' }
            }));
        }
    }

    // Handle 403 - Feature gated (Pro tier required)
    if (response.status === 403) {
        try {
            const data = await response.clone().json();
            if (data.detail?.error === 'pro_required') {
                window.dispatchEvent(new CustomEvent('pro-required', {
                    detail: {
                        error: data.detail?.error || 'pro_required',
                        message: data.detail?.message || 'This feature requires a Pro subscription.',
                        currentTier: data.detail?.current_tier
                    }
                }));
            }
        } catch (e) {
            // Response might not be JSON
        }
    }

    return response;
}

/**
 * Convenience methods for common HTTP verbs
 */
export const api = {
    get: (endpoint, options = {}) =>
        apiFetch(endpoint, { ...options, method: 'GET' }),

    post: (endpoint, data, options = {}) =>
        apiFetch(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data)
        }),

    put: (endpoint, data, options = {}) =>
        apiFetch(endpoint, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data)
        }),

    delete: (endpoint, options = {}) =>
        apiFetch(endpoint, { ...options, method: 'DELETE' }),
};
