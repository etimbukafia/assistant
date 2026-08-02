import { api } from './api';

function buildIdempotencyKey(scope: string): string {
    try {
        return `${scope}:${crypto.randomUUID()}`;
    } catch {
        return `${scope}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
    }
}

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
    current_cycle?: 'monthly' | 'annual';
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
    const response = await api.post<CheckoutResponse>('/billing/checkout', request, {
        headers: { 'Idempotency-Key': buildIdempotencyKey('billing-checkout') },
    });
    return response.data;
}

export interface BillingPortalResponse {
    portal_url: string;
}

export interface BillingSubscriptionResponse {
    tier: string;
    status: string;
    is_active: boolean;
    trial_ends_at?: string | null;
    expires_at?: string | null;
    days_remaining: number;
    current_cycle?: 'monthly' | 'annual' | null;
    renews_at?: string | null;
}

export interface BillingPlanOptionsResponse {
    available_cycles: Array<'monthly' | 'annual'>;
    current_cycle?: 'monthly' | 'annual' | null;
    default_cycle: 'monthly' | 'annual';
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

export interface BillingInvoiceItem {
    invoice_id: number;
    provider_invoice_id?: string | null;
    issued_at?: string | null;
    total_minor?: number | null;
    currency: string;
    status: string;
    action_label?: string | null;
    action_url?: string | null;
}

export interface BillingInvoicesResponse {
    invoices: BillingInvoiceItem[];
}

export interface AdminTokenUsageProviderSummary {
    provider: string;
    request_count: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
}

export interface AdminTokenUsageBreakdownItem {
    provider: string;
    model: string;
    operation: string;
    request_count: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
    billable: boolean;
}

export interface AdminTokenUsageResponse {
    days: number;
    generated_at: string;
    filters: {
        user_id?: string | null;
        provider?: string | null;
        model?: string | null;
        operation?: string | null;
        limit: number;
    };
    total_requests: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_usd: number;
    providers: AdminTokenUsageProviderSummary[];
    breakdown: AdminTokenUsageBreakdownItem[];
}

export async function previewPlanChange(request: PlanChangePreviewRequest): Promise<PlanChangePreviewResponse> {
    const response = await api.post<PlanChangePreviewResponse>('/billing/plan-change/preview', request);
    return response.data;
}

export async function changePlan(request: PlanChangeRequest): Promise<PlanChangeResponse> {
    const response = await api.post<PlanChangeResponse>('/billing/plan-change', request, {
        headers: { 'Idempotency-Key': buildIdempotencyKey('billing-plan-change') },
    });
    return response.data;
}

export async function getBillingPortalUrl(): Promise<BillingPortalResponse> {
    const response = await api.get<BillingPortalResponse>('/billing/portal-url');
    return response.data;
}

export async function getBillingSubscription(): Promise<BillingSubscriptionResponse> {
    const response = await api.get<BillingSubscriptionResponse>('/billing/subscription');
    return response.data;
}

export async function getBillingPlanOptions(): Promise<BillingPlanOptionsResponse> {
    const response = await api.get<BillingPlanOptionsResponse>('/billing/plan-options');
    return response.data;
}

export async function listBillingInvoices(limit = 20): Promise<BillingInvoicesResponse> {
    const response = await api.get<BillingInvoicesResponse>('/billing/invoices', {
        params: { limit },
    });
    return response.data;
}

export async function cancelSubscription(): Promise<{ success: boolean; message: string }> {
    const response = await api.post<{ success: boolean; message: string }>(
        '/billing/cancel',
        {},
        { headers: { 'Idempotency-Key': buildIdempotencyKey('billing-cancel') } }
    );
    return response.data;
}

export async function getCreditStatus(): Promise<CreditStatusResponse> {
    const response = await api.get<CreditStatusResponse>('/billing/credits');
    return response.data;
}

export async function getAdminTokenUsage(params?: {
    days?: number;
    provider?: string;
    userId?: string;
    model?: string;
    operation?: string;
    limit?: number;
}): Promise<AdminTokenUsageResponse> {
    const response = await api.get<AdminTokenUsageResponse>('/billing/admin/token-usage', {
        params: {
            days: params?.days,
            provider: params?.provider,
            user_id: params?.userId,
            model: params?.model,
            operation: params?.operation,
            limit: params?.limit,
        },
    });
    return response.data;
}

export async function createCreditTopupCheckout(
    request: CreditTopupCheckoutRequest
): Promise<CreditTopupCheckoutResponse> {
    const response = await api.post<CreditTopupCheckoutResponse>('/billing/credits/top-up/checkout', request, {
        headers: { 'Idempotency-Key': buildIdempotencyKey('billing-topup') },
    });
    return response.data;
}

export async function triggerInitialSync(provider: 'google' | 'microsoft' = 'google'): Promise<void> {
    const path = provider === 'microsoft'
        ? '/messages/outlook/sync/initial'
        : '/messages/gmail/sync/initial';
    await api.post(path);
}
