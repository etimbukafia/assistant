"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaText } from "@/components/ui/DonnaText";
import { completeOnboarding } from "@/services/onboarding";
import { useRouter } from "next/navigation";
import { Loader2, RefreshCw } from "lucide-react";
import { ENABLE_MICROSOFT_UI } from "@/config/featureFlags";

export default function SetupPage() {
    const router = useRouter();
    const {
        settings,
        loading,
        gmailConnectError,
        signInWithGoogle,
        microsoftConnectError,
        signInWithMicrosoft,
        refreshProfile,
    } = useAuth();
    const [error, setError] = useState<string | null>(null);
    const initOnceRef = useRef(false);

    useEffect(() => {
        if (loading) return;
        if (gmailConnectError || (ENABLE_MICROSOFT_UI && microsoftConnectError)) return;
        if (initOnceRef.current) return;
        initOnceRef.current = true;

        const run = async () => {
            try {
                if (settings && !settings.onboarding_completed) {
                    await completeOnboarding({});
                    await refreshProfile();
                }
                router.replace('/dashboard');
            } catch (err: any) {
                setError(err?.response?.data?.detail || "Something went wrong. Please try again.");
            }
        };
        run();
    }, [settings, loading, gmailConnectError, microsoftConnectError, refreshProfile, router]);

    const connectError = ENABLE_MICROSOFT_UI ? (microsoftConnectError || gmailConnectError) : gmailConnectError;
    const providerLabel = ENABLE_MICROSOFT_UI && microsoftConnectError ? "Microsoft" : "Gmail";

    if (!connectError) {
        return null;
    }

    return (
        <div className="min-h-screen bg-linen">
            <div className="max-w-lg mx-auto px-6 pt-16 pb-8 flex flex-col items-center text-center">
                <Loader2 className="h-8 w-8 animate-spin text-auburn mb-4" />
                <DonnaText variant="h2" className="font-playfair text-obsidian text-[24px] mb-2">
                    We couldn't connect {providerLabel}
                </DonnaText>
                <DonnaText variant="body" className="text-faint text-base leading-6">
                    Please reconnect to continue. We'll resume syncing right after.
                </DonnaText>

                <div className="mt-6">
                    <DonnaButton
                        onClick={() => (ENABLE_MICROSOFT_UI && microsoftConnectError) ? signInWithMicrosoft() : signInWithGoogle()}
                        className="flex items-center gap-2 bg-auburn text-white"
                    >
                        <RefreshCw size={16} />
                        Reconnect {providerLabel}
                    </DonnaButton>
                </div>

                {error && (
                    <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm text-center">
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
}
