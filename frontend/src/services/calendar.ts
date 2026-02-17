import { z } from "zod";
import { api } from "./api";

const AttendeeSchema = z.object({
    email: z.string().optional(),
    name: z.string().optional(),
    response_status: z.string().optional(),
}).passthrough();

export const CalendarEventSchema = z.object({
    id: z.number(),
    title: z.string(),
    description: z.string().nullable().optional(),
    notes: z.string().nullable().optional(),
    all_day: z.boolean().optional(),
    start_time: z.string(),
    end_time: z.string(),
    participants: z.array(z.union([z.string(), AttendeeSchema])),
    timezone: z.string(),
    location: z.string().nullable().optional(),
    source_message_id: z.number().nullable().optional(),
    source_suggestion_id: z.number().nullable().optional(),
    provider: z.string(),
    external_event_id: z.string().nullable().optional(),
    calendar_id: z.string().nullable().optional(),
    status: z.string(),
    error_message: z.string().nullable().optional(),
    briefing: z.object({
        attendees: z.array(z.object({
            email: z.string().nullable().optional(),
            name: z.string().nullable().optional(),
            response: z.string().optional(),
        })).optional(),
        agenda: z.string().optional(),
        location: z.string().nullable().optional(),
        related_emails: z.array(z.object({
            subject: z.string().optional(),
            sender: z.string().optional(),
            summary: z.string().optional(),
            date: z.string().optional(),
        })).optional(),
        open_tasks: z.array(z.object({
            title: z.string().optional(),
            priority: z.string().optional(),
            status: z.string().optional(),
        })).optional(),
        prep_warnings: z.array(z.string()).optional(),
        message_count: z.number().optional(),
        task_count: z.number().optional(),
        prep_complete: z.boolean().optional(),
    }).nullable().optional(),
    briefing_generated_at: z.string().nullable().optional(),
    briefing_scheduled_for: z.string().nullable().optional(),
    created_at: z.string(),
    updated_at: z.string(),
});

export const CalendarEventsResponseSchema = z.object({
    events: z.array(CalendarEventSchema),
    total: z.number(),
});

export const CalendarSettingsSchema = z.object({
    default_meeting_duration: z.number(),
    preferred_meeting_times: z.string(),
    buffer_minutes: z.number(),
    working_hours_start: z.string(),
    working_hours_end: z.string(),
    default_timezone: z.string(),
    calendar_ids: z.array(z.string()),
    default_calendar_id: z.string().nullable().optional(),
    auto_briefing_enabled: z.boolean().nullable().optional(),
    briefing_hours_before: z.number().nullable().optional(),
});

export const CalendarInfoSchema = z.object({
    id: z.string(),
    summary: z.string(),
    primary: z.boolean().optional(),
    access_role: z.string().optional(),
});

export const CalendarInfoResponseSchema = z.object({
    calendars: z.array(CalendarInfoSchema),
});

export type CalendarEvent = z.infer<typeof CalendarEventSchema>;
export type CalendarEventsResponse = z.infer<typeof CalendarEventsResponseSchema>;
export type CalendarSettings = z.infer<typeof CalendarSettingsSchema>;
export type CalendarInfoResponse = z.infer<typeof CalendarInfoResponseSchema>;

export async function fetchCalendarEvents(params?: {
    status?: string;
    limit?: number;
    offset?: number;
    start_time?: string;
    end_time?: string;
}): Promise<CalendarEventsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.limit) searchParams.append("limit", params.limit.toString());
    if (params?.offset) searchParams.append("offset", params.offset.toString());
    if (params?.start_time) searchParams.append("start_time", params.start_time);
    if (params?.end_time) searchParams.append("end_time", params.end_time);
    const query = searchParams.toString();
    const response = await api.get(`/calendar/events${query ? `?${query}` : ""}`);
    return CalendarEventsResponseSchema.parse(response.data);
}

export async function createManualEvent(payload: {
    title: string;
    start_time: string;
    end_time: string;
    description?: string | null;
    notes?: string | null;
    participants?: string[];
    all_day?: boolean;
    timezone?: string;
    location?: string | null;
    calendar_id?: string | null;
}): Promise<CalendarEvent> {
    const response = await api.post("/calendar/events/manual", payload);
    return CalendarEventSchema.parse(response.data);
}

export async function updateEvent(eventId: number, payload: {
    title?: string;
    start_time?: string;
    end_time?: string;
    description?: string | null;
    notes?: string | null;
    participants?: string[];
    all_day?: boolean;
    timezone?: string;
    location?: string | null;
    calendar_id?: string | null;
}): Promise<CalendarEvent> {
    const response = await api.patch(`/calendar/events/${eventId}`, payload);
    return CalendarEventSchema.parse(response.data);
}

export async function deleteEvent(eventId: number): Promise<void> {
    await api.delete(`/calendar/events/${eventId}`);
}

export async function createEventFromSuggestion(payload: {
    suggestion_id: number;
    selected_slot_index?: number;
    title?: string;
    description?: string;
    location?: string;
}): Promise<CalendarEvent> {
    const response = await api.post("/calendar/events", payload);
    return CalendarEventSchema.parse(response.data);
}

export async function syncCalendar(daysAhead: number = 7): Promise<void> {
    await api.post(`/calendar/sync?days_ahead=${daysAhead}`);
}

export async function fetchCalendarSettings(): Promise<CalendarSettings> {
    const response = await api.get("/calendar/settings");
    return CalendarSettingsSchema.parse(response.data);
}

export async function updateCalendarSettings(payload: {
    default_meeting_duration?: number;
    preferred_meeting_times?: string;
    buffer_minutes?: number;
    working_hours_start?: string;
    working_hours_end?: string;
    default_timezone?: string;
    calendar_ids?: string[];
    default_calendar_id?: string | null;
    auto_briefing_enabled?: boolean;
    briefing_hours_before?: number;
}): Promise<CalendarSettings> {
    const response = await api.patch("/calendar/settings", payload);
    return CalendarSettingsSchema.parse(response.data);
}

export async function fetchCalendars(): Promise<CalendarInfoResponse> {
    const response = await api.get("/calendar/calendars");
    return CalendarInfoResponseSchema.parse(response.data);
}

export async function generateBriefing(eventId: number): Promise<{ briefing_generated_at?: string | null }> {
    const response = await api.post(`/calendar/events/${eventId}/generate-briefing`);
    return z.object({
        success: z.boolean(),
        briefing_generated_at: z.string().nullable().optional(),
    }).parse(response.data);
}
