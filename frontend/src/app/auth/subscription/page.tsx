"use client";

import { useState, useMemo } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { activateTrial, createCheckout, triggerInitialSync } from "@/services/billing";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

type PlanType = "trial" | "pro";

export default function SubscriptionPage() {
    const router = useRouter();
    const { user, refreshProfile } = useAuth();
    const [selectedPlan, setSelectedPlan] = useState<PlanType>("trial");
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const firstName = useMemo(() => {
        const fullName = user?.user_metadata?.full_name || user?.user_metadata?.name || "";
        const first = fullName.split(" ")[0];
        return first || "there";
    }, [user]);

    const handleContinue = async () => {
        setIsProcessing(true);
        setError(null);
        try {
            if (selectedPlan === "trial") {
                await activateTrial();
                try {
                    await triggerInitialSync();
                } catch {
                    // Non-fatal: sync can be retried from settings
                }
                await refreshProfile();
                router.replace("/auth/setup");
            } else {
                const data = await createCheckout({
                    success_url: `${window.location.origin}/auth/setup`,
                    cancel_url: `${window.location.origin}/auth/subscription`,
                });
                if (data?.checkout_url) {
                    window.location.href = data.checkout_url;
                }
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || "Something went wrong. Please try again.");
        } finally {
            setIsProcessing(false);
        }
    };

    const ctaText = selectedPlan === "trial"
        ? "Try this week with Teeks"
        : "Try this month with Teeks";

    return (
        <div className="min-h-screen" style={{ backgroundColor: "#FFFDF9" }}>
            <div className="max-w-lg mx-auto px-6 pt-12 pb-8">
                {/* Header */}
                <div className="text-center mb-10">
                    <DonnaText variant="h2" className="font-playfair font-bold text-auburn text-2xl leading-[30px] tracking-tight mb-2">
                        You don&apos;t have to carry alone
                    </DonnaText>
                    <DonnaText variant="body" className="text-faint text-[15px] leading-relaxed">
                        Try Teeks free, or keep it by your side every day
                    </DonnaText>
                </div>

                {/* Email Cards */}
                <div className="space-y-5">
                    {/* Trial Card */}
                    <button
                        onClick={() => setSelectedPlan("trial")}
                        className={`relative w-full text-left rounded-lg overflow-visible transition-all duration-200 ${
                            selectedPlan === "trial"
                                ? "border-2 border-copper shadow-xl shadow-auburn/[0.12]"
                                : "border border-black/5 shadow-md shadow-auburn/[0.04]"
                        }`}
                        style={{ backgroundColor: "#FFFCF8" }}
                    >
                        {/* Clip */}
                        <div className="absolute -top-1.5 left-7 w-9 h-2.5 rounded-sm bg-gray-300 z-10" />

                        {/* Subject */}
                        <div className="px-6 pt-5 pb-2.5 border-b border-dashed border-black/[0.06]">
                            <span className="text-[11px] uppercase tracking-wider text-faint/55">
                                Subject:{" "}
                                <span className="font-semibold text-faint">Teeks Free Trial</span>
                            </span>
                        </div>

                        {/* Body */}
                        <div className="px-6 pt-4 pb-2">
                            <p className="text-[15px] text-obsidian mb-2.5">
                                Dear <span className="text-copper font-semibold">{firstName}</span>,
                            </p>
                            <p className="text-[15px] font-semibold text-obsidian mb-2 leading-relaxed">
                                Start free. See the difference in a week.
                            </p>
                            <p className="text-sm text-faint leading-relaxed">
                                Full access to all pro features and 100 Teeks credits for reply drafting and chat for 5 days. No credit card required.
                            </p>
                        </div>

                        {/* Price */}
                        <div className="px-6 pb-4 flex justify-end">
                            <div className="flex items-baseline">
                                <span className="text-[11px] text-faint/60 mr-0.5">$</span>
                                <span className="font-playfair font-bold text-[22px] text-auburn">0</span>
                                <span className="text-xs text-faint ml-1">/ 5 days</span>
                            </div>
                        </div>
                    </button>

                    {/* Pro Card */}
                    <button
                        onClick={() => setSelectedPlan("pro")}
                        className={`relative w-full text-left rounded-lg overflow-visible transition-all duration-200 ${
                            selectedPlan === "pro"
                                ? "border-2 border-copper shadow-xl shadow-auburn/[0.12]"
                                : "border border-black/5 shadow-md shadow-auburn/[0.04]"
                        } bg-white`}
                    >
                        {/* Copper Clip */}
                        <div className="absolute -top-1.5 left-7 w-9 h-2.5 rounded-sm bg-copper z-10" />

                        {/* Subject */}
                        <div className="px-6 pt-5 pb-2.5 border-b border-dashed border-black/[0.06]">
                            <span className="text-[11px] uppercase tracking-wider text-faint/55">
                                Subject:{" "}
                                <span className="font-semibold text-faint">Teeks Pro</span>
                            </span>
                        </div>

                        {/* Body */}
                        <div className="px-6 pt-4 pb-2">
                            <p className="text-[15px] text-obsidian mb-2.5">
                                Dear <span className="text-copper font-semibold">{firstName}</span>,
                            </p>
                            <p className="text-[15px] font-semibold text-obsidian mb-2 leading-relaxed">
                                Work with clarity. Achieve more with an executive partner at your side.
                            </p>
                            <p className="text-sm text-faint leading-relaxed">
                                Inbox intelligence, task management, AI-assisted replies in your voice, calendar assistance, and executive context memory — everything you need, always by your side.
                            </p>
                        </div>

                        {/* Price */}
                        <div className="px-6 pb-4 flex justify-end">
                            <div className="flex items-baseline">
                                <span className="text-[11px] text-faint/60 mr-0.5">$</span>
                                <span className="font-playfair font-bold text-[22px] text-auburn">19</span>
                                <span className="text-xs text-faint ml-1">/ month</span>
                            </div>
                        </div>
                    </button>

                    {/* Founding Note */}
                    <p className="text-[13px] italic text-faint text-center leading-5">
                        Founding members get full access, early features, and locked-in pricing
                    </p>
                </div>

                {error && (
                    <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm text-center">
                        {error}
                    </div>
                )}
            </div>

            {/* Sticky Footer CTA */}
            <div className="sticky bottom-0 p-6" style={{ backgroundColor: "#FFFDF9" }}>
                <div className="max-w-lg mx-auto">
                    <button
                        onClick={handleContinue}
                        disabled={isProcessing}
                        className="w-full flex items-center justify-center bg-auburn text-white py-4 rounded font-semibold text-[17px] shadow-lg shadow-auburn/25 hover:bg-auburn/90 transition-colors disabled:opacity-60"
                    >
                        {isProcessing ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                            ctaText
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
