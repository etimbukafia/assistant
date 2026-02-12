/**
 * Gmail Connection Service
 *
 * Handles connecting Gmail to the backend using the Google provider token
 * from Supabase OAuth.
 */

import { api } from './api';

export interface ConnectGmailRequest {
    provider_token: string;
    provider_refresh_token?: string;
    email: string;
}

export interface ConnectGmailResponse {
    status: string;
    message: string;
    email: string;
}

/**
 * Connect Gmail using the Google provider token from Supabase.
 *
 * This sends the provider_token to the backend which stores it
 * for Gmail API access (reading emails, syncing, etc.)
 */
export async function connectGmail(request: ConnectGmailRequest): Promise<ConnectGmailResponse> {
    const response = await api.post<ConnectGmailResponse>('/auth/gmail/connect', request);
    return response.data;
}
