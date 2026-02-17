"use client";

import { InboxFeed } from "@/components/inbox/InboxFeed";
import { DonnaText } from "@/components/ui/DonnaText";
import { useAuth } from "@/context/AuthContext";

export default function InboxPage() {
    const { user, settings, gmailConnectError } = useAuth();

    return (
        <div className="container max-w-3xl mx-auto py-8 px-4 min-h-screen">
            <div className="mb-8 space-y-2">
                <DonnaText variant="h2">Inbox</DonnaText>
                <DonnaText variant="body" className="text-muted-foreground">
                    Welcome back, {user?.user_metadata?.full_name || user?.email?.split('@')[0]}.
                </DonnaText>
            </div>

            {!settings?.initial_sync_completed && !gmailConnectError && (
                <div className="mb-6 rounded-lg border border-auburn/20 bg-auburn/5 px-4 py-3">
                    <DonnaText variant="body" className="text-obsidian">
                        We're syncing your emails from today. Your Inbox will show today's processed emails when it's done.
                    </DonnaText>
                </div>
            )}

            <InboxFeed />
        </div>
    );
}
