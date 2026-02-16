"use client";

import { InboxFeed } from "@/components/inbox/InboxFeed";
import { DonnaText } from "@/components/ui/DonnaText";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

export default function InboxPage() {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="flex justify-center items-center h-screen bg-linen">
                <Loader2 className="h-8 w-8 animate-spin text-auburn" />
            </div>
        );
    }

    return (
        <div className="container max-w-3xl mx-auto py-8 px-4 min-h-screen">
            <div className="mb-8 space-y-2">
                <DonnaText variant="h2">Inbox</DonnaText>
                <DonnaText variant="body" className="text-muted-foreground">
                    Welcome back, {user?.user_metadata?.full_name || user?.email?.split('@')[0]}.
                </DonnaText>
            </div>

            <InboxFeed />
        </div>
    );
}
