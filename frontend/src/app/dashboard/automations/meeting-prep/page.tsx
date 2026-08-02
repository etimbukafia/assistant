"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
    ChevronLeft,
    CalendarDays,
    CheckCircle2,
    XCircle,
    ShieldCheck,
    Brain,
    Clock,
    ToggleLeft,
    ToggleRight,
    PlugZap,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { AutomationStatusBadge } from "@/components/automations/AutomationStatusBadge";
import {
    AUTOMATION_DEFINITIONS,
    getAutomationConnectHref,
    getAutomationSetupCopy,
    getAutomationStatus,
    getMissingOptionalConnectors,
    readAutomationPreference,
    writeAutomationPreference,
} from "@/lib/automationCatalog";

export default function MeetingPrepPage() {
    const { settings } = useAuth();
    const [preference, setPreference] = useState<boolean | null>(null);
    const [preferenceLoaded, setPreferenceLoaded] = useState(false);

    useEffect(() => {
        setPreference(readAutomationPreference("meeting-prep"));
        setPreferenceLoaded(true);
    }, []);

    const definition = AUTOMATION_DEFINITIONS["meeting-prep"];
    const calendarConnected = settings?.calendar_connected ?? false;
    const gmailConnected = settings?.gmail_connected ?? false;
    const status = preferenceLoaded
        ? getAutomationStatus("meeting-prep", settings, preference)
        : null;
    const enabled = preference === true;
    const setupCopy = getAutomationSetupCopy("meeting-prep");
    const connectHref = getAutomationConnectHref("meeting-prep");
    const missingOptionalConnectors = getMissingOptionalConnectors("meeting-prep", settings);
    const gmailEnrichmentUnavailable = missingOptionalConnectors.some(
        (connector) => connector.id === "gmail",
    );

    const toggle = () => {
        if (!calendarConnected) {
            return;
        }

        const next = preference === true ? false : true;
        setPreference(next);
        writeAutomationPreference("meeting-prep", next);
    };

    return (
        <div className="max-w-2xl">
            <Link
                href="/dashboard/automations"
                className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
            >
                <ChevronLeft size={15} strokeWidth={2} />
                Automations
            </Link>

            <div className="mb-8 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                        <CalendarDays size={20} strokeWidth={1.8} className="text-primary" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="font-playfair text-[22px] font-semibold leading-tight tracking-tight text-foreground">
                                {definition.name}
                            </h1>
                            {status && <AutomationStatusBadge status={status} />}
                        </div>
                        <p className="mt-0.5 text-[12px] text-muted-foreground">
                            {definition.outcome}
                        </p>
                    </div>
                </div>

                <button
                    onClick={toggle}
                    disabled={!calendarConnected || !preferenceLoaded}
                    title={calendarConnected ? "Turn Meeting Prep on or off" : "Connect Google to run Meeting Prep"}
                    className={cn(
                        "flex items-center gap-2 rounded-lg border px-3 py-2 text-[13px] font-medium transition-colors",
                        enabled
                            ? "border-[#4D7C0F]/30 bg-[#4D7C0F]/8 text-[#4D7C0F]"
                            : "border-border bg-card text-muted-foreground",
                        (!calendarConnected || !preferenceLoaded) && "cursor-not-allowed opacity-40",
                    )}
                >
                    {enabled ? (
                        <ToggleRight size={16} strokeWidth={1.8} />
                    ) : (
                        <ToggleLeft size={16} strokeWidth={1.8} />
                    )}
                    {enabled ? "On" : "Off"}
                </button>
            </div>

            <div className="flex flex-col gap-5">
                <SetupSection
                    title={setupCopy.title}
                    description={
                        status === "ready"
                            ? "Meeting Prep is connected and ready. Turn it on when you want Teeks to start preparing briefs before upcoming events."
                            : status === "off"
                              ? "Meeting Prep is connected but currently off. Turn it back on whenever you want Teeks to resume briefing upcoming meetings."
                              : setupCopy.description
                    }
                    actionHref={status === "needs_connection" ? connectHref : undefined}
                    actionLabel={status === "needs_connection" ? setupCopy.buttonLabel : undefined}
                />

                <Section title="What Teeks will do">
                    <ul className="flex flex-col gap-2.5">
                        {[
                            "Generate a meeting brief before each event on your calendar.",
                            "Pull relationship context for every attendee from stored memory.",
                            "Surface open commitments, decisions, and risks relevant to the meeting.",
                            "Flag preparation items that need attention before the meeting starts.",
                        ].map((item) => (
                            <li key={item} className="flex items-start gap-2.5 text-[14px] leading-[21px] text-foreground">
                                <span className="mt-[3px] flex-shrink-0 text-primary">-&gt;</span>
                                {item}
                            </li>
                        ))}
                    </ul>
                </Section>

                <Section title="Required connections">
                    <div className="flex flex-col gap-4">
                        <ConnectorRow
                            name={definition.requiredConnectors[0].label}
                            required
                            connected={calendarConnected}
                            connectHref={connectHref}
                            description={definition.requiredConnectors[0].description}
                        />
                        <div className="border-t border-border" />
                        <ConnectorRow
                            name={definition.optionalConnectors[0].label}
                            required={false}
                            connected={gmailConnected}
                            connectHref={connectHref}
                            description={definition.optionalConnectors[0].description}
                        />
                    </div>
                </Section>

                {gmailEnrichmentUnavailable && (
                    <Section title="Runs without Gmail">
                        <div className="flex items-start gap-3">
                            <PlugZap size={17} strokeWidth={1.8} className="mt-[2px] flex-shrink-0 text-[#A07850]" />
                            <div>
                                <p className="text-[14px] font-medium text-foreground">
                                    Meeting Prep still works in a reduced mode
                                </p>
                                <p className="mt-0.5 text-[13px] leading-[20px] text-muted-foreground">
                                    Teeks will still build briefs from calendar events, attendees, tasks, and stored memory. It will skip recent attendee email threads until Gmail is connected.
                                </p>
                            </div>
                        </div>
                    </Section>
                )}

                <Section title="Safety mode">
                    <div className="flex items-start gap-3">
                        <ShieldCheck size={17} strokeWidth={1.8} className="mt-[2px] flex-shrink-0 text-[#4D7C0F]" />
                        <div>
                            <p className="text-[14px] font-medium text-foreground">Read only</p>
                            <p className="mt-0.5 text-[13px] text-muted-foreground">
                                Teeks reads your calendar and generates briefs automatically. No actions are taken on your behalf.
                            </p>
                        </div>
                    </div>
                </Section>

                <Section title="Memory used">
                    <ul className="flex flex-col gap-2 text-[13px] text-muted-foreground">
                        {[
                            "Relationship context per attendee: prior interactions, decisions, and open items.",
                            "Commitments and risks linked to the meeting topic.",
                            "Stored preferences for briefing format and detail level.",
                            "Recent attendee email threads when Gmail is connected.",
                        ].map((item) => (
                            <li key={item} className="flex items-start gap-2">
                                <Brain size={13} strokeWidth={1.8} className="mt-[3px] flex-shrink-0 text-muted-foreground/60" />
                                {item}
                            </li>
                        ))}
                    </ul>
                </Section>

                <Section title="Recent runs">
                    <div className="flex flex-col items-start gap-1 py-4">
                        <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
                            <Clock size={14} strokeWidth={1.8} />
                            {status === "running"
                                ? "No runs yet. Teeks will prep briefs before your next meeting."
                                : status === "needs_connection"
                                  ? "Connect Google to start seeing Meeting Prep runs here."
                                  : "Turn Meeting Prep on to start seeing runs here."}
                        </div>
                    </div>
                </Section>
            </div>
        </div>
    );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="rounded-[14px] border border-border bg-card p-5 shadow-[0_1px_3px_rgba(0,0,0,0.07),0_1px_2px_rgba(0,0,0,0.05)]">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60">
                {title}
            </p>
            {children}
        </div>
    );
}

