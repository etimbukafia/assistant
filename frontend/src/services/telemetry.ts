import { api } from "./api";

type TelemetryPayload = Record<string, unknown>;

type TelemetryEvent = {
    event_id?: string;
    event_name: string;
    event_payload: TelemetryPayload;
    page_path?: string;
    client_ts: string;
};

export interface TelemetryDashboard {
    days: number;
    total_events: number;
    event_counts: Record<string, number>;
    funnel: {
        chip_clicked: number;
        message_sent: number;
        action_approved: number;
        click_to_send_rate: number;
        send_to_approve_rate: number;
        click_to_approve_rate: number;
    };
    daily: Array<{
        date: string;
        chip_clicked: number;
        message_sent: number;
        action_approved: number;
    }>;
}

const EVENT_PAYLOAD_ALLOWLIST: Record<string, readonly string[]> = {
    mention_selected: ["mention_type", "source"],
    chat_message_sent: ["has_mentions", "mention_count", "source"],
    chat_chip_clicked: ["chip_id", "prompt_length", "source"],
    chat_approval_sent: ["pending_count", "source"],
    chat_action_approved: ["pending_count", "source"],
};

const queue: TelemetryEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let inFlight = false;

function scheduleFlush() {
    if (flushTimer || inFlight) return;
    flushTimer = setTimeout(() => {
        flushTimer = null;
        void flushTelemetry();
    }, 1500);
}

function generateEventId(): string {
    if (typeof window !== "undefined" && window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

async function flushTelemetry() {
    if (inFlight || queue.length === 0) return;
    inFlight = true;
    const batch = queue.splice(0, 50);
    try {
        await api.post("/telemetry/events", { events: batch });
    } catch {
        // Put events back at the front (bounded retry behavior)
        queue.unshift(...batch.slice(-50));
    } finally {
        inFlight = false;
        if (queue.length) {
            scheduleFlush();
        }
    }
}

export function trackUIEvent(eventName: string, payload: TelemetryPayload = {}): void {
    try {
        if (typeof window !== "undefined") {
            const safePayload = sanitizeTelemetryPayload(eventName, payload);
            queue.push({
                event_id: generateEventId(),
                event_name: eventName,
                event_payload: safePayload,
                page_path: window.location.pathname,
                client_ts: new Date().toISOString(),
            });
            scheduleFlush();

            window.dispatchEvent(
                new CustomEvent("teeks.telemetry", {
                    detail: { event: eventName, payload: safePayload, at: new Date().toISOString() },
                })
            );
        }
        if (process.env.NODE_ENV !== "production") {
            // eslint-disable-next-line no-console
            console.debug("[telemetry]", eventName, sanitizeTelemetryPayload(eventName, payload));
        }
    } catch {
        // telemetry must never break UX flows
    }
}

function sanitizeTelemetryPayload(eventName: string, payload: TelemetryPayload): TelemetryPayload {
    const allowedKeys = EVENT_PAYLOAD_ALLOWLIST[eventName] || [];
    const sanitized: TelemetryPayload = {};

    for (const key of allowedKeys) {
        const value = payload[key];
        if (typeof value === "boolean" || typeof value === "number") {
            sanitized[key] = value;
        } else if (typeof value === "string") {
            sanitized[key] = value.slice(0, 120);
        }
    }

    return sanitized;
}

export async function getTelemetryDashboard(days = 7, userId?: string, eventName?: string): Promise<TelemetryDashboard> {
    const response = await api.get<TelemetryDashboard>("/telemetry/dashboard", {
        params: { days, user_id: userId, event_name: eventName },
    });
    return response.data;
}
