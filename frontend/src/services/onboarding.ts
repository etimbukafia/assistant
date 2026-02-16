import { api } from './api';

export interface CompleteOnboardingRequest {
    assistant_name?: string;
}

export interface CompleteOnboardingResponse {
    status: string;
    assistant_name: string;
}

export async function completeOnboarding(
    request: CompleteOnboardingRequest
): Promise<CompleteOnboardingResponse> {
    const response = await api.post<CompleteOnboardingResponse>(
        '/onboarding/complete',
        request
    );
    return response.data;
}
