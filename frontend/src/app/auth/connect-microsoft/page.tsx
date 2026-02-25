"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaText } from "@/components/ui/DonnaText";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

export default function ConnectMicrosoftPage() {
    const { signInWithMicrosoft } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleConnect = async () => {
        try {
            setIsLoading(true);
            setError(null);
            await signInWithMicrosoft();
        } catch (error) {
            console.error("Microsoft auth error:", error);
            setError("Could not start Microsoft sign-in. Please try again.");
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-[#F9F6F2] min-h-screen font-sans flex flex-col justify-center items-center p-6 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
                <svg className="absolute -top-20 -left-20 w-[600px] h-[600px] text-[#0F172A] opacity-[0.06] blur-3xl animate-pulse" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                    <path d="M44.7,-76.4C58.9,-69.2,71.8,-59.1,81.6,-46.6C91.4,-34.1,98.1,-19.2,96.5,-4.6C95,10,85.2,24.2,74.5,36.5C63.8,48.8,52.2,59.1,39.6,66.9C27,74.7,13.5,80,0.5,79.1C-12.5,78.2,-25,71.1,-37.2,63.1C-49.4,55.1,-61.3,46.2,-71.1,34.8C-80.9,23.4,-88.6,9.5,-87.3,-3.8C-86,-17.1,-75.7,-29.8,-64.2,-39.3C-52.7,-48.8,-40,-55.1,-27.6,-63.4C-15.2,-71.7,-3.1,-82,10.6,-83.4C24.3,-84.8,30.5,-83.6,44.7,-76.4Z" fill="currentColor" transform="translate(100 100)" />
                </svg>
            </div>

            <div className="fixed top-4 left-4 z-20">
                <Link
                    href="/login"
                    className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-black/5 border border-black/10 hover:bg-black/10 transition-colors"
                >
                    <ArrowLeft size={20} className="text-[#050505]" />
                </Link>
            </div>

            <main className="w-full max-w-2xl bg-white/95 backdrop-blur-sm rounded-2xl shadow-[0_4px_20px_-2px_rgba(0,0,0,0.05),0_2px_10px_-2px_rgba(0,0,0,0.02)] p-8 md:p-12 relative z-10">
                <div className="flex flex-col items-center text-center mb-10">
                    <div className="bg-white rounded-full p-4 shadow-sm border border-gray-100 mb-6">
                        <svg className="w-8 h-8" viewBox="0 0 24 24" aria-hidden="true">
                            <rect x="2" y="2" width="9" height="9" fill="#F25022" />
                            <rect x="13" y="2" width="9" height="9" fill="#7FBA00" />
                            <rect x="2" y="13" width="9" height="9" fill="#00A4EF" />
                            <rect x="13" y="13" width="9" height="9" fill="#FFB900" />
                        </svg>
                    </div>
                    <h1 className="text-3xl md:text-4xl font-playfair text-[#050505] mb-4">
                        Calm, connected support.
                    </h1>
                    <p className="text-[#525252] max-w-lg text-lg">
                        Teeks connects to Microsoft so your day stays clear and in control.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                    <div className="space-y-4">
                        <h3 className="font-semibold text-[#050505] text-lg mb-2 flex items-center">
                            <span className="material-symbols-outlined text-[#8A9A5B] mr-2">verified</span>
                            Teeks will:
                        </h3>
                        <ul className="space-y-4">
                            {[
                                { icon: "mark_email_read", text: "Read Outlook mail to extract tasks and context" },
                                { icon: "edit_note", text: "Draft responses for your approval" },
                                { icon: "event_available", text: "Check calendar availability when scheduling" },
                                { icon: "event_upcoming", text: "Create events only with your confirmation" },
                            ].map((item) => (
                                <li key={item.text} className="flex items-start">
                                    <span className="material-symbols-outlined text-[#8A9A5B] text-xl flex-shrink-0 mt-0.5">{item.icon}</span>
                                    <span className="text-[#525252] text-sm ml-3">{item.text}</span>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="space-y-4">
                        <h3 className="font-semibold text-[#050505] text-lg mb-2 flex items-center">
                            <span className="material-symbols-outlined text-red-600 mr-2">gpp_maybe</span>
                            Teeks will never:
                        </h3>
                        <ul className="space-y-4">
                            {[
                                { icon: "send_time_extension", text: "Send emails without your approval" },
                                { icon: "sell", text: "Share or sell your data" },
                                { icon: "folder_off", text: "Access files unrelated to email or calendar" },
                            ].map((item) => (
                                <li key={item.text} className="flex items-start">
                                    <span className="material-symbols-outlined text-red-600 text-xl flex-shrink-0 mt-0.5">{item.icon}</span>
                                    <span className="text-[#525252] text-sm ml-3">{item.text}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>

                <div className="bg-[#0F172A]/10 rounded-xl p-4 mb-10 flex items-center justify-center space-x-3 border border-[#0F172A]/15">
                    <span className="material-symbols-outlined text-[#0F172A] text-xl">shield</span>
                    <p className="text-sm text-[#525252] font-medium">
                        You can revoke access anytime in your Microsoft account settings
                    </p>
                </div>

                <div className="space-y-4">
                    <button
                        onClick={handleConnect}
                        disabled={isLoading}
                        className="w-full flex items-center justify-center gap-3 bg-obsidian text-white py-4 rounded shadow-lg shadow-obsidian/25 font-semibold text-[15px] hover:bg-obsidian/90 transition-colors disabled:opacity-60"
                    >
                        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Continue with Microsoft"}
                    </button>
                    {error && (
                        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm text-center">
                            {error}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
