/**
 * Billing & Subscription service - API functions for TanStack Query
 *
 * Note: Subscription STATUS is fetched via /settings endpoint (see AuthContext).
 * This service handles billing ACTIONS (checkout, portal, trial activation).
 */

import { api } from './api';

// ================================
// Types
// ================================

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

export interface TrialActivationResponse {
    status: 'activated' | 'active' | 'already_subscribed';
    trial_ends_at?: string;
    days_remaining?: number;
    subscription_tier?: string;
    message?: string;
}

// ================================
// Mutation Functions
// ================================

/**
 * Create a Polar checkout session for Pro subscription upgrade.
 * Returns a checkout URL to redirect the user to.
 */
export async function createCheckout(request: CheckoutRequest): Promise<CheckoutResponse> {
    const response = await api.post<CheckoutResponse>('/billing/checkout', request);
    return response.data;
}

/**
 * Get Polar customer portal URL for subscription management.
 * Users can manage their subscription, update payment methods, and view invoices.
 */
export async function getPortalUrl(): Promise<PortalResponse> {
    const response = await api.get<PortalResponse>('/billing/portal-url');
    return response.data;
}

export interface TrialActivationRequest {
    assistant_name?: string;
}

/**
 * Activate the user's 7-day free trial.
 * Called when user explicitly chooses to sync their real data.
 */
export async function activateTrial(request?: TrialActivationRequest): Promise<TrialActivationResponse> {
    const response = await api.post<TrialActivationResponse>('/subscription/activate-trial', request || {});
    return response.data;
}

/**
 * Trigger initial Gmail sync after trial activation.
 */
export async function triggerInitialSync(): Promise<void> {
    await api.post('/messages/gmail/sync/initial');
}
