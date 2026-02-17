import { z } from "zod";
import { api } from "./api";

const TimeSlotSchema = z.object({
    start_time: z.string(),
    end_time: z.string(),
}).passthrough();

export const SchedulingSuggestionSchema = z.object({
    id: z.number(),
    thread_id: z.string(),
    message_id: z.number(),
    participants: z.array(z.string()),
    suggested_slots: z.array(TimeSlotSchema),
    time_window_start: z.string().nullable().optional(),
    time_window_end: z.string().nullable().optional(),
    timezone: z.string(),
    meeting_type: z.string(),
    duration_minutes: z.number(),
    intent_type: z.string(),
    source_text_snippet: z.string().nullable().optional(),
    draft_reply: z.string().nullable().optional(),
    draft_event_description: z.string().nullable().optional(),
    status: z.string(),
    created_at: z.string(),
    updated_at: z.string(),
});

export const SchedulingSuggestionsResponseSchema = z.object({
    suggestions: z.array(SchedulingSuggestionSchema),
    total: z.number(),
});

export type SchedulingSuggestion = z.infer<typeof SchedulingSuggestionSchema>;
export type SchedulingSuggestionsResponse = z.infer<typeof SchedulingSuggestionsResponseSchema>;

export async function fetchSchedulingSuggestions(params?: {
    status?: string;
    message_id?: number;
    limit?: number;
    offset?: number;
}): Promise<SchedulingSuggestionsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.message_id) searchParams.append("message_id", params.message_id.toString());
    if (params?.limit) searchParams.append("limit", params.limit.toString());
    if (params?.offset) searchParams.append("offset", params.offset.toString());
    const query = searchParams.toString();
    const response = await api.get(`/scheduling/suggestions${query ? `?${query}` : ""}`);
    return SchedulingSuggestionsResponseSchema.parse(response.data);
}

export async function sendSchedulingSuggestion(suggestionId: number, editedReply?: string): Promise<void> {
    await api.post(`/scheduling/suggestions/${suggestionId}/send`, editedReply ? { edited_reply: editedReply } : {});
}

export async function dismissSchedulingSuggestion(suggestionId: number): Promise<void> {
    await api.post(`/scheduling/suggestions/${suggestionId}/dismiss`);
}
