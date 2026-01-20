/**
 * Billing & Subscription service - API functions for TanStack Query
 */

import { api } from './api';

// ================================
// Types
// ================================

export interface SubscriptionData {
    tier: 'trial' | 'pro';
    status: 'trialing' | 'active' | 'canceled' | 'past_due' | 'expired';
    is_active: boolean;
    trial_ends_at: string | null;
    expires_at: string | null;
    days_remaining: number;
}

export interface CheckoutRequest {
    success_url: string;
    cancel_url: string;
}

export interface CheckoutResponse {
    checkout_url: string;
}

export interface PortalResponse {
    portal_url: string;
}

// ================================
// Query Functions
// ================================

/**
 * Fetch current subscription status
 */
export async function fetchSubscription(): Promise<SubscriptionData> {
    const response = await api.get('/billing/subscription');
    return response.data;
}

// ================================
// Mutation Functions
// ================================

/**
 * Create a Stripe checkout session for upgrade
 */
export async function createCheckout(request: CheckoutRequest): Promise<CheckoutResponse> {
    const response = await api.post('/billing/checkout', request);
    return response.data;
}

/**
 * Get Stripe customer portal URL for subscription management
 */
export async function getPortalUrl(): Promise<PortalResponse> {
    const response = await api.get('/billing/portal-url');
    return response.data;
}

/**
 * Activate the user's free trial
 */
export async function activateTrial(): Promise<void> {
    await api.post('/subscription/activate-trial');
}

/**
 * Trigger initial Gmail sync after trial activation
 */
export async function triggerInitialSync(): Promise<void> {
    await api.post('/messages/gmail/sync/initial');
}
