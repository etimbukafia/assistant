"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { Settings, LogOut, Inbox, BookOpen, MessageSquare, Target, Calendar } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { chatService } from "@/services/chat";

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
                .catch(() => {
                    // Non-blocking best-effort prefetch
                });
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

    const navItems = [
        { href: "/dashboard/chat", label: "Chat", icon: <MessageSquare size={18} /> },
        { href: "/dashboard/focus", label: "Focus", icon: <Target size={18} /> },
        { href: "/dashboard/vault", label: "Diary", icon: <BookOpen size={18} /> },
        { href: "/dashboard/inbox", label: "Inbox", icon: <Inbox size={18} /> },
        { href: "/dashboard/calendar", label: "Calendar", icon: <Calendar size={18} /> },
        { href: "/dashboard/settings", label: "Settings", icon: <Settings size={18} /> },
    ];

    return (
        <div className="min-h-screen bg-linen selection:bg-auburn/10">
            <header className="sticky top-0 z-50 w-full border-b border-auburn/10 bg-linen/80 backdrop-blur-md">
                <div className="container mx-auto max-w-5xl h-16 flex items-center justify-between px-4">
                    <div className="flex items-center gap-8">
                        <Link href="/dashboard/chat" className="flex items-center gap-2">
                            <span className="w-8 h-8 bg-auburn rounded shadow-sm flex items-center justify-center text-white font-serif font-bold text-lg">
                                T
                            </span>
                            <DonnaText variant="h3" className="hidden sm:block text-auburn tracking-tight">
                                Teeks
                            </DonnaText>
                        </Link>

                        <nav className="flex items-center gap-1">
                            {navItems.map((item) => (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    className={cn(
                                        "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all group",
                                        pathname === item.href
                                            ? "bg-auburn text-white shadow-md active:scale-95"
                                            : "hover:bg-auburn/5 text-muted-foreground hover:text-auburn"
                                    )}
                                >
                                    {item.icon}
                                    <span className="hidden xs:block">{item.label}</span>
                                </Link>
                            ))}
                        </nav>
                    </div>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => signOut()}
                            className="p-2 text-muted-foreground hover:text-auburn transition-colors rounded-full hover:bg-auburn/5"
                            title="Sign Out"
                        >
                            <LogOut size={20} />
                        </button>
                    </div>
                </div>
            </header>

            <main className="container mx-auto py-8 px-4">
                {children}
            </main>
        </div>
    );
}
