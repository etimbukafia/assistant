/**
 * Digest preferences service - API functions for TanStack Query
 */

import { api } from './api';

// ================================
// Types
// ================================

export interface DigestTimeConfig {
    enabled: boolean;
    time: string; // HH:MM format
    include?: string[];
}

export interface WeeklyDigestConfig {
    enabled: boolean;
    day: string;
    time: string; // HH:MM format
    include?: string[];
}

export interface DigestPreferences {
    enabled?: boolean;
    morning_briefing?: DigestTimeConfig;
    end_of_day?: DigestTimeConfig;
    weekly_review?: WeeklyDigestConfig;
    delivery_channel?: string;
}

// ================================
// API Functions
// ================================

/**
 * Fetch current digest preferences from backend
 */
export async function fetchDigestPreferences(): Promise<DigestPreferences> {
    const response = await api.get('/digests/settings');
    return response.data.preferences || {};
}

/**
 * Update digest preferences on backend
 */
export async function updateDigestPreferences(
    preferences: DigestPreferences
): Promise<DigestPreferences> {
    const response = await api.put('/digests/settings', preferences);
    return response.data.preferences;
}
