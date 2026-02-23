import { z } from "zod";
import { api } from "./api";

export const SchedulingIntentSchema = z.object({
    id: z.number(),
    user_id: z.string(),
    message_id: z.number().nullable().optional(),
    thread_id: z.string().nullable().optional(),
    sender_name: z.string().nullable().optional(),
    sender_email: z.string().nullable().optional(),
    intent_type: z.string(),
    intent_summary: z.string().nullable().optional(),
    meeting_title: z.string().nullable().optional(),
    meeting_date: z.string().nullable().optional(),
    matched_event_id: z.number().nullable().optional(),
    status: z.string(),
    created_at: z.string(),
    updated_at: z.string(),
});

export const SchedulingIntentsResponseSchema = z.object({
    intents: z.array(SchedulingIntentSchema),
    total: z.number(),
});

export const OrchestratorResultSchema = z.object({
    suggested_slots: z.array(z.object({
        start_time: z.string(),
        end_time: z.string(),
        has_conflict: z.boolean().optional(),
        conflict_details: z.string().nullable().optional(),
    })),
    draft_reply: z.string(),
    reasoning: z.string().nullable().optional(),
});

export type SchedulingIntent = z.infer<typeof SchedulingIntentSchema>;
export type SchedulingIntentsResponse = z.infer<typeof SchedulingIntentsResponseSchema>;
export type OrchestratorResult = z.infer<typeof OrchestratorResultSchema>;

export async function fetchSchedulingIntents(params?: {
    status?: string;
    thread_id?: string;
    limit?: number;
    offset?: number;
}): Promise<SchedulingIntentsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.thread_id) searchParams.append("thread_id", params.thread_id);
    if (params?.limit) searchParams.append("limit", params.limit.toString());
    if (params?.offset) searchParams.append("offset", params.offset.toString());
    const query = searchParams.toString();
    const response = await api.get(`/scheduling/intents${query ? `?${query}` : ""}`);
    return SchedulingIntentsResponseSchema.parse(response.data);
}

export async function runOrchestrator(intentId: number, userNote?: string): Promise<OrchestratorResult> {
    const response = await api.post(`/scheduling/intents/${intentId}/run`, { user_note: userNote || null });
    return OrchestratorResultSchema.parse(response.data);
}

export async function sendIntentReply(intentId: number, editedReply: string): Promise<void> {
    await api.post(`/scheduling/intents/${intentId}/send`, { edited_reply: editedReply });
}

export async function dismissIntent(intentId: number): Promise<void> {
    await api.post(`/scheduling/intents/${intentId}/dismiss`);
}

export async function acknowledgeIntent(intentId: number): Promise<void> {
    await api.post(`/scheduling/intents/${intentId}/acknowledge`);
}

export async function addIntentToCalendar(intentId: number): Promise<{ event_id: number }> {
    const response = await api.post(`/scheduling/intents/${intentId}/add-to-calendar`);
    return response.data;
}
