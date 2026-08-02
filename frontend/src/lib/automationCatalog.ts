import type { UserSettings } from "@/services/settings";

export type AutomationId = "inbox-copilot" | "meeting-prep";
export type AutomationStatus =
    | "needs_connection"
    | "ready"
    | "running"
    | "drafts_only"
    | "off";
export type ConnectorId = "gmail" | "calendar";

export interface AutomationConnector {
    id: ConnectorId;
    label: string;
    required: boolean;
    description: string;
}

export interface AutomationDefinition {
    id: AutomationId;
    name: string;
    outcome: string;
    safetyMode: "draft_only" | "read_only";
    requiredConnectors: AutomationConnector[];
    optionalConnectors: AutomationConnector[];
}

export const AUTOMATION_DEFINITIONS: Record<AutomationId, AutomationDefinition> = {
    "inbox-copilot": {
        id: "inbox-copilot",
        name: "Inbox Copilot",
        outcome: "Triage threads, extract tasks, and draft replies using your stored context.",
        safetyMode: "draft_only",
        requiredConnectors: [
            {
                id: "gmail",
                label: "Gmail",
                required: true,
                description: "Needed to read threads and prepare reply drafts.",
            },
        ],
        optionalConnectors: [],
    },
    "meeting-prep": {
        id: "meeting-prep",
        name: "Meeting Prep",
        outcome: "Generate meeting briefs, pull attendee context, and surface risks and commitments.",
        safetyMode: "read_only",
        requiredConnectors: [
            {
                id: "calendar",
                label: "Calendar",
                required: true,
                description: "Needed to read upcoming events and attendees.",
            },
        ],
        optionalConnectors: [
            {
                id: "gmail",
                label: "Gmail",
                required: false,
                description: "Optional. Adds recent attendee email threads to each brief.",
            },
        ],
    },
};

const AUTOMATION_STORAGE_KEYS: Record<AutomationId, string> = {
    "inbox-copilot": "teeks_automation_inbox_copilot_enabled",
    "meeting-prep": "teeks_automation_meeting_prep_enabled",
};

export function statusLabel(status: AutomationStatus): string {
    switch (status) {
        case "needs_connection":
            return "Needs connection";
        case "ready":
            return "Ready";
        case "running":
            return "Running";
        case "drafts_only":
            return "Drafts only";
        case "off":
            return "Off";
    }
}

export function getConnectorAvailability(settings: UserSettings | null): Record<ConnectorId, boolean> {
    return {
        gmail: settings?.gmail_connected ?? false,
        calendar: settings?.calendar_connected ?? false,
    };
}

export function readAutomationPreference(id: AutomationId): boolean | null {
    if (typeof window === "undefined") {
        return null;
    }

    const rawValue = window.localStorage.getItem(AUTOMATION_STORAGE_KEYS[id]);
    if (rawValue === "true") {
        return true;
    }
    if (rawValue === "false") {
        return false;
    }
    return null;
}

export function writeAutomationPreference(id: AutomationId, enabled: boolean): void {
    if (typeof window === "undefined") {
        return;
    }

    window.localStorage.setItem(AUTOMATION_STORAGE_KEYS[id], String(enabled));
}

export function getAutomationStatus(
    id: AutomationId,
    settings: UserSettings | null,
    preference: boolean | null,
): AutomationStatus {
    const definition = AUTOMATION_DEFINITIONS[id];
    const connectorAvailability = getConnectorAvailability(settings);
    const requiredConnected = definition.requiredConnectors.every(
        (connector) => connectorAvailability[connector.id],
    );

    if (!requiredConnected) {
        return "needs_connection";
    }

    if (preference === true) {
        return definition.safetyMode === "draft_only" ? "drafts_only" : "running";
    }

    if (preference === false) {
        return "off";
    }

    return "ready";
}

export function getMissingOptionalConnectors(
    id: AutomationId,
    settings: UserSettings | null,
): AutomationConnector[] {
    const definition = AUTOMATION_DEFINITIONS[id];
    const connectorAvailability = getConnectorAvailability(settings);
    return definition.optionalConnectors.filter(
        (connector) => !connectorAvailability[connector.id],
    );
}

export function getAutomationConnectHref(id: AutomationId): string {
    return `/auth/connect-google?automation=${id}`;
}

export function getAutomationReturnPath(id: AutomationId): string {
    return `/dashboard/automations/${id}`;
}

export function getAutomationSetupCopy(id: AutomationId): {
    title: string;
    description: string;
    buttonLabel: string;
} {
    switch (id) {
        case "inbox-copilot":
            return {
                title: "Turn on Inbox Copilot",
                description:
                    "Connect Google so Teeks can read inbox threads, extract tasks, and prepare reply drafts for your review.",
                buttonLabel: "Connect Google for Inbox Copilot",
            };
        case "meeting-prep":
            return {
                title: "Turn on Meeting Prep",
                description:
                    "Connect Google so Teeks can read your calendar and assemble briefs before meetings. Gmail adds attendee email context when available.",
                buttonLabel: "Connect Google for Meeting Prep",
            };
    }
}
