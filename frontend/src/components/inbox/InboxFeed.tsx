"use client";

import { useInbox } from "@/hooks/useInbox";
import { EmailCard } from "./EmailCard";
import { DonnaText } from "@/components/ui/DonnaText";
import { Loader2, Inbox } from "lucide-react";
import { useEffect, useRef } from "react";
import { isToday, isYesterday, parseISO } from "date-fns";

export function InboxFeed() {
    const { data, fetchNextPage, hasNextPage, isFetchingNextPage, status, isFetching } = useInbox();

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

    const messages = data?.pages.flatMap(page => page.messages) || [];

    if (messages.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-[50vh] text-muted-foreground gap-4">
                <Inbox size={48} className="text-muted-foreground/50" />
                <DonnaText variant="h3" className="text-muted-foreground">Inbox Zero!</DonnaText>
                <DonnaText variant="body">Nothing needs your attention right now.</DonnaText>
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
        <div className="space-y-4 pb-20">
            {messages.map((msg, index) => {
                const group = getGroup(msg.received_at);
                const showHeader = group !== lastDateGroup;
                lastDateGroup = group;

                return (
                    <div key={msg.id} className="space-y-4">
                        {showHeader && (
                            <div className="sticky top-0 z-10 bg-linen/95 backdrop-blur-sm py-2 px-1">
                                <DonnaText variant="label" className="text-auburn font-bold tracking-widest uppercase">
                                    {group}
                                </DonnaText>
                            </div>
                        )}
                        <EmailCard message={msg} />
                    </div>
                );
            })}

            {/* Sentinel */}
            <div ref={loadMoreRef} className="h-10 w-full flex items-center justify-center">
                {isFetchingNextPage && <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />}
            </div>
        </div>
    );
}
