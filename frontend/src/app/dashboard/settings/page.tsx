"use client";

import { useState, useEffect } from "react";
import {
    Calendar,
    CheckCircle2,
    ChevronRight,
    Download,
    Loader2,
    Mail,
    Monitor,
    Shield,
    XCircle,
} from "lucide-react";
import { Switch } from "@/components/ui/Switch";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { useSettings } from "@/hooks/useSettings";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { supabase } from "@/utils/supabase/client";
import { exportUserData, revokeGmailAccess, deleteAllData } from "@/services/privacy";

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = "general" | "notifications" | "calendar" | "account" | "privacy";

const TABS: { id: Tab; label: string }[] = [
    { id: "general",       label: "General" },
    { id: "notifications", label: "Notifications" },
    { id: "calendar",      label: "Calendar" },
    { id: "account",       label: "Account" },
    { id: "privacy",       label: "Privacy" },
];

// ─── Layout primitives ────────────────────────────────────────────────────────

function Section({ children }: { children: React.ReactNode }) {
    return (
        <div
            className="rounded-[14px] border border-border bg-card overflow-hidden"
            style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)" }}
        >
            {children}
        </div>
    );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
    return (
        <p className="px-5 pt-5 pb-2 text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
            {children}
        </p>
    );
}

function Row({
    label,
    description,
    control,
    onClick,
    destructive = false,
}: {
    label: string;
    description?: string;
    control?: React.ReactNode;
    onClick?: () => void;
    destructive?: boolean;
}) {
    const Tag = onClick ? "button" : "div";
    return (
        <Tag
            {...(onClick ? { type: "button" as const, onClick } : {})}
            className={cn(
                "w-full text-left flex items-center justify-between gap-4 px-5 py-4",
                "border-b border-border last:border-0 transition-colors",
                onClick && (destructive
                    ? "hover:bg-destructive/5 cursor-pointer"
                    : "hover:bg-muted/30 cursor-pointer"),
            )}
        >
            <div className="min-w-0">
                <p className={cn(
                    "text-[13px] font-medium font-inter",
                    destructive ? "text-destructive" : "text-foreground"
                )}>
                    {label}
                </p>
                {description && (
                    <p className="text-[12px] text-muted-foreground font-inter mt-0.5 leading-relaxed">
                        {description}
                    </p>
                )}
            </div>
            {control ? (
                <div className="shrink-0">{control}</div>
            ) : onClick ? (
                <ChevronRight size={15} className="shrink-0 text-muted-foreground" />
            ) : null}
        </Tag>
    );
}

