"use client";

import { useInbox } from "@/hooks/useInbox";
import { EmailCard } from "./EmailCard";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { Loader2, Inbox, Zap, ZapOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { isToday, isYesterday, parseISO } from "date-fns";
import { cn } from "@/lib/utils";
import { useSearchParams } from "next/navigation";

export function InboxFeed() {
    const [isFocusMode, setIsFocusMode] = useState(false);
    const searchParams = useSearchParams();
    const highlightId = searchParams.get("messageId");
    const { data, fetchNextPage, hasNextPage, isFetchingNextPage, status } = useInbox({
        needs_reply: isFocusMode ? true : undefined
    });

    // Sentinel logic for infinite scroll
    const loadMoreRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
                fetchNextPage();
            }
        }, { rootMargin: "200px" });

        if (loadMoreRef.current) observer.observe(loadMoreRef.current);
        return () => observer.disconnect();
    }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

    const messages = data?.pages.flatMap(page => page.messages) || [];

    useEffect(() => {
        if (!highlightId) return;
        const target = document.getElementById(`message-${highlightId}`);
        if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [highlightId, messages.length]);

    if (status === "pending") {
        return (
            <div className="flex justify-center items-center h-40">
                <Loader2 className="h-8 w-8 animate-spin text-auburn" />
            </div>
        );
    }

    if (status === "error") {
        return (
            <div className="text-center p-8 text-destructive">
                Error loading inbox. Please try again.
            </div>
        );
    }

    // Group messages logic
    let lastDateGroup: string | null = null;

    const getGroup = (dateStr: string) => {
        const date = parseISO(dateStr);
        if (isToday(date)) return "Today";
        if (isYesterday(date)) return "Yesterday";
        return "Older";
    };

    return (
        <div className="space-y-6 pb-20">
            {/* Header Actions */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <DonnaButton
                        variant="outline"
                        size="sm"
                        onClick={() => setIsFocusMode(!isFocusMode)}
                        className={cn(
                            "gap-2 transition-all duration-300 border-auburn/20 hover:border-auburn/50",
                            isFocusMode && "bg-auburn/10 text-auburn border-auburn"
                        )}
                    >
                        {isFocusMode ? <Zap size={16} className="fill-current" /> : <ZapOff size={16} />}
                        {isFocusMode ? "Focus Mode On" : "Focus Mode Off"}
                    </DonnaButton>

                    {isFocusMode && (
                        <DonnaText variant="caption" className="text-auburn animate-in fade-in slide-in-from-left-2">
                            Showing only actionable items
                        </DonnaText>
                    )}
                </div>
            </div>

            {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-[40vh] text-muted-foreground gap-4 animate-in fade-in zoom-in-95 duration-500">
                    <Inbox size={48} className="text-muted-foreground/30" />
                    <DonnaText variant="h3" className="text-muted-foreground">
                        {isFocusMode ? "All Caught Up!" : "Inbox Zero!"}
                    </DonnaText>
                    <DonnaText variant="body" align="center" className="max-w-xs">
                        {isFocusMode
                            ? "No urgent items requiring your attention."
                            : "Nothing needs your attention right now."}
                    </DonnaText>
                    {isFocusMode && (
                        <DonnaButton variant="link" onClick={() => setIsFocusMode(false)} className="text-auburn">
                            View all messages
                        </DonnaButton>
                    )}
                </div>
            ) : (
                <div className="space-y-4">
                    {messages.map((msg) => {
                        const group = getGroup(msg.received_at);
                        const showHeader = group !== lastDateGroup;
                        lastDateGroup = group;

                        return (
                            <div
                                key={msg.id}
                                id={`message-${msg.id}`}
                                className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-500"
                            >
                                {showHeader && (
                                    <div className="sticky top-0 z-10 bg-linen/95 backdrop-blur-sm py-2 px-1 border-b border-border/40">
                                        <DonnaText variant="label" className="text-auburn font-bold tracking-widest uppercase">
                                            {group}
                                        </DonnaText>
                                    </div>
                                )}
                                <EmailCard message={msg} highlight={highlightId === String(msg.id)} />
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Sentinel */}
            <div ref={loadMoreRef} className="h-10 w-full flex items-center justify-center">
                {isFetchingNextPage && <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />}
            </div>
        </div>
    );
}