function SetupSection({
    title,
    description,
    actionHref,
    actionLabel,
}: {
    title: string;
    description: string;
    actionHref?: string;
    actionLabel?: string;
}) {
    return (
        <Section title="Setup">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="flex items-start gap-3">
                    <PlugZap size={17} strokeWidth={1.8} className="mt-[2px] flex-shrink-0 text-primary" />
                    <div>
                        <p className="text-[14px] font-medium text-foreground">{title}</p>
                        <p className="mt-0.5 text-[13px] leading-[20px] text-muted-foreground">
                            {description}
                        </p>
                    </div>
                </div>
                {actionHref && actionLabel && (
                    <Link
                        href={actionHref}
                        className="flex-shrink-0 rounded-lg bg-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-primary/90"
                    >
                        {actionLabel}
                    </Link>
                )}
            </div>
        </Section>
    );
}

function ConnectorRow({
    name,
    required,
    connected,
    connectHref,
    description,
}: {
    name: string;
    required: boolean;
    connected: boolean;
    connectHref: string;
    description: string;
}) {
    return (
        <div className="flex items-center justify-between gap-4">
            <div className="flex items-start gap-2.5">
                {connected ? (
                    <CheckCircle2 size={16} strokeWidth={1.8} className="mt-[2px] flex-shrink-0 text-[#4D7C0F]" />
                ) : (
                    <XCircle
                        size={16}
                        strokeWidth={1.8}
                        className={cn(
                            "mt-[2px] flex-shrink-0",
                            required ? "text-amber-500" : "text-muted-foreground/50",
                        )}
                    />
                )}
                <div>
                    <div className="flex items-center gap-2">
                        <p className="text-[14px] font-medium text-foreground">{name}</p>
                        {!required && (
                            <span className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground/50">
                                Optional
                            </span>
                        )}
                    </div>
                    <p className="text-[12px] text-muted-foreground">{description}</p>
                </div>
            </div>
            {!connected && (
                <Link
                    href={connectHref}
                    className="flex-shrink-0 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-semibold text-white transition-colors hover:bg-primary/90"
                >
                    {required ? "Connect" : "Add"}
                </Link>
            )}
        </div>
    );
}
