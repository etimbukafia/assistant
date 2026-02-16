"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { completeOnboarding } from "@/services/onboarding";
import { triggerInitialSync } from "@/services/billing";
import { useRouter } from "next/navigation";
import { Sparkles, Mail, Calendar, CheckCircle2, ShieldCheck, ArrowRight, Loader2 } from "lucide-react";

export default function SetupPage() {
    const router = useRouter();
    const { refreshProfile } = useAuth();
    const [assistantName, setAssistantName] = useState("Donna");
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleComplete = async () => {
        setIsProcessing(true);
        setError(null);
        try {
            await completeOnboarding({ assistant_name: assistantName.trim() || "Donna" });

            // Safety net: ensure initial sync was triggered
            try {
                await triggerInitialSync();
            } catch {
                // Non-fatal: 'already_completed' is fine
            }

            await refreshProfile();
            router.replace("/dashboard");
        } catch (err: any) {
            setError(err.response?.data?.detail || "Something went wrong. Please try again.");
            setIsProcessing(false);
        }
    };

    return (
        <div className="min-h-screen bg-linen">
            <div className="max-w-lg mx-auto px-6 pt-10 pb-8">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="mx-auto w-[72px] h-[72px] rounded-full bg-auburn/[0.08] flex items-center justify-center mb-4">
                        <Sparkles size={32} className="text-auburn" />
                    </div>
                    <DonnaText variant="h2" className="font-playfair text-obsidian text-[28px] mb-2">
                        Set Up Your Assistant
                    </DonnaText>
                    <DonnaText variant="body" className="text-faint text-base leading-6">
                        Personalize your experience and connect your accounts
                    </DonnaText>
                </div>

                {/* Assistant Name */}
                <div className="mb-8">
                    <label className="block text-[13px] font-semibold text-faint uppercase tracking-wider mb-4">
                        Name Your Assistant
                    </label>
                    <div className="bg-white rounded-xl border border-border px-4 py-4 mb-1">
                        <input
                            type="text"
                            value={assistantName}
                            onChange={(e) => setAssistantName(e.target.value)}
                            placeholder="Donna"
                            maxLength={50}
                            className="w-full text-lg font-medium text-obsidian bg-transparent outline-none placeholder:text-faint focus-visible:ring-2 focus-visible:ring-auburn/40 rounded"
                        />
                    </div>
                    <p className="text-[13px] text-faint ml-1">
                        This is what your AI assistant will be called throughout the app
                    </p>
                </div>

                {/* What Happens Next */}
                <div className="mb-8">
                    <label className="block text-[13px] font-semibold text-faint uppercase tracking-wider mb-4">
                        What happens next
                    </label>

                    {/* Email Sync */}
                    <div className="flex items-center bg-white rounded-xl border-2 border-border p-4 mb-3">
                        <div className="w-12 h-12 rounded-lg bg-[#EA4335]/10 flex items-center justify-center mr-4 shrink-0">
                            <Mail size={24} className="text-[#EA4335]" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <DonnaText variant="body" weight="semibold" className="text-obsidian text-base">
                                Email Sync
                            </DonnaText>
                            <DonnaText variant="caption" className="text-faint text-[13px] leading-[18px]">
                                Your recent emails will be synced to extract tasks and context
                            </DonnaText>
                        </div>
                        <CheckCircle2 size={24} className="text-sage shrink-0 ml-2" />
                    </div>

                    {/* Calendar */}
                    <div className="flex items-center bg-white rounded-xl border-2 border-border p-4">
                        <div className="w-12 h-12 rounded-lg bg-[#4285F4]/10 flex items-center justify-center mr-4 shrink-0">
                            <Calendar size={24} className="text-[#4285F4]" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <DonnaText variant="body" weight="semibold" className="text-obsidian text-base">
                                Calendar Access
                            </DonnaText>
                            <DonnaText variant="caption" className="text-faint text-[13px] leading-[18px]">
                                Smart scheduling suggestions based on your availability
                            </DonnaText>
                        </div>
                        <CheckCircle2 size={24} className="text-sage shrink-0 ml-2" />
                    </div>
                </div>

                {/* Privacy Note */}
                <div className="flex items-start gap-2 bg-copper/10 rounded-lg p-4">
                    <ShieldCheck size={20} className="text-copper shrink-0 mt-0.5" />
                    <span className="text-[13px] text-faint leading-5">
                        Your data is encrypted and processed securely. We never share your information.
                    </span>
                </div>

                {error && (
                    <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm text-center">
                        {error}
                    </div>
                )}
            </div>

            {/* Sticky Footer */}
            <div className="sticky bottom-0 bg-white border-t border-border p-6">
                <div className="max-w-lg mx-auto">
                    <button
                        onClick={handleComplete}
                        disabled={isProcessing}
                        className="w-full flex items-center justify-center gap-2 bg-auburn text-white py-4 rounded-full font-semibold text-[17px] shadow-lg shadow-auburn/30 hover:bg-auburn/90 transition-colors disabled:opacity-60"
                    >
                        {isProcessing ? (
                            <>
                                <Loader2 className="h-5 w-5 animate-spin" />
                                Setting up...
                            </>
                        ) : (
                            <>
                                Complete Setup
                                <ArrowRight size={20} />
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
