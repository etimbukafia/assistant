"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import {
    Settings,
    LogOut,
    Inbox,
    BookOpen,
    MessageSquare,
    Target,
    Calendar,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { chatService } from "@/services/chat";

const primaryNavItems = [
    { href: "/dashboard/chat",     label: "Chat",     icon: MessageSquare },
    { href: "/dashboard/focus",    label: "Focus",    icon: Target },
    { href: "/dashboard/inbox",    label: "Inbox",    icon: Inbox },
    { href: "/dashboard/calendar", label: "Calendar", icon: Calendar },
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
    const { signOut, settings } = useAuth();
    const pathname = usePathname();
    const prevSyncCompletedRef = useRef<boolean | null>(null);

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
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
