import { api } from './api';

export interface CheckoutRequest {
    success_url: string;
    cancel_url: string;
}

export interface CheckoutResponse {
    checkout_url: string;
}

export interface TrialActivationResponse {
    status: 'activated' | 'active' | 'already_subscribed';
    trial_ends_at?: string;
    days_remaining?: number;
    subscription_tier?: string;
    message?: string;
}

export async function activateTrial(): Promise<TrialActivationResponse> {
    const response = await api.post<TrialActivationResponse>('/subscription/activate-trial', {});
    return response.data;
}

export async function createCheckout(request: CheckoutRequest): Promise<CheckoutResponse> {
    const response = await api.post<CheckoutResponse>('/billing/checkout', request);
    return response.data;
}

export async function triggerInitialSync(): Promise<void> {
    await api.post('/messages/gmail/sync/initial');
}
