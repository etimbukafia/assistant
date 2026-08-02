"use client";

import { useEffect, useState, type ElementType } from "react";
import Link from "next/link";
import { Inbox, CalendarDays, ChevronRight, PlugZap } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { AutomationStatusBadge } from "@/components/automations/AutomationStatusBadge";
import {
    AUTOMATION_DEFINITIONS,
    getAutomationStatus,
    getMissingOptionalConnectors,
    readAutomationPreference,
    type AutomationId,
    type AutomationStatus,
} from "@/lib/automationCatalog";

interface AutomationCardProps {
    href: string;
    icon: ElementType;
    name: string;
    outcome: string;
    requiredConnectors: string[];
    optionalConnectors?: string[];
    status: AutomationStatus | null;
    degradedNote?: string | null;
}

function AutomationCard({
    href,
    icon: Icon,
    name,
    outcome,
    requiredConnectors,
    optionalConnectors,
    status,
    degradedNote,
}: AutomationCardProps) {
    // null = preferences not yet loaded from localStorage — defer the label
    const ctaLabel = status == null || status === "needs_connection" ? "Set up" : "Configure";

    return (
        <div className="bg-card rounded-[14px] border border-border shadow-[0_1px_3px_rgba(0,0,0,0.07),0_1px_2px_rgba(0,0,0,0.05)] p-6 flex flex-col gap-4">
            {/* Header row */}
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <Icon size={18} strokeWidth={1.8} className="text-primary" />
                    </div>
                    <h2 className="font-playfair font-semibold text-[17px] text-foreground leading-tight">
                        {name}
                    </h2>
                </div>
                {status && <AutomationStatusBadge status={status} />}
            </div>

            {/* Outcome */}
            <p className="text-[14px] text-muted-foreground leading-[21px]">
                {outcome}
            </p>

            {/* Connector requirements */}
            <div className="flex flex-wrap gap-1.5">
                {requiredConnectors.map((c) => (
                    <span
                        key={c}
                        className="inline-flex items-center px-2 py-0.5 rounded-[4px] border border-border text-[11px] font-medium text-muted-foreground"
                    >
                        {c} required
                    </span>
                ))}
                {optionalConnectors?.map((c) => (
                    <span
                        key={c}
                        className="inline-flex items-center px-2 py-0.5 rounded-[4px] border border-border/60 text-[11px] font-medium text-muted-foreground/70"
                    >
                        {c} optional
                    </span>
                ))}
            </div>

            {degradedNote && (
                <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-2">
                    <p className="flex items-start gap-2 text-[12px] leading-[18px] text-muted-foreground">
                        <PlugZap size={14} strokeWidth={1.8} className="mt-0.5 flex-shrink-0 text-muted-foreground/70" />
                        {degradedNote}
                    </p>
                </div>
            )}

            {/* CTA */}
            <div className="mt-auto pt-2">
                <Link
                    href={href}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-[13px] font-semibold hover:bg-primary/90 transition-colors"
                >
                    {ctaLabel}
                    <ChevronRight size={14} strokeWidth={2} />
                </Link>
            </div>
        </div>
    );
}

export default function AutomationsPage() {
    const { settings } = useAuth();
    const [preferences, setPreferences] = useState<Record<AutomationId, boolean | null>>({
        "inbox-copilot": null,
        "meeting-prep": null,
    });
    const [preferencesLoaded, setPreferencesLoaded] = useState(false);

    useEffect(() => {
        setPreferences({
            "inbox-copilot": readAutomationPreference("inbox-copilot"),
            "meeting-prep": readAutomationPreference("meeting-prep"),
        });
        setPreferencesLoaded(true);
    }, []);

    const inboxCopilotStatus = preferencesLoaded
        ? getAutomationStatus("inbox-copilot", settings, preferences["inbox-copilot"])
        : null;
    const meetingPrepStatus = preferencesLoaded
        ? getAutomationStatus("meeting-prep", settings, preferences["meeting-prep"])
        : null;
    const meetingPrepOptionalGaps = getMissingOptionalConnectors("meeting-prep", settings);
    const meetingPrepDegradedNote =
        meetingPrepOptionalGaps.length > 0
            ? "Meeting Prep still runs from calendar, contacts, tasks, and stored memory. Connect Gmail to add recent attendee thread context."
            : null;

    return (
        <div>
            {/* Page header */}
            <div className="mb-8">
                <h1 className="font-playfair font-semibold text-[22px] text-foreground tracking-tight mb-1">
                    Automations
                </h1>
                <p className="text-[13px] text-muted-foreground">
                    Turn Teeks memory into ongoing work across your inbox and calendar.
                </p>
            </div>

            {/* Catalog — two cards only, no workflow builder */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl">
                <AutomationCard
                    href="/dashboard/automations/inbox-copilot"
                    icon={Inbox}
                    name={AUTOMATION_DEFINITIONS["inbox-copilot"].name}
                    outcome={AUTOMATION_DEFINITIONS["inbox-copilot"].outcome}
                    requiredConnectors={AUTOMATION_DEFINITIONS["inbox-copilot"].requiredConnectors.map((connector) => connector.label)}
                    status={inboxCopilotStatus}
                />
                <AutomationCard
                    href="/dashboard/automations/meeting-prep"
                    icon={CalendarDays}
                    name={AUTOMATION_DEFINITIONS["meeting-prep"].name}
                    outcome={AUTOMATION_DEFINITIONS["meeting-prep"].outcome}
                    requiredConnectors={AUTOMATION_DEFINITIONS["meeting-prep"].requiredConnectors.map((connector) => connector.label)}
                    optionalConnectors={AUTOMATION_DEFINITIONS["meeting-prep"].optionalConnectors.map((connector) => connector.label)}
                    status={meetingPrepStatus}
                    degradedNote={meetingPrepDegradedNote}
                />
            </div>
        </div>
    );
}
