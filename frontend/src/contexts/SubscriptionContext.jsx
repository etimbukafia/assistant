import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { API_BASE_URL } from '../utils/constants';

const SubscriptionContext = createContext({});

export const useSubscription = () => useContext(SubscriptionContext);

export const SubscriptionProvider = ({ children }) => {
    const { session } = useAuth();
    const [subscription, setSubscription] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchSubscription = useCallback(async () => {
        if (!session?.access_token) {
            setLoading(false);
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/billing/subscription`, {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to fetch subscription');
            }

            const data = await response.json();
            setSubscription(data);
            setError(null);
        } catch (err) {
            console.error('Error fetching subscription:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [session?.access_token]);

    // Fetch subscription on mount and when session changes
    useEffect(() => {
        fetchSubscription();
    }, [fetchSubscription]);

    // Listen for trial-expired event from API error handling
    useEffect(() => {
        const handleTrialExpired = () => {
            fetchSubscription();
        };

        window.addEventListener('trial-expired', handleTrialExpired);
        return () => window.removeEventListener('trial-expired', handleTrialExpired);
    }, [fetchSubscription]);

    const createCheckout = async (successUrl, cancelUrl) => {
        if (!session?.access_token) {
            throw new Error('Not authenticated');
        }

        const response = await fetch(`${API_BASE_URL}/billing/checkout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                success_url: successUrl,
                cancel_url: cancelUrl,
            }),
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to create checkout');
        }

        const data = await response.json();
        return data.checkout_url;
    };

    const cancelSubscription = async () => {
        if (!session?.access_token) {
            throw new Error('Not authenticated');
        }

        const response = await fetch(`${API_BASE_URL}/billing/cancel`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
            },
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to cancel subscription');
        }

        const data = await response.json();
        await fetchSubscription(); // Refresh subscription state
        return data;
    };

    const getPortalUrl = async () => {
        if (!session?.access_token) {
            throw new Error('Not authenticated');
        }

        const response = await fetch(`${API_BASE_URL}/billing/portal-url`, {
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
            },
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to get portal URL');
        }

        const data = await response.json();
        return data.portal_url;
    };

    const value = {
        // Subscription state
        tier: subscription?.tier || 'trial',
        status: subscription?.status || 'trialing',
        isActive: subscription?.is_active ?? false,
        trialEndsAt: subscription?.trial_ends_at ? new Date(subscription.trial_ends_at) : null,
        expiresAt: subscription?.expires_at ? new Date(subscription.expires_at) : null,
        daysRemaining: subscription?.days_remaining,

        // Computed helpers
        isProUser: subscription?.tier === 'pro',
        isTrialUser: subscription?.tier === 'trial',
        isTrialExpired: subscription?.tier === 'trial' && !subscription?.is_active,
        isCanceled: subscription?.status === 'canceled',

        // Loading/error state
        loading,
        error,

        // Actions
        refresh: fetchSubscription,
        createCheckout,
        cancelSubscription,
        getPortalUrl,
    };

    return (
        <SubscriptionContext.Provider value={value}>
            {children}
        </SubscriptionContext.Provider>
    );
};

export default SubscriptionContext;
