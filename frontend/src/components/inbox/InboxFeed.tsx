"use client";

import { useInbox } from "@/hooks/useInbox";
import { EmailCard } from "./EmailCard";
import { Inbox, Archive } from "lucide-react";
import { useEffect, useRef } from "react";
import { isToday, isYesterday, parseISO } from "date-fns";
import { cn } from "@/lib/utils";
import { useSearchParams } from "next/navigation";

interface InboxFeedProps {
    selectedThreadId?: string | null;
    onSelectThread?: (threadId: string) => void;
    onThreadIdsChange?: (threadIds: string[]) => void;
    compact?: boolean;
    statusFilter?: string;
}

export function InboxFeed({ selectedThreadId, onSelectThread, onThreadIdsChange, compact, statusFilter }: InboxFeedProps) {
    const searchParams = useSearchParams();
    const highlightId = searchParams.get("messageId");
    const { data, fetchNextPage, hasNextPage, isFetchingNextPage, status } = useInbox({
        status: statusFilter,
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

    // Report thread IDs to parent for keyboard navigation
    const prevThreadIdsRef = useRef<string>("");
    useEffect(() => {
        if (!onThreadIdsChange) return;
        const ids = messages
            .map(m => m.thread_id)
            .filter((id): id is string => !!id);
        const unique = [...new Set(ids)];
        const key = unique.join(",");
        if (key !== prevThreadIdsRef.current) {
            prevThreadIdsRef.current = key;
            onThreadIdsChange(unique);
        }
    }, [messages, onThreadIdsChange]);

    useEffect(() => {
        if (!highlightId) return;
        const target = document.getElementById(`message-${highlightId}`);
        if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [highlightId, messages.length]);

    if (status === "pending") {
        return (
            <div className="flex justify-center items-center h-40 gap-1">
                <span className="teeks-dot" />
                <span className="teeks-dot" />
                <span className="teeks-dot" />
            </div>
        );
    }

    if (status === "error") {
        return (
            <p className="text-center p-8 text-destructive font-inter text-sm">
                Error loading inbox. Please try again.
            </p>
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
            {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-[40vh] text-muted-foreground gap-4 animate-in fade-in zoom-in-95 duration-500">
                    {statusFilter === "archived" ? (
                        <Archive size={40} className="text-muted-foreground/25" />
                    ) : (
                        <Inbox size={40} className="text-muted-foreground/25" />
                    )}
                    <p className="font-playfair text-xl text-muted-foreground/70">
                        {statusFilter === "archived" ? "No archived messages" : "Inbox zero"}
                    </p>
                    {!compact && (
                        <p className="text-sm font-inter text-muted-foreground/50 text-center max-w-xs">
                            {statusFilter === "archived"
                                ? "Messages you archive will appear here."
                                : "Nothing needs your attention right now."}
                        </p>
                    )}
                </div>
            ) : (
                <div className={cn("space-y-4", compact && "space-y-2")}>
                    {messages.map((msg) => {
                        const group = getGroup(msg.received_at);
                        const showHeader = group !== lastDateGroup;
                        lastDateGroup = group;
                        const isSelected = selectedThreadId === msg.thread_id;

                        return (
                            <div
                                key={msg.id}
                                id={`message-${msg.id}`}
                                className={cn(
                                    "space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-500",
                                    compact && "space-y-2"
                                )}
                            >
                                {showHeader && (
                                    <div className="sticky top-0 z-10 bg-linen/95 backdrop-blur-sm py-2 flex items-center gap-3">
                                        <span className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter shrink-0">
                                            {group}
                                        </span>
                                        <div className="flex-1 h-px bg-border/40" />
                                    </div>
                                )}
                                <EmailCard
                                    message={msg}
                                    highlight={highlightId === String(msg.id)}
                                    selected={isSelected}
                                    compact={compact}
                                    onClick={(threadId) => onSelectThread?.(threadId)}
                                />
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Sentinel */}
            <div ref={loadMoreRef} className="h-10 w-full flex items-center justify-center gap-1">
                {isFetchingNextPage && (
                    <>
                        <span className="teeks-dot" />
                        <span className="teeks-dot" />
                        <span className="teeks-dot" />
                    </>
                )}
            </div>
        </div>
    );
}
