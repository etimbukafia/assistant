/**
 * Calendar API Service
 * 
 * Functions for calendar operations against the backend.
 */

import { api } from './api';

// Types matching backend schemas
export interface CalendarEvent {
    id: number;
    title: string;
    description?: string;
    start_time: string;
    end_time: string;
    participants: string[];
    timezone: string;
    location?: string;
    source_message_id?: number;
    source_suggestion_id?: number;
    provider: string;
    external_event_id?: string;
    status: 'upcoming' | 'completed';
    error_message?: string;
    created_at: string;
    updated_at: string;
    briefing?: CalendarBriefing | null;
}

export interface CalendarBriefing {
    agenda?: string;
    prep_complete?: boolean;
    prep_warnings?: { message: string; severity: string; suggestion: string }[];
    attendees?: { name: string; email: string }[];
    related_emails?: { id: number; subject: string; sender: string }[];
    open_tasks?: { id: number; title: string; priority: string }[];
}

export interface CalendarSettings {
    default_meeting_duration: number;
    preferred_meeting_times: string;
    buffer_minutes: number;
    working_hours_start: string;
    working_hours_end: string;
    default_timezone: string;
    calendar_ids: string[];
}

export interface CalendarSettingsUpdate {
    default_meeting_duration?: number;
    preferred_meeting_times?: string;
    buffer_minutes?: number;
    working_hours_start?: string;
    working_hours_end?: string;
    default_timezone?: string;
    calendar_ids?: string[];
}

export interface CalendarEventsResponse {
    events: CalendarEvent[];
    total: number;
}

export interface SyncResponse {
    success: boolean;
    message: string;
    results: {
        created: number;
        updated: number;
        unchanged: number;
    };
}

export interface FollowUp {
    type: 'task' | 'email_draft' | 'reminder';
    title: string;
    description?: string;
    priority?: string;
    draft_content?: string;
}

export interface FollowUpsResponse {
    follow_ups: FollowUp[];
}

/**
 * Fetch calendar events
 */
export async function fetchCalendarEvents(status?: string): Promise<CalendarEventsResponse> {
    const params = status ? `?status=${status}` : '';
    const response = await api.get<CalendarEventsResponse>(`/calendar/events${params}`);
    return response.data;
}

/**
 * Sync calendar events from Google Calendar
 */
export async function syncCalendar(daysAhead: number = 7): Promise<SyncResponse> {
    const response = await api.post<SyncResponse>(`/calendar/sync?days_ahead=${daysAhead}`);
    return response.data;
}

/**
 * Fetch calendar settings
 */
export async function fetchCalendarSettings(): Promise<CalendarSettings> {
    const response = await api.get<CalendarSettings>('/calendar/settings');
    return response.data;
}

/**
 * Update calendar settings
 */
export async function updateCalendarSettings(settings: CalendarSettingsUpdate): Promise<CalendarSettings> {
    const response = await api.patch<CalendarSettings>('/calendar/settings', settings);
    return response.data;
}

/**
 * Generate follow-ups for a completed meeting
 */
export async function generateFollowUps(eventId: number): Promise<FollowUpsResponse> {
    const response = await api.post<FollowUpsResponse>(`/calendar/events/${eventId}/generate-followups`);
    return response.data;
}

// ============================================
// Additional Calendar APIs
// ============================================

export interface CalendarInfo {
    id: string;
    summary: string;
    primary: boolean;
    access_role: string;
}

export interface CalendarsResponse {
    calendars: CalendarInfo[];
}

export interface BusySlot {
    start: string;
    end: string;
    calendar_id: string;
}

export interface AvailabilityResponse {
    busy_slots: BusySlot[];
    timezone: string;
}

export interface CreateEventRequest {
    suggestion_id: number;
    selected_slot_index?: number;
    title?: string;
    description?: string;
    location?: string;
}

/**
 * Get list of user's Google calendars
 * Use in Settings → Calendar preferences for calendar selection
 * Cache aggressively - calendar list rarely changes
 */
export async function fetchUserCalendars(): Promise<CalendarsResponse> {
    const response = await api.get<CalendarsResponse>('/calendar/calendars');
    return response.data;
}

/**
 * Check calendar availability for a time range
 * 
 * IMPORTANT: Only call when:
 * - Scheduling intent exists
 * - User explicitly engages with scheduling
 * 
 * NEVER call on app load or in background
 */
export async function checkAvailability(
    startTime: string,
    endTime: string,
    calendarIds?: string[]
): Promise<AvailabilityResponse> {
    const params = new URLSearchParams({
        start_time: startTime,
        end_time: endTime,
    });
    if (calendarIds?.length) {
        params.append('calendar_ids', calendarIds.join(','));
    }
    const response = await api.get<AvailabilityResponse>(`/calendar/availability?${params}`);
    return response.data;
}

/**
 * Create a calendar event from a scheduling suggestion
 * 
 * IMPORTANT: Only call after explicit user approval
 * Never auto-create events or create as side effects
 */
export async function createCalendarEvent(request: CreateEventRequest): Promise<CalendarEvent> {
    const response = await api.post<CalendarEvent>('/calendar/events', request);
    return response.data;
}
