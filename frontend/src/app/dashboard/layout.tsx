"use client";

import { useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { Settings, LogOut, Inbox, BookOpen, MessageSquare, Target, Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { signOut, settings, settingsLoading, loading } = useAuth();
    const pathname = usePathname();
    const router = useRouter();

    // Onboarding guard: redirect users who haven't completed setup
    useEffect(() => {
        if (loading || settingsLoading || !settings) return;

        if (!settings.is_active && !settings.onboarding_completed) {
            router.replace('/auth/subscription');
        } else if (settings.is_active && !settings.onboarding_completed) {
            router.replace('/auth/setup');
        }
    }, [settings, loading, settingsLoading, router]);

    // Show loading while checking onboarding status
    if (loading || settingsLoading || !settings) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-linen">
                <Loader2 className="h-8 w-8 animate-spin text-auburn" />
            </div>
        );
    }

    // Don't render dashboard if user needs onboarding
    if (!settings.is_active && !settings.onboarding_completed) return null;
    if (settings.is_active && !settings.onboarding_completed) return null;

    const navItems = [
        { href: "/dashboard/chat", label: "Chat", icon: <MessageSquare size={18} /> },
        { href: "/dashboard/focus", label: "Focus", icon: <Target size={18} /> },
        { href: "/dashboard/vault", label: "Knowledge", icon: <BookOpen size={18} /> },
        { href: "/dashboard/inbox", label: "Inbox", icon: <Inbox size={18} /> },
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
