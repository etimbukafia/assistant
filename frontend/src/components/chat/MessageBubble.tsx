import * as React from "react"
import { cn } from "@/lib/utils"
import { DonnaText } from "@/components/ui/DonnaText"

interface MessageBubbleProps {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp?: string;
}

export function MessageBubble({ role, content, timestamp }: MessageBubbleProps) {
    const isUser = role === 'user';

    return (
        <div className={cn(
            "flex w-full mb-4",
            isUser ? "justify-end" : "justify-start"
        )}>
            <div className={cn(
                "max-w-[80%] p-3",
                isUser
                    ? "bg-auburn text-white rounded-2xl rounded-tr-sm shadow-md"
                    : "bg-white border border-border/40 text-foreground rounded-2xl rounded-tl-sm shadow-sm"
            )}>
                <DonnaText variant="body" className={cn(
                    "text-sm whitespace-pre-wrap",
                    isUser ? "text-white" : "text-foreground"
                )}>
                    {content}
                </DonnaText>
                {timestamp && (
                    <div className={cn(
                        "text-[10px] mt-1 opacity-70",
                        isUser ? "text-white/80 text-right" : "text-muted-foreground"
                    )}>
                        {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                )}
            </div>
        </div>
    );
}
