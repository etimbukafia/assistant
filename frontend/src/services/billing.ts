import { api } from './api';

export interface CheckoutRequest {
    success_url: string;
    cancel_url: string;
    plan_cycle?: 'monthly' | 'annual';
}

export interface CheckoutResponse {
    checkout_url: string;
}

export interface PlanChangePreviewRequest {
    target_cycle: 'monthly' | 'annual';
}

export interface PlanChangePreviewResponse {
    target_cycle: 'monthly' | 'annual';
    current_cycle?: 'monthly' | 'annual' | null;
    change_direction?: 'upgrade' | 'downgrade' | 'lateral' | 'unknown';
    effective_timing?: 'immediate' | 'next_cycle';
    effective_at?: string | null;
    amount_due_today?: number | null;
    currency?: string | null;
    message: string;
}

export interface PlanChangeRequest {
    target_cycle: 'monthly' | 'annual';
    current_cycle?: 'monthly' | 'annual';
}

export interface PlanChangeResponse {
    success: boolean;
    current_cycle?: 'monthly' | 'annual' | null;
    change_direction?: 'upgrade' | 'downgrade' | 'lateral' | 'unknown';
    effective_timing?: 'immediate' | 'next_cycle';
    effective_at?: string | null;
    message: string;
    amount_due_today?: number | null;
    currency?: string | null;
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

export interface BillingPortalResponse {
    portal_url: string;
}

export interface CreditStatusResponse {
    credits_used: number;
    credits_limit: number;
    credits_remaining: number;
    percentage_used: number;
    is_exhausted: boolean;
    period_start: string | null;
    tier: string;
}

export interface CreditTopupCheckoutRequest {
    amount_usd: number;
    success_url: string;
    cancel_url: string;
}

export interface CreditTopupCheckoutResponse {
    checkout_url: string;
    amount_usd: number;
    credits_to_add: number;
    message: string;
}

export async function previewPlanChange(request: PlanChangePreviewRequest): Promise<PlanChangePreviewResponse> {
    const response = await api.post<PlanChangePreviewResponse>('/billing/plan-change/preview', request);
    return response.data;
}

export async function changePlan(request: PlanChangeRequest): Promise<PlanChangeResponse> {
    const response = await api.post<PlanChangeResponse>('/billing/plan-change', request);
    return response.data;
}

export async function getBillingPortalUrl(): Promise<BillingPortalResponse> {
    const response = await api.get<BillingPortalResponse>('/billing/portal-url');
    return response.data;
}

export async function getCreditStatus(): Promise<CreditStatusResponse> {
    const response = await api.get<CreditStatusResponse>('/billing/credits');
    return response.data;
}

export async function createCreditTopupCheckout(
    request: CreditTopupCheckoutRequest
): Promise<CreditTopupCheckoutResponse> {
    const response = await api.post<CreditTopupCheckoutResponse>('/billing/credits/top-up/checkout', request);
    return response.data;
}

export async function triggerInitialSync(provider: 'google' | 'microsoft' = 'google'): Promise<void> {
    const path = provider === 'microsoft'
        ? '/messages/outlook/sync/initial'
        : '/messages/gmail/sync/initial';
    await api.post(path);
}
