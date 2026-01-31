import { api } from './api';

export interface CompleteOnboardingRequest {
    assistant_name?: string;
}

export interface CompleteOnboardingResponse {
    status: string;
    assistant_name: string;
}

/**
 * Complete user onboarding (for Pro checkout flow).
 * Sets assistant name and marks onboarding as completed.
 */
export async function completeOnboarding(
    request: CompleteOnboardingRequest
): Promise<CompleteOnboardingResponse> {
    const response = await api.post<CompleteOnboardingResponse>(
        '/onboarding/complete',
        request
    );
    return response.data;
}
