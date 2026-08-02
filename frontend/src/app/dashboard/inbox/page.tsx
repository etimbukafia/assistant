"use client";

import { Suspense, useState, useCallback, useEffect } from "react";
import { InboxFeed } from "@/components/inbox/InboxFeed";
import { ThreadDetailPanel } from "@/components/inbox/ThreadDetailPanel";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { useSearchParams } from "next/navigation";
import { ENABLE_MICROSOFT_UI } from "@/config/featureFlags";

export default function InboxPage() {
    const { user, settings, gmailConnectError, microsoftConnectError } = useAuth();
    const searchParams = useSearchParams();
    const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
    const [threadIds, setThreadIds] = useState<string[]>([]);
    const [view, setView] = useState<"inbox" | "archived">("inbox");
    const panelOpen = !!selectedThreadId;

    // Keyboard navigation
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            if (e.key === "Escape" && panelOpen) {
                setSelectedThreadId(null);
                return;
            }

            if (!panelOpen || threadIds.length === 0) return;
            if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;

            e.preventDefault();
            const currentIndex = selectedThreadId ? threadIds.indexOf(selectedThreadId) : -1;

            if (e.key === "ArrowDown") {
                const next = Math.min(currentIndex + 1, threadIds.length - 1);
                setSelectedThreadId(threadIds[next]);
            } else if (e.key === "ArrowUp") {
                const prev = Math.max(currentIndex - 1, 0);
                setSelectedThreadId(threadIds[prev]);
            }
        }

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [panelOpen, selectedThreadId, threadIds]);

    const handleSelectThread = useCallback((threadId: string) => {
        setSelectedThreadId(threadId);
    }, []);

    const handleClosePanel = useCallback(() => {
        setSelectedThreadId(null);
    }, []);

    useEffect(() => {
        const threadId = searchParams.get("threadId");
        if (threadId) {
            setSelectedThreadId(threadId);
        }
    }, [searchParams]);

    return (
        <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
            {/* Inbox List — shrinks when panel opens */}
            <div className={cn(
                "transition-all duration-300 ease-out overflow-y-auto",
                panelOpen ? "w-[380px] min-w-[380px] border-r border-border/40" : "flex-1 max-w-3xl mx-auto",
            )}>
                <div className={cn("py-8 px-4", panelOpen && "py-4 px-3")}>
                    {/* Header */}
                    <div className={cn("mb-8 space-y-1", panelOpen && "mb-4")}>
                        {!panelOpen && (
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                {user?.user_metadata?.full_name || user?.email?.split('@')[0]}
                            </p>
                        )}
                        <h1 className={cn(
                            "font-playfair text-foreground",
                            panelOpen ? "text-xl font-semibold" : "text-3xl font-bold"
                        )}>
                            {view === "archived" ? "Archive" : "Inbox"}
                        </h1>
                    </div>

                    {/* View Toggle — pill tabs matching Focus/Chat pattern */}
                    <div className={cn("flex gap-1 mb-6 rounded-full border border-border p-1 w-fit", panelOpen && "mb-4")}>
                        <button
                            onClick={() => { setView("inbox"); setSelectedThreadId(null); }}
                            className={cn(
                                "px-3 py-1 rounded-full text-[12px] font-medium font-inter transition-all",
                                view === "inbox"
                                    ? "bg-foreground text-background"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            {panelOpen ? "In" : "Inbox"}
                        </button>
                        <button
                            onClick={() => { setView("archived"); setSelectedThreadId(null); }}
                            className={cn(
                                "px-3 py-1 rounded-full text-[12px] font-medium font-inter transition-all",
                                view === "archived"
                                    ? "bg-foreground text-background"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            {panelOpen ? "Arc" : "Archived"}
                        </button>
                    </div>

                    {settings !== null && !settings.initial_sync_completed && (
                        (
                            ENABLE_MICROSOFT_UI
                                ? (
                                    settings.connected_provider === "microsoft"
                                        ? settings.outlook_connected && !microsoftConnectError
                                        : settings.gmail_connected && !gmailConnectError
                                )
                                : (settings.gmail_connected && !gmailConnectError)
                        )
                    ) && (
                        <div className="mb-6 rounded-[8px] border border-primary/20 bg-primary/[0.04] px-4 py-3">
                            <p className="text-sm font-inter text-foreground/80">
                                We&apos;re syncing your emails from today.
                            </p>
                        </div>
                    )}

                    <Suspense fallback={
                        <div className="flex justify-center items-center h-40 gap-1">
                            <span className="teeks-dot" />
                            <span className="teeks-dot" />
                            <span className="teeks-dot" />
                        </div>
                    }>
                        <InboxFeed
                            selectedThreadId={selectedThreadId}
                            onSelectThread={handleSelectThread}
                            onThreadIdsChange={setThreadIds}
                            compact={panelOpen}
                            statusFilter={view === "archived" ? "archived" : undefined}
                        />
                    </Suspense>
                </div>
            </div>

            {/* Thread Detail Panel — slides in from right */}
            <div className={cn(
                "transition-all duration-300 ease-out overflow-hidden",
                panelOpen ? "flex-1 min-w-0" : "w-0",
            )}>
                {panelOpen && (
                    <ThreadDetailPanel
                        threadId={selectedThreadId}
                        onClose={handleClosePanel}
                        statusContext={view}
                    />
                )}
            </div>
        </div>
    );
}
