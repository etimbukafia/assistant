"use client";

import { Suspense, useState, useCallback, useEffect } from "react";
import { InboxFeed } from "@/components/inbox/InboxFeed";
import { ThreadDetailPanel } from "@/components/inbox/ThreadDetailPanel";
import { DonnaText } from "@/components/ui/DonnaText";
import { useAuth } from "@/context/AuthContext";
import { Loader2, Inbox, Archive } from "lucide-react";
import { cn } from "@/lib/utils";

export default function InboxPage() {
    const { user, settings, gmailConnectError } = useAuth();
    const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
    const [threadIds, setThreadIds] = useState<string[]>([]);
    const [view, setView] = useState<"inbox" | "archived">("inbox");
    const panelOpen = !!selectedThreadId;

    // Keyboard navigation
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            // ESC to close panel
            if (e.key === "Escape" && panelOpen) {
                setSelectedThreadId(null);
                return;
            }

            // Arrow keys to navigate threads (only when panel is open)
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

    return (
        <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
            {/* Inbox List — shrinks when panel opens */}
            <div className={cn(
                "transition-all duration-300 ease-out overflow-y-auto",
                panelOpen ? "w-[380px] min-w-[380px] border-r border-border/40" : "flex-1 max-w-3xl mx-auto",
            )}>
                <div className={cn("py-8 px-4", panelOpen && "py-4 px-3")}>
                    {/* Header — compact when panel open */}
                    <div className={cn("mb-8 space-y-2", panelOpen && "mb-4 space-y-1")}>
                        <DonnaText variant={panelOpen ? "h3" : "h2"}>
                            {view === "archived" ? "Archive" : "Inbox"}
                        </DonnaText>
                        {!panelOpen && (
                            <DonnaText variant="body" className="text-muted-foreground">
                                Welcome back, {user?.user_metadata?.full_name || user?.email?.split('@')[0]}.
                            </DonnaText>
                        )}
                    </div>

                    {/* View Toggle */}
                    <div className={cn("flex gap-1 mb-6 p-1 rounded-lg bg-muted/50 w-fit", panelOpen && "mb-4")}>
                        <button
                            onClick={() => { setView("inbox"); setSelectedThreadId(null); }}
                            className={cn(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                                view === "inbox"
                                    ? "bg-background text-foreground shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <Inbox size={13} />
                            {!panelOpen && "Inbox"}
                        </button>
                        <button
                            onClick={() => { setView("archived"); setSelectedThreadId(null); }}
                            className={cn(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                                view === "archived"
                                    ? "bg-background text-foreground shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <Archive size={13} />
                            {!panelOpen && "Archived"}
                        </button>
                    </div>

                    {!settings?.initial_sync_completed && !gmailConnectError && (
                        <div className="mb-6 rounded-lg border border-auburn/20 bg-auburn/5 px-4 py-3">
                            <DonnaText variant="body" className="text-obsidian text-sm">
                                We're syncing your emails from today.
                            </DonnaText>
                        </div>
                    )}

                    <Suspense fallback={<div className="flex justify-center items-center h-40"><Loader2 className="h-8 w-8 animate-spin text-auburn" /></div>}>
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
                    />
                )}
            </div>
        </div>
    );
}
