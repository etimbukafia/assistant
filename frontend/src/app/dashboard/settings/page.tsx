"use client";

import { useState, useEffect } from "react";
import {
    Calendar,
    CheckCircle2,
    ChevronRight,
    Loader2,
    Mail,
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
import { disconnectProvider } from "@/services/microsoft";
import {
    changePlan,
    createCreditTopupCheckout,
    getCreditStatus,
    getBillingPortalUrl,
    previewPlanChange,
    type PlanChangePreviewResponse,
} from "@/services/billing";
import type { NotificationPreferences, ReminderPreferences } from "@/services/settings";

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = "personal" | "executive" | "general" | "integrations" | "account" | "privacy";

const TABS: { id: Tab; label: string }[] = [
    { id: "personal",     label: "Personal" },
    { id: "executive",    label: "Executive" },
    { id: "general",      label: "General" },
    { id: "integrations", label: "Integrations" },
    { id: "account",      label: "Account" },
    { id: "privacy",      label: "Privacy" },
];

// Alphabetical, "Other" always last
const ROLE_OPTIONS = [
    "Administrative Executive Assistant",
    "Chief of Staff",
    "Executive Business Partner",
    "Executive Operations Manager",
    "Founder Associate / CEO Associate",
    "Personal Executive Assistant (Private / UHNW)",
    "Senior Executive Assistant",
    "Strategic Executive Assistant",
    "Strategic Operations Partner",
    "Virtual Executive Assistant",
    "Other",
];

const EXECUTIVE_ROLE_OPTIONS = [
    "C-Suite Executive",
    "Chief of Staff",
    "Family Office / UHNW Executive",
    "Founder / CEO",
    "Functional Executive",
    "Operator Executive",
    "Portfolio Executive",
    "Power Executive",
    "Startup Executive",
    "Visionary CEO",
    "Other",
];

const PREF_PLACEHOLDERS = [
    "I like concise responses, no elaboration unless I ask",
    "Present summaries as action points",
    "Draft emails formally",
];

const EXEC_PREF_PLACEHOLDERS = [
    "Prefers bullet points, no lengthy explanations",
    "Never schedules back-to-back meetings",
    "Respond to all board communications within the hour",
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
    const { user, signOut, signInWithGoogle, signInWithMicrosoft, refreshProfile } = useAuth();
    const { settings, isLoading, updateSetting, isUpdating } = useSettings();

    const [activeTab, setActiveTab]   = useState<Tab>("personal");
    const [instructions, setInstructions] = useState("");
    const [notifEmail, setNotifEmail] = useState("");
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);

    // Personal tab
    const [fullName, setFullName]           = useState("");
    const [preferredName, setPreferredName] = useState("");
    const [role, setRole]                   = useState("");
    const [roleOtherText, setRoleOtherText] = useState("");
    const [personalPrefs, setPersonalPrefs] = useState("");
    const [prefPlaceholderIdx, setPrefPlaceholderIdx] = useState(0);
    const [prefFocused, setPrefFocused]     = useState(false);

    // Executive tab
    const [execFullName, setExecFullName]           = useState("");
    const [execPreferredName, setExecPreferredName] = useState("");
    const [execRole, setExecRole]                   = useState("");
    const [execRoleOtherText, setExecRoleOtherText] = useState("");
    const [execPrefs, setExecPrefs]                 = useState("");
    const [execPrefPlaceholderIdx, setExecPrefPlaceholderIdx] = useState(0);
    const [execPrefFocused, setExecPrefFocused]     = useState(false);

    // Integrations tab
    const [connectOpen, setConnectOpen] = useState(false);
    const [connectPending, setConnectPending] = useState<"google" | "microsoft" | null>(null);
    const [connectBusy, setConnectBusy] = useState(false);
    const [disconnectConfirmOpen, setDisconnectConfirmOpen] = useState(false);
    const [disconnectBusy, setDisconnectBusy] = useState(false);

    // Account tab
    const [selectedBillingCycle, setSelectedBillingCycle] = useState<"monthly" | "annual">("annual");
    const [planPreview, setPlanPreview] = useState<PlanChangePreviewResponse | null>(null);
    const [planPreviewLoading, setPlanPreviewLoading] = useState(false);
    const [planPreviewError, setPlanPreviewError] = useState<string | null>(null);
    const [planChangeBusy, setPlanChangeBusy] = useState(false);
    const [portalBusy, setPortalBusy] = useState(false);
    const [creditStatus, setCreditStatus] = useState<{
        credits_used: number;
        credits_limit: number;
        credits_remaining: number;
    } | null>(null);
    const [creditStatusLoading, setCreditStatusLoading] = useState(false);
    const [creditStatusError, setCreditStatusError] = useState<string | null>(null);
    const [topupAmountUsd, setTopupAmountUsd] = useState<number>(5);
    const [topupBusy, setTopupBusy] = useState(false);

    useEffect(() => {
        if (!settings) return;
        setInstructions(settings.task_detection_instructions || "");
        setNotifEmail(settings.notification_email || "");
    }, [settings?.task_detection_instructions, settings?.notification_email]);

    // Initialise personal fields from saved settings or OAuth metadata
    useEffect(() => {
        if (!settings) return;
        const oauthName = (user as any)?.user_metadata?.full_name
            || (user as any)?.user_metadata?.name
            || "";
        const savedFull = settings.full_name || oauthName;
        setFullName(savedFull);
        setPreferredName(settings.preferred_name || savedFull.split(" ")[0] || "");
        const saved = settings.role || "";
        // "Executive Assistant" is the backend default — treat it as unset in the UI
        const effectiveRole = saved === "Executive Assistant" ? "" : saved;
        const allPresets = [
            ...ROLE_OPTIONS.slice(0, -1),
            ...EXECUTIVE_ROLE_OPTIONS.slice(0, -1),
        ];
        if (allPresets.includes(effectiveRole) || effectiveRole === "") {
            setRole(effectiveRole);
            setRoleOtherText("");
        } else {
            setRole("Other");
            setRoleOtherText(effectiveRole);
        }
        setPersonalPrefs(settings.personal_preferences || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [settings?.full_name, settings?.preferred_name, settings?.role, settings?.personal_preferences]);

    // Rotate placeholder examples while the textarea is empty and unfocused
    useEffect(() => {
        if (prefFocused || personalPrefs) return;
        const id = setInterval(() => {
            setPrefPlaceholderIdx((i) => (i + 1) % PREF_PLACEHOLDERS.length);
        }, 3500);
        return () => clearInterval(id);
    }, [prefFocused, personalPrefs]);

    // Initialise executive fields from saved settings (never prefill from OAuth)
    useEffect(() => {
        if (!settings) return;
        const saved = settings.exec_role || "";
        const allPresets = [
            ...EXECUTIVE_ROLE_OPTIONS.slice(0, -1),
        ];
        setExecFullName(settings.exec_full_name || "");
        setExecPreferredName(settings.exec_preferred_name || "");
        setExecPrefs(settings.exec_preferences || "");
        if (allPresets.includes(saved) || saved === "") {
            setExecRole(saved);
            setExecRoleOtherText("");
        } else {
            setExecRole("Other");
            setExecRoleOtherText(saved);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [settings?.exec_full_name, settings?.exec_preferred_name, settings?.exec_role, settings?.exec_preferences]);

    // Rotate exec placeholder examples
    useEffect(() => {
        if (execPrefFocused || execPrefs) return;
        const id = setInterval(() => {
            setExecPrefPlaceholderIdx((i) => (i + 1) % EXEC_PREF_PLACEHOLDERS.length);
        }, 3500);
        return () => clearInterval(id);
    }, [execPrefFocused, execPrefs]);

    const currentProvider = settings?.connected_provider || "none";

    const extractError = (err: any, fallback: string): string => {
        const detail = err?.response?.data?.detail;
        if (!detail) return fallback;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail)) return detail.map((e: any) => e?.msg ?? String(e)).join(", ");
        return fallback;
    };

    const formatEffectiveAt = (value?: string | null) => {
        if (!value) return null;
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    };

    const saveRole = (selected: string, otherText: string) => {
        const value = selected === "Other" ? (otherText.trim() || null) : (selected || null);
        updateSetting("role", value);
    };

    const saveExecRole = (selected: string, otherText: string) => {
        const value = selected === "Other" ? (otherText.trim() || null) : (selected || null);
        updateSetting("exec_role", value);
    };

    const startProviderConnect = async (provider: "google" | "microsoft") => {
        if (connectBusy) return;
        if (currentProvider === provider) {
            setConnectOpen(false);
            setConnectPending(null);
            return;
        }
        setConnectBusy(true);
        try {
            setConnectOpen(false);
            if (currentProvider !== "none") {
                await disconnectProvider(currentProvider === "google" ? "google" : "microsoft");
                await refreshProfile();
            }
            if (provider === "google") {
                await signInWithGoogle();
            } else {
                await signInWithMicrosoft();
            }
        } catch (err: any) {
            toast.error(extractError(err, "Could not switch provider. Please try again."));
        } finally {
            setConnectBusy(false);
        }
    };

    const handleConnectChoice = (provider: "google" | "microsoft") => {
        if (currentProvider !== "none" && currentProvider !== provider) {
            setConnectPending(provider);
            return;
        }
        void startProviderConnect(provider);
    };

    const handleDisconnect = async () => {
        if (disconnectBusy || currentProvider === "none") return;
        setDisconnectBusy(true);
        try {
            await disconnectProvider(currentProvider === "google" ? "google" : "microsoft");
            await refreshProfile();
            toast.success(`${currentProvider === "google" ? "Google" : "Microsoft"} disconnected`);
            setDisconnectConfirmOpen(false);
        } catch (err: any) {
            toast.error(extractError(err, "Could not disconnect. Please try again."));
        } finally {
            setDisconnectBusy(false);
        }
    };

    const loadPlanPreview = async (targetCycle: "monthly" | "annual") => {
        if (settings?.subscription_tier !== "pro") return;
        setPlanPreviewLoading(true);
        setPlanPreviewError(null);
        try {
            const preview = await previewPlanChange({ target_cycle: targetCycle });
            setPlanPreview(preview);
        } catch (err: any) {
            setPlanPreview(null);
            setPlanPreviewError(extractError(err, "Couldn't load plan change details right now."));
        } finally {
            setPlanPreviewLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab !== "account") return;
        if (settings?.subscription_tier !== "pro") {
            setPlanPreview(null);
            setPlanPreviewError(null);
            setPlanPreviewLoading(false);
            return;
        }
        void loadPlanPreview(selectedBillingCycle);
    }, [activeTab, selectedBillingCycle, settings?.subscription_tier]);

    const loadCreditStatus = async () => {
        if (settings?.subscription_tier !== "pro") return;
        setCreditStatusLoading(true);
        setCreditStatusError(null);
        try {
            const status = await getCreditStatus();
            setCreditStatus({
                credits_used: status.credits_used,
                credits_limit: status.credits_limit,
                credits_remaining: status.credits_remaining,
            });
        } catch (err: any) {
            setCreditStatus(null);
            setCreditStatusError(err?.response?.data?.detail || "Couldn't load credit status right now.");
        } finally {
            setCreditStatusLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab !== "account") return;
        if (settings?.subscription_tier !== "pro") {
            setCreditStatus(null);
            setCreditStatusError(null);
            setCreditStatusLoading(false);
            return;
        }
        void loadCreditStatus();
    }, [activeTab, settings?.subscription_tier]);

    const handleApplyPlanChange = async () => {
        if (!planPreview || planChangeBusy) return;
        if (planPreview.change_direction === "lateral") {
            toast.message("You're already on this billing cycle.");
            return;
        }

        setPlanChangeBusy(true);
        try {
            const response = await changePlan({
                target_cycle: selectedBillingCycle,
                current_cycle: planPreview.current_cycle ?? undefined,
            });
            toast.success(response.message);
            await refreshProfile();
            await loadPlanPreview(selectedBillingCycle);
        } catch (err: any) {
            toast.error(extractError(err, "Couldn't update your plan right now."));
        } finally {
            setPlanChangeBusy(false);
        }
    };

    const handleOpenBillingPortal = async () => {
        if (portalBusy) return;
        setPortalBusy(true);
        try {
            const data = await getBillingPortalUrl();
            window.location.href = data.portal_url;
        } catch {
            toast.error("Couldn't open billing right now. Please try again.");
        } finally {
            setPortalBusy(false);
        }
    };

    const handleBuyExtraCredits = async () => {
        if (topupBusy) return;
        if (topupAmountUsd < 5) {
            toast.error("Minimum top-up is $5.");
            return;
        }
        setTopupBusy(true);
        try {
            const response = await createCreditTopupCheckout({
                amount_usd: topupAmountUsd,
                success_url: `${window.location.origin}/dashboard/settings`,
                cancel_url: `${window.location.origin}/dashboard/settings`,
            });
            window.location.href = response.checkout_url;
        } catch (err: any) {
            toast.error(err?.response?.data?.detail || "Couldn't start checkout for extra credits.");
        } finally {
            setTopupBusy(false);
        }
    };

    // Helpers for nested preference objects
    const notifPref: NotificationPreferences = settings?.notification_preferences ?? {
        push_enabled: false,
        push_urgent_tasks: false,
        push_deadlines: false,
        push_digests: false,
        push_briefings: false,
    };
    const reminderPref: ReminderPreferences = settings?.reminder_preferences ?? { enabled: false };

    const setNotifPref = (key: string, val: boolean) =>
        updateSetting("notification_preferences", { ...notifPref, [key]: val });

    const setReminderPref = (key: string, val: boolean | string) =>
        updateSetting("reminder_preferences", { ...reminderPref, [key]: val });

    // Actions
    const handleSignOutAll = async () => {
        await supabase.auth.signOut({ scope: "global" });
        window.location.href = "/login";
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

    // ── Shared SVGs ───────────────────────────────────────────────────────────
    const GoogleLogo = () => (
        <svg width="16" height="16" viewBox="0 0 48 48">
            <path d="M44.5 20H24v8.5h11.8C34.7 33.9 30.1 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4z" fill="#4285F4" />
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
        </svg>
    );
    const MicrosoftLogo = () => (
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="2" y="2" width="9" height="9" fill="#F25022" />
            <rect x="13" y="2" width="9" height="9" fill="#7FBA00" />
            <rect x="2" y="13" width="9" height="9" fill="#00A4EF" />
            <rect x="13" y="13" width="9" height="9" fill="#FFB900" />
        </svg>
    );

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

            {/* ── Personal / Executive (shared profile fields) ──────────────── */}
            {(activeTab === "personal" || activeTab === "executive") && (
                <div className="space-y-5">

                    <Section>
                        <SectionLabel>{activeTab === "executive" ? "Their Profile" : "Your Profile"}</SectionLabel>
                        <Pad>
                            <div className="space-y-4">
                                <div>
                                    <p className="text-[12px] text-muted-foreground font-inter mb-1.5">
                                        {activeTab === "executive" ? "Their full name" : "Full name"}
                                    </p>
                                    <Input
                                        value={activeTab === "executive" ? execFullName : fullName}
                                        onChange={(e) => activeTab === "executive" ? setExecFullName(e.target.value) : setFullName(e.target.value)}
                                        onBlur={() => {
                                            if (activeTab === "executive") {
                                                const v = execFullName.trim() || null;
                                                if (v !== (settings?.exec_full_name ?? null)) updateSetting("exec_full_name", v);
                                            } else {
                                                const v = fullName.trim() || null;
                                                if (v !== (settings?.full_name ?? null)) updateSetting("full_name", v);
                                            }
                                        }}
                                        placeholder={activeTab === "executive" ? "Executive's full name" : "Your full name"}
                                        className="h-9 text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                                    />
                                </div>
                                <div>
                                    <p className="text-[12px] text-muted-foreground font-inter mb-1.5">
                                        {activeTab === "executive" ? "What should Teeks call your executive?" : "What should Teeks call you?"}
                                    </p>
                                    <Input
                                        value={activeTab === "executive" ? execPreferredName : preferredName}
                                        onChange={(e) => activeTab === "executive" ? setExecPreferredName(e.target.value) : setPreferredName(e.target.value)}
                                        onBlur={() => {
                                            if (activeTab === "executive") {
                                                const v = execPreferredName.trim() || null;
                                                if (v !== (settings?.exec_preferred_name ?? null)) updateSetting("exec_preferred_name", v);
                                            } else {
                                                const v = preferredName.trim() || null;
                                                if (v !== (settings?.preferred_name ?? null)) updateSetting("preferred_name", v);
                                            }
                                        }}
                                        placeholder={activeTab === "executive" ? "How they prefer to be addressed" : "Preferred name"}
                                        className="h-9 text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                                    />
                                </div>
                            </div>
                        </Pad>
                    </Section>

                    <Section>
                        <SectionLabel>{activeTab === "executive" ? "Their Role" : "Your Role"}</SectionLabel>
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-2">
                                {activeTab === "executive" ? "What best describes their role?" : "What best describes your role?"}
                            </p>
                            <select
                                value={activeTab === "executive" ? execRole : role}
                                onChange={(e) => {
                                    const val = e.target.value;
                                    if (activeTab === "executive") {
                                        setExecRole(val);
                                        if (val !== "Other") { setExecRoleOtherText(""); saveExecRole(val, ""); }
                                    } else {
                                        setRole(val);
                                        if (val !== "Other") { setRoleOtherText(""); saveRole(val, ""); }
                                    }
                                }}
                                className={cn(
                                    "w-full h-9 rounded-lg border border-border bg-background px-3 text-[13px] font-inter",
                                    "focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-colors",
                                    !(activeTab === "executive" ? execRole : role) ? "text-muted-foreground" : "text-foreground"
                                )}
                            >
                                <option value="" disabled>
                                    {activeTab === "executive" ? "Select their role" : "Select your role"}
                                </option>
                                {(activeTab === "executive" ? EXECUTIVE_ROLE_OPTIONS : ROLE_OPTIONS).map((opt) => (
                                    <option key={opt} value={opt}>{opt}</option>
                                ))}
                            </select>
                            {(activeTab === "executive" ? execRole : role) === "Other" && (
                                <Input
                                    value={activeTab === "executive" ? execRoleOtherText : roleOtherText}
                                    onChange={(e) => activeTab === "executive" ? setExecRoleOtherText(e.target.value) : setRoleOtherText(e.target.value)}
                                    onBlur={() => activeTab === "executive" ? saveExecRole("Other", execRoleOtherText) : saveRole("Other", roleOtherText)}
                                    placeholder={activeTab === "executive" ? "Describe their role (optional)" : "Describe your role (optional)"}
                                    className="mt-3 h-9 text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                                />
                            )}
                        </Pad>
                    </Section>

                    <Section>
                        <SectionLabel>Preferences</SectionLabel>
                        <Pad>
                            <p className="text-[12px] text-muted-foreground font-inter mb-3">
                                What preferences should Teeks use in responses and actions?
                            </p>
                            <Textarea
                                value={activeTab === "executive" ? execPrefs : personalPrefs}
                                onChange={(e) => activeTab === "executive" ? setExecPrefs(e.target.value) : setPersonalPrefs(e.target.value)}
                                onFocus={() => activeTab === "executive" ? setExecPrefFocused(true) : setPrefFocused(true)}
                                onBlur={() => {
                                    if (activeTab === "executive") {
                                        setExecPrefFocused(false);
                                        const v = execPrefs.trim() || null;
                                        if (v !== (settings?.exec_preferences ?? null)) {
                                            updateSetting("exec_preferences", v);
                                            if (v) toast.success("Preferences saved");
                                        }
                                    } else {
                                        setPrefFocused(false);
                                        const v = personalPrefs.trim() || null;
                                        if (v !== (settings?.personal_preferences ?? null)) {
                                            updateSetting("personal_preferences", v);
                                            if (v) toast.success("Preferences saved");
                                        }
                                    }
                                }}
                                placeholder={activeTab === "executive"
                                    ? EXEC_PREF_PLACEHOLDERS[execPrefPlaceholderIdx]
                                    : PREF_PLACEHOLDERS[prefPlaceholderIdx]}
                                className="min-h-[110px] text-[13px] bg-background border-border focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30 resize-none font-inter transition-all"
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

            {/* ── Integrations ─────────────────────────────────────────────── */}
            {activeTab === "integrations" && (
                <div className="space-y-5">

                    {/* Email */}
                    <Section>
                        <SectionLabel>Email</SectionLabel>

                        {/* Gmail */}
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

                        {/* Outlook */}
                        <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <Mail size={15} className="text-muted-foreground flex-shrink-0" />
                                <div>
                                    <p className="text-[13px] font-medium text-foreground font-inter">Outlook</p>
                                    <p className="text-[12px] text-muted-foreground font-inter">Email sync and task extraction</p>
                                </div>
                            </div>
                            {settings?.outlook_connected ? (
                                <span className="flex items-center gap-1.5 text-[12px] font-medium text-primary font-inter">
                                    <CheckCircle2 size={13} /> Connected
                                </span>
                            ) : (
                                <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground font-inter">
                                    <XCircle size={13} /> Not connected
                                </span>
                            )}
                        </div>

                        {/* Actions */}
                        <div className="px-5 py-4 flex items-center gap-2">
                            {currentProvider !== "none" ? (
                                <>
                                    <button
                                        type="button"
                                        onClick={() => setDisconnectConfirmOpen(true)}
                                        className="h-8 px-3 rounded-lg border border-border text-[12px] font-medium text-foreground font-inter hover:bg-muted/40 transition-colors"
                                    >
                                        Disconnect {currentProvider === "google" ? "Google" : "Microsoft"}
                                    </button>
                                    <Dialog open={connectOpen} onOpenChange={(open) => { if (!open) setConnectPending(null); setConnectOpen(open); }}>
                                        <DialogTrigger asChild>
                                            <button
                                                type="button"
                                                className="h-8 px-3 rounded-lg border border-border text-[12px] font-medium text-muted-foreground font-inter hover:text-foreground hover:border-foreground/40 transition-colors"
                                            >
                                                Switch provider
                                            </button>
                                        </DialogTrigger>
                                        {/* connect dialog content below */}
                                        <DialogContent className="sm:max-w-md">
                                            <DialogHeader>
                                                <DialogTitle className="font-playfair text-[18px] font-semibold">
                                                    Switch provider
                                                </DialogTitle>
                                                <DialogDescription className="text-[13px] text-muted-foreground font-inter pt-1 leading-relaxed">
                                                    Choose the provider you want Teeks to use.
                                                </DialogDescription>
                                                <div className="pt-2">
                                                    <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-[11px] font-medium text-muted-foreground font-inter">
                                                        Current:{" "}
                                                        <span className="text-foreground">
                                                            {currentProvider === "google" ? "Google" : currentProvider === "microsoft" ? "Microsoft" : "Not connected"}
                                                        </span>
                                                    </span>
                                                </div>
                                            </DialogHeader>
                                            {connectPending ? (
                                                <div className="space-y-4 pt-2">
                                                    <p className="text-[13px] text-foreground font-inter">
                                                        Connecting {connectPending === "google" ? "Google" : "Microsoft"} will disconnect your current provider.
                                                    </p>
                                                    <DialogFooter className="gap-2">
                                                        <button onClick={() => setConnectPending(null)} className="px-4 py-2 text-[13px] font-medium rounded border border-border">Back</button>
                                                        <button
                                                            onClick={() => void startProviderConnect(connectPending)}
                                                            disabled={connectBusy}
                                                            className="px-4 py-2 text-[13px] font-medium rounded bg-foreground text-background disabled:opacity-60"
                                                        >
                                                            {connectBusy ? "Switching..." : "Continue"}
                                                        </button>
                                                    </DialogFooter>
                                                </div>
                                            ) : (
                                                <div className="space-y-3 pt-2">
                                                    <button onClick={() => handleConnectChoice("google")} className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-border hover:border-foreground/40 transition-colors">
                                                        <span className="flex items-center gap-3 text-[13px] font-medium font-inter">
                                                            <GoogleLogo /> Google
                                                        </span>
                                                        {currentProvider === "google" && <span className="text-[11px] text-primary font-medium">Connected</span>}
                                                    </button>
                                                    <button onClick={() => handleConnectChoice("microsoft")} className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-border hover:border-foreground/40 transition-colors">
                                                        <span className="flex items-center gap-3 text-[13px] font-medium font-inter">
                                                            <MicrosoftLogo /> Microsoft
                                                        </span>
                                                        {currentProvider === "microsoft" && <span className="text-[11px] text-primary font-medium">Connected</span>}
                                                    </button>
                                                </div>
                                            )}
                                        </DialogContent>
                                    </Dialog>
                                </>
                            ) : (
                                <Dialog open={connectOpen} onOpenChange={(open) => { if (!open) setConnectPending(null); setConnectOpen(open); }}>
                                    <DialogTrigger asChild>
                                        <button
                                            type="button"
                                            className="h-8 px-3 rounded-lg bg-primary text-primary-foreground text-[12px] font-medium font-inter hover:bg-primary/90 transition-colors"
                                        >
                                            Connect an account
                                        </button>
                                    </DialogTrigger>
                                    <DialogContent className="sm:max-w-md">
                                        <DialogHeader>
                                            <DialogTitle className="font-playfair text-[18px] font-semibold">
                                                Connect your inbox
                                            </DialogTitle>
                                            <DialogDescription className="text-[13px] text-muted-foreground font-inter pt-1 leading-relaxed">
                                                Choose the provider you want Teeks to use.
                                            </DialogDescription>
                                        </DialogHeader>
                                        <div className="space-y-3 pt-2">
                                            <button onClick={() => handleConnectChoice("google")} className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-border hover:border-foreground/40 transition-colors">
                                                <span className="flex items-center gap-3 text-[13px] font-medium font-inter">
                                                    <GoogleLogo /> Google
                                                </span>
                                            </button>
                                            <button onClick={() => handleConnectChoice("microsoft")} className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-border hover:border-foreground/40 transition-colors">
                                                <span className="flex items-center gap-3 text-[13px] font-medium font-inter">
                                                    <MicrosoftLogo /> Microsoft
                                                </span>
                                            </button>
                                        </div>
                                    </DialogContent>
                                </Dialog>
                            )}
                        </div>
                    </Section>

                    {/* Calendar */}
                    <Section>
                        <SectionLabel>Calendar</SectionLabel>

                        {/* Google Calendar */}
                        <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-4">
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

                        {/* Microsoft Calendar */}
                        <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <Calendar size={15} className="text-muted-foreground flex-shrink-0" />
                                <div>
                                    <p className="text-[13px] font-medium text-foreground font-inter">Microsoft Calendar</p>
                                    <p className="text-[12px] text-muted-foreground font-inter">Meeting briefings and scheduling</p>
                                </div>
                            </div>
                            {settings?.outlook_connected ? (
                                <span className="flex items-center gap-1.5 text-[12px] font-medium text-primary font-inter">
                                    <CheckCircle2 size={13} /> Connected
                                </span>
                            ) : (
                                <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground font-inter">
                                    <XCircle size={13} /> Not connected
                                </span>
                            )}
                        </div>

                        {/* Meeting Briefings */}
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

                    {/* Default Calendar */}
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

                    {/* Disconnect confirmation dialog */}
                    <Dialog open={disconnectConfirmOpen} onOpenChange={setDisconnectConfirmOpen}>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle className="font-playfair text-[18px] font-semibold">
                                    Disconnect {currentProvider === "google" ? "Google" : "Microsoft"}?
                                </DialogTitle>
                                <DialogDescription className="text-[13px] text-muted-foreground font-inter pt-1 leading-relaxed">
                                    This will stop email and calendar syncing. Your existing data won't be deleted.
                                </DialogDescription>
                            </DialogHeader>
                            <DialogFooter className="gap-2 pt-2">
                                <button
                                    type="button"
                                    onClick={() => setDisconnectConfirmOpen(false)}
                                    className="h-9 px-4 rounded-lg text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors font-inter"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="button"
                                    onClick={handleDisconnect}
                                    disabled={disconnectBusy}
                                    className="h-9 px-4 rounded-lg bg-foreground text-background text-[13px] font-medium font-inter hover:bg-foreground/90 transition-colors disabled:opacity-60"
                                >
                                    {disconnectBusy ? "Disconnecting..." : "Disconnect"}
                                </button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
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
                        <SectionLabel>Billing</SectionLabel>
                        {settings?.subscription_tier === "pro" ? (
                            <Pad>
                                <div className="space-y-3">
                                    <p className="text-[12px] text-muted-foreground font-inter">
                                        Select billing cycle
                                    </p>
                                    <div className="inline-flex rounded-lg border border-border p-1 bg-background">
                                        <button
                                            type="button"
                                            onClick={() => setSelectedBillingCycle("monthly")}
                                            className={cn(
                                                "px-3 py-1.5 rounded-md text-xs font-medium font-inter transition-colors",
                                                selectedBillingCycle === "monthly"
                                                    ? "bg-primary text-primary-foreground"
                                                    : "text-muted-foreground hover:bg-muted/60"
                                            )}
                                        >
                                            Monthly
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setSelectedBillingCycle("annual")}
                                            className={cn(
                                                "px-3 py-1.5 rounded-md text-xs font-medium font-inter transition-colors",
                                                selectedBillingCycle === "annual"
                                                    ? "bg-primary text-primary-foreground"
                                                    : "text-muted-foreground hover:bg-muted/60"
                                            )}
                                        >
                                            Annual
                                        </button>
                                    </div>

                                    <div className="rounded-lg border border-border bg-muted/20 p-3">
                                        {planPreviewLoading ? (
                                            <div className="flex items-center gap-2 text-[12px] text-muted-foreground font-inter">
                                                <Loader2 size={13} className="animate-spin" />
                                                Loading plan details...
                                            </div>
                                        ) : planPreviewError ? (
                                            <p className="text-[12px] text-destructive font-inter">{planPreviewError}</p>
                                        ) : planPreview ? (
                                            <div className="space-y-1.5">
                                                <p className="text-[12px] text-foreground font-medium font-inter">
                                                    {planPreview.message}
                                                </p>
                                                {planPreview.current_cycle && (
                                                    <p className="text-[11px] text-muted-foreground font-inter">
                                                        Current cycle: {planPreview.current_cycle}
                                                    </p>
                                                )}
                                                {planPreview.effective_at && (
                                                    <p className="text-[11px] text-muted-foreground font-inter">
                                                        Effective on: {formatEffectiveAt(planPreview.effective_at)}
                                                    </p>
                                                )}
                                            </div>
                                        ) : (
                                            <p className="text-[12px] text-muted-foreground font-inter">
                                                Select a cycle to preview changes.
                                            </p>
                                        )}
                                    </div>

                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            type="button"
                                            onClick={handleApplyPlanChange}
                                            disabled={
                                                planChangeBusy ||
                                                planPreviewLoading ||
                                                !!planPreviewError ||
                                                !planPreview ||
                                                planPreview.change_direction === "lateral"
                                            }
                                            className="h-9 px-4 rounded-lg bg-primary text-primary-foreground text-[13px] font-medium font-inter hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                                        >
                                            {planChangeBusy ? (
                                                <span className="inline-flex items-center gap-2">
                                                    <Loader2 size={13} className="animate-spin" />
                                                    Updating...
                                                </span>
                                            ) : planPreview?.effective_timing === "next_cycle" ? (
                                                "Schedule change"
                                            ) : (
                                                "Apply now"
                                            )}
                                        </button>
                                        <button
                                            type="button"
                                            onClick={handleOpenBillingPortal}
                                            disabled={portalBusy}
                                            className="h-9 px-4 rounded-lg border border-border text-[13px] font-medium text-foreground font-inter hover:bg-muted/40 transition-colors disabled:opacity-60"
                                        >
                                            {portalBusy ? "Opening..." : "Manage payment method"}
                                        </button>
                                    </div>

                                    <div className="pt-2 border-t border-border/70 space-y-2">
                                        <p className="text-[12px] text-muted-foreground font-inter">
                                            Extra AI credits (power usage)
                                        </p>
                                        <div className="rounded-lg border border-border bg-muted/20 p-3">
                                            {creditStatusLoading ? (
                                                <div className="flex items-center gap-2 text-[12px] text-muted-foreground font-inter">
                                                    <Loader2 size={13} className="animate-spin" />
                                                    Loading credit status...
                                                </div>
                                            ) : creditStatusError ? (
                                                <p className="text-[12px] text-destructive font-inter">{creditStatusError}</p>
                                            ) : creditStatus ? (
                                                <div className="space-y-1 text-[12px] font-inter">
                                                    <p className="text-foreground">Available: {Math.round(creditStatus.credits_remaining * 100)} credits</p>
                                                    <p className="text-muted-foreground">Used: {Math.round(creditStatus.credits_used * 100)} / {Math.round(creditStatus.credits_limit * 100)} credits</p>
                                                </div>
                                            ) : (
                                                <p className="text-[12px] text-muted-foreground font-inter">No credit data available.</p>
                                            )}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            {[5, 10, 25].map((amt) => (
                                                <button
                                                    key={amt}
                                                    type="button"
                                                    onClick={() => setTopupAmountUsd(amt)}
                                                    className={cn(
                                                        "h-8 px-3 rounded-md border text-[12px] font-medium font-inter transition-colors",
                                                        topupAmountUsd === amt
                                                            ? "bg-primary text-primary-foreground border-primary"
                                                            : "border-border text-muted-foreground hover:text-foreground hover:bg-muted/40"
                                                    )}
                                                >
                                                    ${amt}
                                                </button>
                                            ))}
                                            <Input
                                                type="number"
                                                min={5}
                                                step={1}
                                                value={topupAmountUsd}
                                                onChange={(e) => setTopupAmountUsd(Math.max(5, Number(e.target.value) || 5))}
                                                className="h-8 w-24 text-[12px] bg-background border-border"
                                            />
                                            <button
                                                type="button"
                                                onClick={handleBuyExtraCredits}
                                                disabled={topupBusy}
                                                className="h-8 px-3 rounded-md bg-primary text-primary-foreground text-[12px] font-medium font-inter hover:bg-primary/90 transition-colors disabled:opacity-60"
                                            >
                                                {topupBusy ? "Starting..." : `Buy ${topupAmountUsd * 100} credits`}
                                            </button>
                                        </div>
                                        <p className="text-[11px] text-muted-foreground font-inter">
                                            $1 = 100 credits. Minimum top-up is $5.
                                        </p>
                                    </div>
                                </div>
                            </Pad>
                        ) : (
                            <Pad>
                                <p className="text-[12px] text-muted-foreground font-inter mb-3">
                                    You're on Trial. Choose Pro to unlock all capabilities.
                                </p>
                                <button
                                    type="button"
                                    onClick={() => { window.location.href = "/auth/subscription"; }}
                                    className="h-9 px-4 rounded-lg bg-primary text-primary-foreground text-[13px] font-medium font-inter hover:bg-primary/90 transition-colors"
                                >
                                    Choose plan
                                </button>
                            </Pad>
                        )}
                    </Section>

                    <Section>
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

                    <div className="rounded-[14px] border border-border bg-card px-5 py-5 space-y-4"
                        style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)" }}
                    >
                        <div className="flex gap-3">
                            <Shield size={14} className="text-muted-foreground shrink-0 mt-0.5" />
                            <p className="text-[13px] text-foreground font-inter leading-relaxed">
                                Your email content is encrypted. We use industry standard encryption so your data stays protected.
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <Shield size={14} className="text-muted-foreground shrink-0 mt-0.5" />
                            <p className="text-[13px] text-foreground font-inter leading-relaxed">
                                You stay in control of your data. If you delete your account, your data is permanently removed within 24 hours. No hidden backups. No lingering copies.
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <Shield size={14} className="text-muted-foreground shrink-0 mt-0.5" />
                            <p className="text-[13px] text-foreground font-inter leading-relaxed">
                                Built with security-first principles. We follow SOC 2 security practices from day one, including audit logs, strict data isolation, and regular security reviews.
                            </p>
                        </div>
                    </div>

                    <div className="rounded-[14px] border border-border bg-card px-5 py-5 space-y-4"
                        style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)" }}
                    >
                        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                            How Teeks uses your data
                        </p>
                        <ul className="space-y-3">
                            <li className="text-[13px] text-foreground font-inter leading-relaxed">
                                <span className="font-medium">Your emails are read, not stored in full.</span>{" "}
                                Teeks processes your email content to extract tasks, scheduling info, and action points. Raw email bodies are stored encrypted.
                            </li>
                            <li className="text-[13px] text-foreground font-inter leading-relaxed">
                                <span className="font-medium">Your data stays yours.</span>{" "}
                                Teeks does not share your data with third parties or other users.
                            </li>
                            <li className="text-[13px] text-foreground font-inter leading-relaxed">
                                <span className="font-medium">Aggregate insights only.</span>{" "}
                                Teeks may analyse anonymised usage patterns in aggregate to improve the product. This analysis is never tied back to individual accounts or content.
                            </li>
                        </ul>
                    </div>

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
                            {settings?.subscription_tier === "pro" && settings?.is_active ? (
                                <DialogContent>
                                    <DialogHeader>
                                        <DialogTitle className="font-playfair text-[18px] font-semibold">
                                            Cancel your subscription first
                                        </DialogTitle>
                                        <DialogDescription className="text-[13px] text-muted-foreground font-inter pt-1 leading-relaxed">
                                            You have an active Pro subscription. Cancel it before deleting your account.
                                        </DialogDescription>
                                    </DialogHeader>
                                    <DialogFooter className="gap-2 pt-2">
                                        <button
                                            type="button"
                                            onClick={() => setIsDeleteOpen(false)}
                                            className="h-9 px-4 rounded-lg text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors font-inter"
                                        >
                                            Back
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => { setIsDeleteOpen(false); void handleOpenBillingPortal(); }}
                                            disabled={portalBusy}
                                            className="h-9 px-4 rounded-lg bg-foreground text-background text-[13px] font-medium font-inter hover:bg-foreground/90 transition-colors disabled:opacity-60"
                                        >
                                            {portalBusy ? "Opening..." : "Manage subscription"}
                                        </button>
                                    </DialogFooter>
                                </DialogContent>
                            ) : (
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
                            )}
                        </Dialog>
                    </div>
                </div>
            )}
        </div>
    );
}
