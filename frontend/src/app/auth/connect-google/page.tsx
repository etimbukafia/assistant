"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { ArrowLeft, CheckCircle2, XCircle, ShieldCheck, Loader2 } from "lucide-react";
import Link from "next/link";

export default function ConnectGooglePage() {
    const { signInWithGoogle } = useAuth();
    const [isLoading, setIsLoading] = useState(false);

    const handleConnect = async () => {
        try {
            setIsLoading(true);
            await signInWithGoogle();
        } catch (error) {
            console.error("Google auth error:", error);
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-linen">
            {/* Header */}
            <div className="px-4 pt-4">
                <Link
                    href="/login"
                    className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-black/5 border border-black/10 hover:bg-black/10 transition-colors"
                >
                    <ArrowLeft size={20} className="text-obsidian" />
                </Link>
            </div>

            <div className="max-w-lg mx-auto px-6 pt-4 pb-8">
                {/* Icon & Title */}
                <div className="text-center mb-8">
                    <div className="mx-auto w-16 h-16 rounded-full bg-[#4285F4]/10 flex items-center justify-center mb-4">
                        <svg width="32" height="32" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                            <path d="M5.84 14.13c-.22-.66-.35-1.36-.35-2.13s.13-1.47.35-2.13V7.03H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.97l3.66-2.84z" fill="#FBBC05" />
                            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.03l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                        </svg>
                    </div>
                    <DonnaText variant="h3" className="font-playfair text-obsidian mb-2">
                        Connect Your Google Workspace
                    </DonnaText>
                    <DonnaText variant="body" className="text-faint text-[15px] leading-relaxed">
                        Teeks needs access to your Gmail and Calendar to help manage your work
                    </DonnaText>
                </div>

                {/* Will Do */}
                <div className="mb-6">
                    <DonnaText variant="body" weight="semibold" className="text-obsidian mb-4 text-sm">
                        Teeks will:
                    </DonnaText>
                    <div className="space-y-3">
                        {[
                            "Read emails to extract tasks and context",
                            "Draft responses for your approval",
                            "Check calendar availability when scheduling",
                            "Create events only with your confirmation",
                        ].map((text) => (
                            <div key={text} className="flex items-start gap-2">
                                <CheckCircle2 size={20} className="text-sage shrink-0 mt-0.5" />
                                <span className="text-[15px] text-faint leading-relaxed">{text}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Will Never */}
                <div className="mb-6">
                    <DonnaText variant="body" weight="semibold" className="text-obsidian mb-4 text-sm">
                        Teeks will never:
                    </DonnaText>
                    <div className="space-y-3">
                        {[
                            "Send emails without your approval",
                            "Share or sell your data",
                            "Access files unrelated to email or calendar",
                        ].map((text) => (
                            <div key={text} className="flex items-start gap-2">
                                <XCircle size={20} className="text-red-500 shrink-0 mt-0.5" />
                                <span className="text-[15px] text-faint leading-relaxed">{text}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Revoke Notice */}
                <div className="flex items-start gap-2 bg-copper/10 rounded-lg p-4 mb-8">
                    <ShieldCheck size={20} className="text-copper shrink-0 mt-0.5" />
                    <span className="text-[13px] text-faint leading-5">
                        You can revoke access anytime in your Google account settings
                    </span>
                </div>
            </div>

            {/* Sticky Footer CTA */}
            <div className="sticky bottom-0 bg-white border-t border-border p-6">
                <div className="max-w-lg mx-auto">
                    <button
                        onClick={handleConnect}
                        disabled={isLoading}
                        className="w-full flex items-center justify-center gap-2 bg-[#4285F4] text-white py-4 rounded-full font-semibold text-[17px] shadow-lg shadow-[#4285F4]/30 hover:bg-[#3367D6] transition-colors disabled:opacity-60"
                    >
                        {isLoading ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                            <>
                                <svg width="20" height="20" viewBox="0 0 48 48" fill="#FFFFFF">
                                    <path d="M44.5 20H24v8.5h11.8C34.7 33.9 30.1 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4z" />
                                </svg>
                                Continue with Google
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
