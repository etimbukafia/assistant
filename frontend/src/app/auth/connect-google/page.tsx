"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import {
    getAutomationReturnPath,
    getAutomationSetupCopy,
    type AutomationId,
} from "@/lib/automationCatalog";

export default function ConnectGooglePage() {
    const { signInWithGoogle } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const searchParams = useSearchParams();
    const automationParam = searchParams.get("automation");
    const automationId: AutomationId | null =
        automationParam === "inbox-copilot" || automationParam === "meeting-prep"
            ? automationParam
            : null;
    const setupCopy = automationId ? getAutomationSetupCopy(automationId) : null;
    const pageTitle = setupCopy?.title ?? "Effortless support begins with trust.";
    const pageSubtitle = setupCopy?.description ?? "Teeks handles the details so you can focus on the big picture";
    const continueLabel = setupCopy?.buttonLabel ?? "Continue with Google";
    const backHref = automationId ? getAutomationReturnPath(automationId) : "/login";
    const willItems = automationId === "meeting-prep"
        ? [
            { icon: "event_available", text: "Read calendar events and attendees for upcoming meetings" },
            { icon: "assignment", text: "Build meeting briefs from stored context and open work" },
            { icon: "mark_email_read", text: "Add recent attendee email context when Gmail is connected" },
            { icon: "visibility", text: "Stay read-only while preparing each brief" },
        ]
        : automationId === "inbox-copilot"
          ? [
              { icon: "mark_email_read", text: "Read emails to triage threads and extract tasks" },
              { icon: "edit_note", text: "Draft responses for your approval" },
              { icon: "history", text: "Use stored relationship context while preparing drafts" },
              { icon: "shield", text: "Keep outgoing messages in draft mode until you approve them" },
          ]
          : [
              { icon: "mark_email_read", text: "Read emails to extract tasks and context" },
              { icon: "edit_note", text: "Draft responses for your approval" },
              { icon: "event_available", text: "Check calendar availability when scheduling" },
              { icon: "event_upcoming", text: "Create events only with your confirmation" },
          ];

    const handleConnect = async () => {
        try {
            setIsLoading(true);
            setError(null);
            await signInWithGoogle(automationId ? getAutomationReturnPath(automationId) : undefined);
        } catch (error) {
            console.error("Google auth error:", error);
            setError("Could not start Google sign-in. Please try again.");
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-[#F9F6F2] min-h-screen font-sans flex flex-col justify-center items-center p-6 relative overflow-hidden">
            {/* Background blobs */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
                <svg className="absolute -top-20 -left-20 w-[600px] h-[600px] text-[#D97745] opacity-[0.08] blur-3xl animate-pulse" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                    <path d="M44.7,-76.4C58.9,-69.2,71.8,-59.1,81.6,-46.6C91.4,-34.1,98.1,-19.2,96.5,-4.6C95,10,85.2,24.2,74.5,36.5C63.8,48.8,52.2,59.1,39.6,66.9C27,74.7,13.5,80,0.5,79.1C-12.5,78.2,-25,71.1,-37.2,63.1C-49.4,55.1,-61.3,46.2,-71.1,34.8C-80.9,23.4,-88.6,9.5,-87.3,-3.8C-86,-17.1,-75.7,-29.8,-64.2,-39.3C-52.7,-48.8,-40,-55.1,-27.6,-63.4C-15.2,-71.7,-3.1,-82,10.6,-83.4C24.3,-84.8,30.5,-83.6,44.7,-76.4Z" fill="currentColor" transform="translate(100 100)" />
                </svg>
                <svg className="absolute -bottom-32 -right-32 w-[700px] h-[700px] text-[#8A9A5B] opacity-[0.12] blur-3xl" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                    <path d="M38.1,-62.4C49.9,-54.9,60.5,-46.4,69.5,-36.1C78.5,-25.8,85.9,-13.7,85.1,-1.9C84.3,9.9,75.3,21.4,66,31.5C56.7,41.6,47.1,50.3,36.5,57.1C25.9,63.9,14.3,68.8,1.9,65.5C-10.5,62.2,-23.7,50.7,-36.3,41.8C-48.9,32.9,-60.9,26.6,-66.9,17.2C-72.9,7.8,-72.9,-4.7,-67.7,-15.8C-62.5,-26.9,-52.1,-36.6,-41.5,-44.6C-30.9,-52.6,-20.1,-58.9,-8.8,-60.2C2.5,-61.5,15,-67.9,38.1,-62.4Z" fill="currentColor" transform="translate(100 100)" />
                </svg>
                <svg className="absolute top-1/4 -right-10 w-[300px] h-[300px] text-[#D97745] opacity-[0.05] blur-2xl" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                    <path d="M47.7,-52.9C61.4,-44.2,71.8,-29.6,75.1,-13.9C78.4,1.8,74.6,18.6,65.4,32.4C56.2,46.2,41.6,57,26.1,61.9C10.6,66.8,-5.8,65.8,-20.8,60.6C-35.8,55.4,-49.4,46,-59.1,33.1C-68.8,20.2,-74.6,3.8,-70.8,-10.1C-67,-24,-53.6,-35.4,-40.9,-44.3C-28.2,-53.2,-16.2,-59.6,0.5,-60.2C17.2,-60.8,34,-55.6,47.7,-52.9Z" fill="currentColor" transform="translate(100 100)" />
                </svg>
            </div>

            {/* Back button */}
            <div className="fixed top-4 left-4 z-20">
                <Link
                    href={backHref}
                    className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-black/5 border border-black/10 hover:bg-black/10 transition-colors"
                >
                    <ArrowLeft size={20} className="text-[#050505]" />
                </Link>
            </div>

            {/* Card */}
            <main className="w-full max-w-2xl bg-white/95 backdrop-blur-sm rounded-2xl shadow-[0_4px_20px_-2px_rgba(0,0,0,0.05),0_2px_10px_-2px_rgba(0,0,0,0.02)] p-8 md:p-12 relative z-10">
                {/* Google Icon */}
                <div className="flex flex-col items-center text-center mb-10">
                    <div className="bg-white rounded-full p-4 shadow-sm border border-gray-100 mb-6">
                        <svg className="w-8 h-8" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                        </svg>
                    </div>
                    <h1 className="text-3xl md:text-4xl font-playfair text-[#050505] mb-4">
                        {pageTitle}
                    </h1>
                    <p className="text-[#525252] max-w-lg text-lg">
                        {pageSubtitle}
                    </p>
                </div>

                {/* Will / Won't grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                    {/* Teeks will */}
                    <div className="space-y-4">
                        <h3 className="font-semibold text-[#050505] text-lg mb-2 flex items-center">
                            <span className="material-symbols-outlined text-[#8A9A5B] mr-2">verified</span>
                            Teeks will:
                        </h3>
                        <ul className="space-y-4">
                            {willItems.map((item) => (
                                <li key={item.text} className="flex items-start">
                                    <span className="material-symbols-outlined text-[#8A9A5B] text-xl flex-shrink-0 mt-0.5">{item.icon}</span>
                                    <span className="text-[#525252] text-sm ml-3">{item.text}</span>
                                </li>
                            ))}
                        </ul>
                    </div>

                    {/* Teeks will never */}
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

                {/* Shield notice */}
                <div className="bg-[#D97745]/10 rounded-xl p-4 mb-10 flex items-center justify-center space-x-3 border border-[#D97745]/20">
                    <span className="material-symbols-outlined text-[#D97745] text-xl">shield</span>
                    <p className="text-sm text-[#525252] font-medium">
                        You can revoke access anytime in your Google account settings
                    </p>
                </div>

                {error && (
                    <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm text-center">
                        {error}
                    </div>
                )}

                {/* CTA */}
                <div className="flex flex-col items-center w-full">
                    <button
                        onClick={handleConnect}
                        disabled={isLoading}
                        className="w-full md:w-3/4 bg-[#4285F4] hover:bg-[#3367D6] text-white font-medium py-3.5 px-6 rounded-full flex items-center justify-center transition-all shadow-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#4285F4] disabled:opacity-60"
                    >
                        {isLoading ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                            <>
                                <span className="bg-white rounded-full p-1 mr-3 flex items-center justify-center">
                                    <svg className="w-4 h-4" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                                    </svg>
                                </span>
                                {continueLabel}
                            </>
                        )}
                    </button>
                    <p className="mt-6 text-xs text-center text-[#525252]">
                        By continuing, you agree to Teeks&apos;{" "}
                        <a className="underline hover:text-[#7E2E2E] transition-colors" href="https://teeks.ai/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a> and{" "}
                        <a className="underline hover:text-[#7E2E2E] transition-colors" href="https://teeks.ai/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.
                    </p>
                </div>
            </main>

            {/* Footer */}
            <footer className="mt-8 text-center z-10">
                <span className="font-playfair italic text-lg text-[#7E2E2E] opacity-60">Teeks.</span>
            </footer>
        </div>
    );
}
