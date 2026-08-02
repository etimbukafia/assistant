"use client";

import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { Loader2 } from "lucide-react";
import { ENABLE_MICROSOFT_UI } from "@/config/featureFlags";

const CARDS = [
    {
        context: "Board Meeting - Tomorrow 9am",
        urgent: true,
        items: [
            "Q3 numbers need sign-off by tonight",
            "Tom wants 10 mins before",
            "Deck v3 ready - 2 open comments",
        ],
        color: "#FFF8F8",
        rotation: -1.5,
        position: { top: -20, left: 10 },
        zIndex: 4,
        showPin: true,
    },
    {
        context: "CFO responded on Waystar deal",
        items: [
            "They want Thursday call",
            "I've held 3pm and 4pm",
            "NDA draft ready for review",
        ],
        color: "#F4FBFB",
        rotation: 2,
        position: { top: 10, left: 25 },
        zIndex: 3,
    },
    {
        context: "3 emails need you",
        items: [
            "Legal: signature required",
            "Sarah: reschedule request",
            "Investor update: FYI only",
        ],
        color: "#FFFFFF",
        rotation: -3,
        position: { top: 40, left: -10 },
        zIndex: 2,
    },
    {
        context: "Your exec's day tomorrow",
        items: [
            "6 meetings, 2 conflicts",
            "Prep sent for the 10am",
            "Travel docs for Friday ready",
        ],
        color: "#F8F7FF",
        rotation: 4,
        position: { top: 60, left: 30 },
        zIndex: 1,
        opacity: 0.85,
    },
];

function BriefingCard({
    context,
    urgent,
    items,
    color,
    rotation,
    position,
    zIndex,
    showPin,
    opacity,
}: (typeof CARDS)[0]) {
    return (
        <div
            className="absolute w-60 p-4 border border-black/[0.08] shadow-md"
            style={{
                backgroundColor: color,
                transform: `rotate(${rotation}deg)`,
                top: position.top,
                left: position.left,
                zIndex,
                opacity: opacity ?? 1,
                borderRadius: 2,
            }}
        >
            {showPin && (
                <div className="absolute -top-2 left-4 w-7 h-2 bg-black/10 rounded-sm" />
            )}
            <div className="border-b border-black/[0.06] pb-2.5 mb-3">
                <span
                    className={`text-[10px] font-bold uppercase tracking-wider ${urgent ? "text-auburn" : "text-faint"
                        }`}
                >
                    {context}
                </span>
            </div>
            <div className="space-y-2">
                {items.map((item, i) => (
                    <div key={i} className="flex items-start">
                        <span className="text-copper font-black mr-2 text-[13px]">→</span>
                        <span className="flex-1 text-[13px] font-medium text-gray-800 leading-[18px]">
                            {item}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function LoginPage() {
    const { loading, signInWithGoogle, signInWithMicrosoft } = useAuth();

    const handleContinue = () => {
        // Navigate to connect-google trust screen first
        window.location.href = "/auth/connect-google";
    };

    const handleLogin = async () => {
        // Skip trust screen and go straight to Google auth
        await signInWithGoogle();
    };

    const handleContinueMicrosoft = () => {
        window.location.href = "/auth/connect-microsoft";
    };

    const handleLoginMicrosoft = async () => {
        await signInWithMicrosoft();
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-linen">
                <Loader2 className="h-8 w-8 animate-spin text-auburn" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-linen overflow-hidden">
            <div className="max-w-md mx-auto px-6 pb-10 pt-0 flex flex-col items-center min-h-screen">
                {/* Floating Cards Hero */}
                <div className="h-80 flex items-center justify-center mt-12 mb-16">
                    <div className="relative w-72 h-60">
                        {CARDS.map((card, i) => (
                            <BriefingCard key={i} {...card} />
                        ))}
                    </div>
                </div>

                {/* Headline */}
                <div className="text-center mb-8">
                    <h1 className="font-playfair font-bold text-[32px] leading-[48px] tracking-tight text-obsidian mb-4 px-4">
                        <span className="text-[#A91D3A]">Chaos</span>
                        {" out. "}
                        <span className="italic text-copper">Clarity</span>
                        {" in."}
                    </h1>
                    <p className="text-base text-obsidian/80 leading-6 max-w-xs mx-auto">
                        Automation powered by your stored context.
                    </p>
                </div>

                {/* Auth Buttons */}
                <div className="w-full space-y-4 mb-6">
                    <button
                        onClick={handleContinue}
                        className="w-full flex items-center justify-center gap-3 bg-auburn text-white py-4 rounded shadow-lg shadow-auburn/30 font-semibold text-[15px] hover:bg-auburn/90 transition-colors"
                    >
                        <svg width="18" height="18" viewBox="0 0 48 48" fill="#FFFFFF">
                            <path d="M44.5 20H24v8.5h11.8C34.7 33.9 30.1 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4z" />
                        </svg>
                        Continue with Google
                    </button>
                    <button
                        type="button"
                        onClick={handleLogin}
                        className="w-full flex items-center justify-center gap-3 border border-auburn/20 text-auburn py-3.5 rounded font-semibold text-[15px] hover:bg-auburn/5 transition-colors"
                    >
                        Log in with Google
                    </button>
                    {ENABLE_MICROSOFT_UI && (
                        <>
                            <button
                                onClick={handleContinueMicrosoft}
                                className="w-full flex items-center justify-center gap-3 bg-obsidian text-white py-4 rounded shadow-lg shadow-obsidian/20 font-semibold text-[15px] hover:bg-obsidian/90 transition-colors"
                            >
                                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                                    <rect x="2" y="2" width="9" height="9" fill="#F25022" />
                                    <rect x="13" y="2" width="9" height="9" fill="#7FBA00" />
                                    <rect x="2" y="13" width="9" height="9" fill="#00A4EF" />
                                    <rect x="13" y="13" width="9" height="9" fill="#FFB900" />
                                </svg>
                                Continue with Microsoft
                            </button>
                            <p className="text-xs text-faint text-center">
                                Already signed up?{" "}
                                <button
                                    type="button"
                                    onClick={handleLogin}
                                    className="underline text-copper"
                                >
                                    Log in with Google
                                </button>
                                {" "}or{" "}
                                <button
                                    type="button"
                                    onClick={handleLoginMicrosoft}
                                    className="underline text-copper"
                                >
                                    Log in with Microsoft
                                </button>
                            </p>
                        </>
                    )}


                </div>

                {/* Footer */}
                <div className="text-center mt-auto pt-4">
                    <p className="text-xs text-faint leading-[18px]">
                        By continuing, you agree to our{" "}
                        <a
                            href="https://teeks.ai/terms"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-copper underline"
                        >
                            Terms of Service
                        </a>
                        {" "}and{" "}
                        <a
                            href="https://teeks.ai/privacy"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-copper underline"
                        >
                            Privacy Policy
                        </a>
                    </p>
                </div>
            </div>
        </div>
    );
}