function Pad({ children }: { children: React.ReactNode }) {
    return <div className="px-5 pb-5">{children}</div>;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
    const { user, signOut } = useAuth();
    const { settings, isLoading, updateSetting, isUpdating } = useSettings();

    const [activeTab, setActiveTab]   = useState<Tab>("general");
    const [instructions, setInstructions] = useState("");
    const [notifEmail, setNotifEmail] = useState("");
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);

    useEffect(() => {
        if (!settings) return;
        setInstructions(settings.task_detection_instructions || "");
        setNotifEmail(settings.notification_email || "");
    }, [settings?.task_detection_instructions, settings?.notification_email]);

    // Helpers for nested preference objects
    const notifPref   = settings?.notification_preferences ?? {};
    const reminderPref = settings?.reminder_preferences ?? {};

    const setNotifPref = (key: string, val: boolean) =>
        updateSetting("notification_preferences", { ...notifPref, [key]: val });

    const setReminderPref = (key: string, val: boolean | string) =>
        updateSetting("reminder_preferences", { ...reminderPref, [key]: val });

    // Actions
    const handleSignOutAll = async () => {
        try {
            await supabase.auth.signOut({ scope: "global" });
            toast.success("Signed out from all devices");
            window.location.href = "/login";
        } catch {
            toast.error("Failed to sign out from all devices");
        }
    };

    const handleExport = async () => {
        try {
            const data = await exportUserData();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement("a");
            a.href     = url;
            a.download = `teeks_export_${new Date().toISOString().split("T")[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            toast.success("Export started");
        } catch {
            toast.error("Failed to export data");
        }
    };

    const handleDeleteAccount = async () => {
        try {
            await deleteAllData();
            await supabase.auth.signOut();
            window.location.href = "/login";
        } catch {
            toast.error("Failed to delete account. Please try again.");
            setIsDeleteOpen(false);
        }
    };

    const planLabel = settings?.subscription_tier === "pro" ? "Pro" : "Trial";
    const daysLeft  = settings?.days_remaining ?? 0;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 size={18} className="animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto">

            {/* Header */}
            <div className="mb-6">
                <h1 className="font-playfair text-[28px] font-semibold text-foreground tracking-tight">
                    Settings
                </h1>
                <p className="text-[13px] text-muted-foreground font-inter mt-1">
                    Manage your assistant and account.
                </p>
            </div>

            {/* Tab bar */}
            <div className="flex items-center border-b border-border mb-8 gap-1">
                {TABS.map((tab) => (
                    <button
                        key={tab.id}
                        type="button"
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            "px-4 pb-3 text-[13px] font-medium font-inter border-b-2 -mb-px transition-colors",
                            activeTab === tab.id
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* ── General ─────────────────────────────────────────────────── */}
            {activeTab === "general" && (
                <div className="space-y-5">

                    <Section>
                        <SectionLabel>AI & Automation</SectionLabel>
                        <Row
                            label="Auto-approve tasks"
                            description="Add AI-detected tasks to your list without manual review"
                            control={
                                <Switch
                                    checked={settings?.auto_approve_tasks ?? false}
                                    onCheckedChange={(v) => updateSetting("auto_approve_tasks", v)}
                                />
                            }
                        />
                        <Row
                            label="Quick reply from task"
                            description="Enable AI-drafted replies directly from task cards"
                            control={
                                <Switch
                                    checked={settings?.enable_quick_reply_from_task ?? false}
                                    onCheckedChange={(v) => updateSetting("enable_quick_reply_from_task", v)}
                                />
                            }
                        />
                    </Section>

                    <Section>
                        <SectionLabel>Task Detection</SectionLabel>
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-3">
                                Guide Teeks on how to identify tasks in your emails. Mention specific keywords, projects, or people to prioritise.
                            </p>
                            <Textarea
                                placeholder={`e.g. Flag anything from the executive team. Anything mentioning "board prep" or "Q3 roadmap" is high priority.`}
                                value={instructions}
                                onChange={(e) => setInstructions(e.target.value)}
                                onBlur={() => {
                                    if (instructions !== settings?.task_detection_instructions) {
                                        updateSetting("task_detection_instructions", instructions || null);
                                        toast.success("Instructions updated");
                                    }
                                }}
                                className="min-h-[110px] text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30 resize-none font-inter"
                            />
                            {isUpdating && (
                                <p className="mt-2 text-[11px] text-muted-foreground font-inter flex items-center gap-1.5">
                                    <Loader2 size={11} className="animate-spin" /> Saving…
                                </p>
                            )}
                        </Pad>
                    </Section>
                </div>
            )}

            {/* ── Notifications ────────────────────────────────────────────── */}
            {activeTab === "notifications" && (
                <div className="space-y-5">

                    <Section>
                        <SectionLabel>Notification Email</SectionLabel>
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-2">
                                Where digests and alerts are sent. Defaults to your login email.
                            </p>
                            <Input
                                type="email"
                                value={notifEmail}
                                onChange={(e) => setNotifEmail(e.target.value)}
                                onBlur={() => {
                                    const v = notifEmail.trim() || null;
                                    if (v !== (settings?.notification_email ?? null)) {
                                        updateSetting("notification_email", v);
                                        toast.success("Notification email updated");
                                    }
                                }}
                                placeholder={user?.email ?? "your@email.com"}
                                className="h-9 text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                            />
                        </Pad>
                    </Section>

                    <Section>
                        <SectionLabel>Push Notifications</SectionLabel>
                        <Row
                            label="Enable push notifications"
                            description="Receive notifications outside the app"
                            control={
                                <Switch
                                    checked={notifPref.push_enabled ?? false}
                                    onCheckedChange={(v) => setNotifPref("push_enabled", v)}
                                />
                            }
                        />
                        <Row
                            label="Urgent tasks"
                            description="Notify when a time-critical task is detected"
                            control={
                                <Switch
                                    checked={notifPref.push_urgent_tasks ?? false}
                                    onCheckedChange={(v) => setNotifPref("push_urgent_tasks", v)}
                                />
                            }
                        />
                        <Row
                            label="Deadlines"
                            description="Notify when a commitment or deadline is approaching"
                            control={
                                <Switch
                                    checked={notifPref.push_deadlines ?? false}
                                    onCheckedChange={(v) => setNotifPref("push_deadlines", v)}
                                />
                            }
                        />
                        <Row
                            label="Daily digest"
                            description="Morning summary of what needs your attention"
                            control={
                                <Switch
                                    checked={notifPref.push_digests ?? false}
                                    onCheckedChange={(v) => setNotifPref("push_digests", v)}
                                />
                            }
                        />
                        <Row
                            label="Meeting briefings"
                            description="Notify when a pre-meeting briefing is ready"
                            control={
                                <Switch
                                    checked={notifPref.push_briefings ?? false}
                                    onCheckedChange={(v) => setNotifPref("push_briefings", v)}
                                />
                            }
                        />
                    </Section>

                    <Section>
                        <SectionLabel>Reminders</SectionLabel>
                        <Row
                            label="Enable reminders"
                            description="Allow Teeks to send you task and follow-up reminders"
                            control={
                                <Switch
                                    checked={reminderPref.enabled ?? false}
                                    onCheckedChange={(v) => setReminderPref("enabled", v)}
                                />
                            }
                        />
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-2">
                                Default reminder time
                            </p>
                            <Input
                                type="time"
                                defaultValue={reminderPref.default_time || "09:00"}
                                onBlur={(e) => {
                                    if (e.target.value !== reminderPref.default_time) {
                                        setReminderPref("default_time", e.target.value);
                                        toast.success("Reminder time updated");
                                    }
                                }}
                                className="h-9 w-36 text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                            />
                        </Pad>
                    </Section>
                </div>
            )}

            {/* ── Calendar ─────────────────────────────────────────────────── */}
            {activeTab === "calendar" && (
                <div className="space-y-5">

                    <Section>
                        <SectionLabel>Connections</SectionLabel>
                        <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <Mail size={15} className="text-muted-foreground flex-shrink-0" />
                                <div>
                                    <p className="text-[13px] font-medium text-foreground font-inter">Gmail</p>
                                    <p className="text-[12px] text-muted-foreground font-inter">Email sync and task extraction</p>
                                </div>
                            </div>
                            {settings?.gmail_connected ? (
                                <span className="flex items-center gap-1.5 text-[12px] font-medium text-primary font-inter">
                                    <CheckCircle2 size={13} /> Connected
                                </span>
                            ) : (
                                <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground font-inter">
                                    <XCircle size={13} /> Not connected
                                </span>
                            )}
                        </div>
                        <div className="px-5 py-4 flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <Calendar size={15} className="text-muted-foreground flex-shrink-0" />
                                <div>
                                    <p className="text-[13px] font-medium text-foreground font-inter">Google Calendar</p>
                                    <p className="text-[12px] text-muted-foreground font-inter">Meeting briefings and scheduling</p>
                                </div>
                            </div>
                            {settings?.calendar_connected ? (
                                <span className="flex items-center gap-1.5 text-[12px] font-medium text-primary font-inter">
                                    <CheckCircle2 size={13} /> Connected
                                </span>
                            ) : (
                                <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground font-inter">
                                    <XCircle size={13} /> Not connected
                                </span>
                            )}
                        </div>
                    </Section>

                    <Section>
                        <SectionLabel>Meeting Briefings</SectionLabel>
                        <Row
                            label="Auto-generate briefings"
                            description="Prepare context, attendees, and notes before scheduled meetings"
                            control={
                                <Switch
                                    checked={settings?.auto_briefing_enabled ?? false}
                                    onCheckedChange={(v) => updateSetting("auto_briefing_enabled", v)}
                                />
                            }
                        />
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-2">
                                Generate briefing this long before the meeting
                            </p>
                            <select
                                value={settings?.briefing_hours_before ?? 2}
                                onChange={(e) => updateSetting("briefing_hours_before", Number(e.target.value))}
                                className="h-9 rounded-lg border border-border bg-background px-3 text-[13px] text-foreground font-inter focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-colors"
                            >
                                <option value={1}>1 hour before</option>
                                <option value={2}>2 hours before</option>
                                <option value={4}>4 hours before</option>
                                <option value={8}>8 hours before</option>
                                <option value={24}>24 hours before</option>
                            </select>
                        </Pad>
                    </Section>

                    <Section>
                        <SectionLabel>Default Calendar</SectionLabel>
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-2">
                                Calendar ID where new events are created. Leave blank to use your primary calendar.
                            </p>
                            <Input
                                defaultValue={settings?.default_calendar_id || ""}
                                onBlur={(e) => {
                                    const v = e.target.value.trim() || null;
                                    if (v !== (settings?.default_calendar_id ?? null)) {
                                        updateSetting("default_calendar_id", v);
                                        toast.success("Default calendar updated");
                                    }
                                }}
                                placeholder="primary"
                                className="h-9 text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                            />
                        </Pad>
                    </Section>
                </div>
            )}

            {/* ── Account ──────────────────────────────────────────────────── */}
            {activeTab === "account" && (
                <div className="space-y-5">

                    <Section>
                        <div className="px-5 py-5 flex items-center gap-4 border-b border-border">
                            <div className="w-11 h-11 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                                <span className="font-playfair font-semibold text-lg text-primary leading-none">
                                    {user?.email?.[0].toUpperCase() ?? "U"}
                                </span>
                            </div>
                            <div className="min-w-0">
                                <p className="text-[14px] font-medium text-foreground font-inter truncate">
                                    {user?.email}
                                </p>
                                <p className="text-[12px] text-muted-foreground font-inter mt-0.5">
                                    {planLabel}
                                    {settings?.subscription_tier !== "pro" && daysLeft > 0
                                        ? ` · ${daysLeft} day${daysLeft !== 1 ? "s" : ""} remaining`
                                        : ""}
                                </p>
                            </div>
                        </div>
                        <Row
                            label="Sign out"
                            description="Sign out of this device"
                            onClick={() => signOut()}
                        />
                    </Section>

                    <Section>
                        <SectionLabel>Sessions</SectionLabel>
                        <div className="px-5 py-4 border-b border-border flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                                <Monitor size={14} className="text-primary" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-[13px] font-medium text-foreground font-inter">This device</p>
                                <p className="text-[12px] text-muted-foreground font-inter">Active now</p>
                            </div>
                            <span className="text-[10px] font-bold uppercase tracking-[1px] text-primary bg-primary/10 px-2 py-0.5 rounded-full font-inter">
                                Current
                            </span>
                        </div>
                        <Row
                            label="Sign out all devices"
                            description="Revoke all active sessions across every device"
                            onClick={handleSignOutAll}
                            destructive
                        />
                    </Section>
                </div>
            )}

            {/* ── Privacy ──────────────────────────────────────────────────── */}
            {activeTab === "privacy" && (
                <div className="space-y-5">

                    <Section>
                        <SectionLabel>Your Data</SectionLabel>
                        <Row
                            label="Export my data"
                            description="Download a complete copy of your tasks, settings, and AI memory (JSON)"
                            onClick={handleExport}
                        />
                        <Row
                            label="Revoke Gmail access"
                            description="Disconnect Google account and delete all synced email data"
                            onClick={() =>
                                revokeGmailAccess()
                                    .then(() => toast.success("Gmail access revoked"))
                                    .catch(() => toast.error("Failed to revoke access"))
                            }
                            destructive
                        />
                    </Section>

                    <div className="rounded-[14px] border border-destructive/25 bg-destructive/[0.03] p-5">
                        <p className="text-[13px] font-semibold text-destructive font-inter mb-1">
                            Danger zone
                        </p>
                        <p className="text-[12px] text-destructive/70 font-inter mb-4 leading-relaxed">
                            Permanently deletes your account, all tasks, AI memory, and settings. This cannot be undone.
                        </p>
                        <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
                            <DialogTrigger asChild>
                                <button
                                    type="button"
                                    className="h-9 px-4 rounded-lg border border-destructive/40 text-destructive text-[13px] font-medium font-inter hover:bg-destructive hover:text-white transition-colors"
                                >
                                    Delete my account
                                </button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle className="font-playfair text-[18px] font-semibold">
                                        Delete account permanently?
                                    </DialogTitle>
                                    <DialogDescription className="text-[13px] text-muted-foreground font-inter pt-1 leading-relaxed">
                                        This removes your account, all tasks, emails, AI memory, and settings from our servers. It cannot be undone.
                                    </DialogDescription>
                                </DialogHeader>
                                <DialogFooter className="gap-2 pt-2">
                                    <button
                                        type="button"
                                        onClick={() => setIsDeleteOpen(false)}
                                        className="h-9 px-4 rounded-lg text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors font-inter"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="button"
                                        onClick={handleDeleteAccount}
                                        className="h-9 px-4 rounded-lg bg-destructive text-white text-[13px] font-medium font-inter hover:bg-destructive/90 transition-colors"
                                    >
                                        Delete everything
                                    </button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>
            )}
        </div>
    );
}
