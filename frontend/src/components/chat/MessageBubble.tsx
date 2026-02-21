import * as React from "react"
import { cn } from "@/lib/utils"

interface MessageBubbleProps {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp?: string;
}

export function MessageBubble({ role, content, timestamp }: MessageBubbleProps) {
    const isUser = role === 'user';

    return (
        <div className={cn(
            "flex w-full teeks-bubble-in",
            isUser ? "justify-end" : "justify-start"
        )}>
            <div className={cn(
                "max-w-[78%] px-[14px] py-[10px]",
                isUser
                    // User: Peony (#C2185B via --primary), send corner collapses — design_system.md §5
                    ? "bg-primary text-primary-foreground rounded-2xl rounded-br-[4px] shadow-sm"
                    // Assistant: white surface, hairline border, receive corner collapses
                    : "bg-white border border-border text-foreground rounded-2xl rounded-bl-[4px]"
            )}
            style={!isUser ? { boxShadow: '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)' } : undefined}
            >
                <p className={cn(
                    "text-sm leading-[1.55] whitespace-pre-wrap font-inter",
                    isUser ? "text-white" : "text-foreground"
                )}>
                    {content}
                </p>
                {timestamp && (
                    <time
                        dateTime={timestamp}
                        className={cn(
                            "block text-[10px] mt-1.5 font-inter",
                            isUser ? "text-right text-white/60" : "text-muted-foreground/70"
                        )}
                    >
                        {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </time>
                )}
            </div>
        </div>
    );
}
