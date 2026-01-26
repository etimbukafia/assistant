/**
 * Memory API Service
 *
 * Functions for user preferences and contact context operations.
 */

import { api } from './api';

// ================================
// Types
// ================================

export interface PrincipalMemory {
    id: number;
    user_id: string;
    key: string;
    value: string;
    context_type: 'drafting' | 'scheduling' | 'task_review' | 'communication' | 'tasks' | 'general';
    source: 'manual' | 'approved_suggestion';
    created_at: string;
    updated_at: string;
}

export interface PrincipalMemoryListResponse {
    preferences: PrincipalMemory[];
    total: number;
}

export interface CreatePreferenceRequest {
    key: string;
    value: string;
    context_type: string;
    source?: string;
}

export interface UpdatePreferenceRequest {
    key?: string;
    value?: string;
    context_type?: string;
}

export interface DecisionPattern {
    id: number;
    user_id: string;
    pattern_key: string;
    pattern_type: string;
    context: Record<string, any>;
    observed_frequency: number;
    confidence_score: number;
    is_approved: boolean | null;
    created_at: string;
    updated_at: string;
}

export interface DecisionPatternListResponse {
    patterns: DecisionPattern[];
    total: number;
}

export interface ContactContext {
    id: number;
    user_id: string;
    contact_email: string;
    contact_name?: string;
    contact_metadata: Record<string, any>;
    notes?: string;
    category?: 'vip' | 'colleague' | 'external' | 'vendor';
    preferred_tone?: 'formal' | 'neutral' | 'casual';
    created_at: string;
    updated_at: string;
}

export interface ContactContextListResponse {
    contacts: ContactContext[];
    total: number;
}

export interface UpdateContactRequest {
    contact_name?: string;
    notes?: string;
    category?: string;
    preferred_tone?: string;
}

// ================================
// Preferences API
// ================================

/**
 * Fetch all user preferences
 */
export async function fetchPreferences(): Promise<PrincipalMemoryListResponse> {
    const response = await api.get<PrincipalMemoryListResponse>('/memory/preferences');
    return response.data;
}

/**
 * Create a new preference
 */
export async function createPreference(request: CreatePreferenceRequest): Promise<PrincipalMemory> {
    const response = await api.post<PrincipalMemory>('/memory/preferences', request);
    return response.data;
}

/**
 * Update an existing preference
 */
export async function updatePreference(
    preferenceId: number,
    request: UpdatePreferenceRequest
): Promise<PrincipalMemory> {
    const response = await api.put<PrincipalMemory>(`/memory/preferences/${preferenceId}`, request);
    return response.data;
}

/**
 * Delete a preference
 */
export async function deletePreference(preferenceId: number): Promise<void> {
    await api.delete(`/memory/preferences/${preferenceId}`);
}

// ================================
// Decision Patterns API
// ================================

/**
 * Fetch all decision patterns (approved ones)
 */
export async function fetchPatterns(): Promise<DecisionPatternListResponse> {
    const response = await api.get<DecisionPatternListResponse>('/memory/patterns');
    return response.data;
}

/**
 * Fetch pattern suggestions (pending approval)
 */
export async function fetchPatternSuggestions(): Promise<DecisionPatternListResponse> {
    const response = await api.get<DecisionPatternListResponse>('/memory/patterns/suggestions');
    return response.data;
}

/**
 * Take action on a pattern (approve, reject, not_now)
 */
export async function actionPattern(
    patternId: number,
    action: 'approve' | 'reject' | 'not_now'
): Promise<{ success: boolean; message: string }> {
    const response = await api.post<{ success: boolean; message: string }>(
        `/memory/patterns/${patternId}/action`,
        { action }
    );
    return response.data;
}

// ================================
// Contacts API
// ================================

/**
 * Fetch all contact contexts
 */
export async function fetchContacts(category?: string): Promise<ContactContextListResponse> {
    const params = category ? `?category=${category}` : '';
    const response = await api.get<ContactContextListResponse>(`/memory/contacts${params}`);
    return response.data;
}

/**
 * Fetch a single contact by email
 */
export async function fetchContact(contactEmail: string): Promise<ContactContext> {
    const response = await api.get<ContactContext>(`/memory/contacts/${encodeURIComponent(contactEmail)}`);
    return response.data;
}

/**
 * Update contact context
 */
export async function updateContact(
    contactEmail: string,
    request: UpdateContactRequest
): Promise<ContactContext> {
    const response = await api.put<ContactContext>(
        `/memory/contacts/${encodeURIComponent(contactEmail)}`,
        request
    );
    return response.data;
}

/**
 * Delete a contact context
 */
export async function deleteContact(contactEmail: string): Promise<void> {
    await api.delete(`/memory/contacts/${encodeURIComponent(contactEmail)}`);
}
