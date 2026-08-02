"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { DashboardErrorBoundary } from "@/components/DashboardErrorBoundary";
import {
    Settings,
    LogOut,
    Inbox,
    BookOpen,
    Brain,
    Zap,
    Target,
    Calendar,
    CreditCard,
    Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { chatService } from "@/services/chat";
import { getBillingPortalUrl } from "@/services/billing";
import { NotificationBell } from "@/components/notifications/NotificationBell";

// Primary product pillars — Memory and Automations
const primaryNavItems = [
    { href: "/dashboard/chat",        label: "Memory",      icon: Brain },
    { href: "/dashboard/automations", label: "Automations", icon: Zap },
];

// Work surfaces — subordinate to the primary pillars
const workSurfaceItems = [
    { href: "/dashboard/inbox",    label: "Inbox",    icon: Inbox },
    { href: "/dashboard/people",   label: "People",   icon: Users },
    { href: "/dashboard/calendar", label: "Calendar", icon: Calendar },
    { href: "/dashboard/focus",    label: "Focus",    icon: Target },
    { href: "/dashboard/vault",    label: "Diary",    icon: BookOpen },
];

function NavLink({
    href,
    label,
    icon: Icon,
    isActive,
    sidebar = false,
}: {
    href: string;
    label: string;
    icon: React.ElementType;
    isActive: boolean;
    sidebar?: boolean;
}) {
    if (sidebar) {
        return (
            <Link
                href={href}
                className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-colors",
                    isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                )}
            >
                <Icon size={17} strokeWidth={1.8} className="flex-shrink-0" />
                {label}
            </Link>
        );
    }

    return (
        <Link
            href={href}
            title={label}
            className={cn(
                "p-2 rounded-lg transition-colors",
                isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
            )}
        >
            <Icon size={19} strokeWidth={1.8} />
        </Link>
    );
}

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const queryClient = useQueryClient();
    const router = useRouter();
    const { signOut, settings, settingsLoading, refreshProfile, user, loading } = useAuth();
    const pathname = usePathname();
    const prevSyncCompletedRef = useRef<boolean | null>(null);
    const [billingBusy, setBillingBusy] = useState(false);

    // Defence-in-depth auth guard — middleware is primary, this catches edge cases
    // (stale client session, middleware miss on cold navigation).
    useEffect(() => {
        if (!loading && !user) {
            router.replace("/login");
        }
    }, [loading, user, router]);

    if (loading) {
        return <div className="min-h-screen bg-background" />;
    }
    if (!user) {
        return null;
    }

    useEffect(() => {
        if (!settings) return;
        if (prevSyncCompletedRef.current === null) {
            prevSyncCompletedRef.current = settings.initial_sync_completed;
            return;
        }
        if (!prevSyncCompletedRef.current && settings.initial_sync_completed) {
            const storageKey = "teeks_initial_sync_notified";
            if (!window.localStorage.getItem(storageKey)) {
                toast.success("Initial sync complete. Today's processed emails are ready in your Inbox.");
                window.localStorage.setItem(storageKey, "1");
            }
        }
        prevSyncCompletedRef.current = settings.initial_sync_completed;
    }, [settings?.initial_sync_completed, settings]);

    useEffect(() => {
        if (typeof window === "undefined") return;
        let cancelled = false;

        const prefetch = () => {
            if (cancelled) return;
            queryClient
                .prefetchQuery({
                    queryKey: ["chat", "action-chips", 5],
                    queryFn: () => chatService.getActionChips(5),
                    staleTime: 10 * 60 * 1000,
                })
                .catch(() => {});
        };

        const w = window as Window & {
            requestIdleCallback?: (cb: () => void, opts?: { timeout?: number }) => number;
            cancelIdleCallback?: (id: number) => void;
        };

        if (typeof w.requestIdleCallback === "function") {
            const idleId = w.requestIdleCallback(() => prefetch(), { timeout: 1000 });
            return () => {
                cancelled = true;
                if (typeof w.cancelIdleCallback === "function") w.cancelIdleCallback(idleId);
            };
        }

        const timer = window.setTimeout(prefetch, 0);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [queryClient]);

    useEffect(() => {
        if (!settings?.dunning_active) return;
        const interval = window.setInterval(() => {
            refreshProfile().catch(() => {});
        }, 60_000);
        return () => window.clearInterval(interval);
    }, [settings?.dunning_active, refreshProfile]);

    const handleOpenBillingPortal = async () => {
        if (billingBusy) return;
        setBillingBusy(true);
        try {
            const data = await getBillingPortalUrl();
            window.location.href = data.portal_url;
        } catch {
            toast.error("Couldn't open billing right now. Please try again.");
        } finally {
            setBillingBusy(false);
        }
    };

    return (
        <div className="min-h-screen bg-background">

            {/* ── Mobile / tablet header — hidden on lg+ ─────────────────────── */}
            <header className="lg:hidden sticky top-0 z-50 bg-background/95 backdrop-blur-md border-b border-border">
                <div className="h-14 flex items-center justify-between px-4">

                    {/* Logo mark */}
                    <Link href="/dashboard/chat" className="flex items-center gap-2.5">
                        <span className="w-7 h-7 bg-primary rounded-[6px] flex items-center justify-center flex-shrink-0">
                            <span className="font-playfair font-bold text-[15px] text-white leading-none">T</span>
                        </span>
                        <span className="font-playfair font-semibold text-lg text-foreground tracking-tight hidden sm:block">
                            Teeks
                        </span>
                    </Link>

                    {/* Mobile icon nav */}
                    <nav className="flex items-center gap-0.5">
                        <NotificationBell />
                        <span className="w-px h-5 bg-border mx-1" />
                        {primaryNavItems.map((item) => (
                            <NavLink
                                key={item.href}
                                href={item.href}
                                label={item.label}
                                icon={item.icon}
                                isActive={pathname === item.href}
                            />
                        ))}
                        <span className="w-px h-5 bg-border mx-1" />
                        {workSurfaceItems.map((item) => (
                            <NavLink
                                key={item.href}
                                href={item.href}
                                label={item.label}
                                icon={item.icon}
                                isActive={pathname === item.href}
                            />
                        ))}
                        <span className="w-px h-5 bg-border mx-1" />
                        <Link
                            href="/dashboard/settings"
                            title="Settings"
                            className={cn(
                                "p-2 rounded-lg transition-colors",
                                pathname === "/dashboard/settings"
                                    ? "bg-primary/10 text-primary"
                                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                            )}
                        >
                            <Settings size={19} strokeWidth={1.8} />
                        </Link>
                    </nav>
                </div>
            </header>

            <div className="flex">

                {/* ── Desktop sidebar — lg+ ───────────────────────────────────── */}
                <aside className="hidden lg:flex flex-col fixed inset-y-0 left-0 w-[216px] bg-card border-r border-border z-40">

                    {/* Brand */}
                    <div className="h-16 flex items-center px-5 border-b border-border flex-shrink-0">
                        <Link href="/dashboard/chat" className="flex items-center gap-3">
                            <span className="w-8 h-8 bg-primary rounded-[8px] flex items-center justify-center flex-shrink-0 shadow-sm">
                                <span className="font-playfair font-bold text-lg text-white leading-none">T</span>
                            </span>
                            <span className="font-playfair font-semibold text-xl text-foreground tracking-tight">
                                Teeks
                            </span>
                        </Link>
                    </div>

                    {/* Primary navigation */}
                    <nav className="flex-1 flex flex-col px-3 py-4 gap-0.5 overflow-y-auto">
                        {primaryNavItems.map((item) => (
                            <NavLink
                                key={item.href}
                                href={item.href}
                                label={item.label}
                                icon={item.icon}
                                isActive={pathname === item.href}
                                sidebar
                            />
                        ))}

                        {/* Work surfaces — subordinate */}
                        <div className="mt-4 mb-1 px-3">
                            <span className="text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60">
                                Work surfaces
                            </span>
                        </div>
                        {workSurfaceItems.map((item) => (
                            <NavLink
                                key={item.href}
                                href={item.href}
                                label={item.label}
                                icon={item.icon}
                                isActive={pathname === item.href}
                                sidebar
                            />
                        ))}
                    </nav>

                    {/* Footer — Settings + Sign out */}
                    <div className="flex flex-col px-3 py-4 gap-0.5 border-t border-border flex-shrink-0">
                        <NavLink
                            href="/dashboard/settings"
                            label="Settings"
                            icon={Settings}
                            isActive={pathname === "/dashboard/settings"}
                            sidebar
                        />
                        <button
                            onClick={() => signOut()}
                            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors w-full text-left"
                        >
                            <LogOut size={17} strokeWidth={1.8} className="flex-shrink-0" />
                            Sign out
                        </button>
                    </div>
                </aside>

                {/* ── Main content ────────────────────────────────────────────── */}
                <main className="flex-1 lg:pl-[216px] min-h-screen">
                    <div className="mx-auto max-w-7xl px-6 py-8">
                        <div className="hidden lg:flex mb-5 items-center justify-end">
                            <NotificationBell />
                        </div>
                        {/* Dunning banner — skeleton while settings load, real content after */}
                        {settingsLoading && !settings ? (
                            <div className="mb-5 h-[62px] rounded-xl bg-muted/40 animate-pulse" />
                        ) : settings?.dunning_active ? (
                            <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="text-[13px] font-semibold text-amber-900">
                                            {settings.dunning_suspended_at
                                                ? "Pro is paused until payment is updated"
                                                : "Payment update needed to keep Pro active"}
                                        </p>
                                        <p className="mt-0.5 text-[12px] text-amber-800">
                                            {settings.dunning_suspended_at
                                                ? "Update your payment method to restore access immediately."
                                                : `We couldn't process your latest payment. Retry ${Math.max(1, settings.dunning_attempt_count ?? 1)}/3. ${Math.max(0, settings.dunning_days_remaining ?? 0)} day(s) left before Pro is paused.`}
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={handleOpenBillingPortal}
                                        disabled={billingBusy}
                                        className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-white px-3 py-2 text-[12px] font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-60"
                                    >
                                        <CreditCard size={14} />
                                        {billingBusy ? "Opening..." : "Update payment method"}
                                    </button>
                                </div>
                            </div>
                        ) : null}
                        <DashboardErrorBoundary>
                            {children}
                        </DashboardErrorBoundary>
                    </div>
                </main>
            </div>
        </div>
    );
}
