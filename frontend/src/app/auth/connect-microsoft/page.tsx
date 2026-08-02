"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ENABLE_MICROSOFT_UI } from "@/config/featureFlags";

export default function ConnectMicrosoftPage() {
    const router = useRouter();
    const { signInWithMicrosoft } = useAuth();

    useEffect(() => {
        if (!ENABLE_MICROSOFT_UI) {
            router.replace("/auth/connect-google");
        }
    }, [router]);

    if (!ENABLE_MICROSOFT_UI) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-linen">
                <Loader2 className="h-8 w-8 animate-spin text-auburn" />
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-linen p-6">
            <button
                type="button"
                onClick={() => void signInWithMicrosoft()}
                className="h-11 px-6 rounded-lg bg-obsidian text-white text-sm font-medium hover:bg-obsidian/90 transition-colors"
            >
                Continue with Microsoft
            </button>
        </div>
    );
}
