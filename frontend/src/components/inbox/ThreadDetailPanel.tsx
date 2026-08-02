"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchThreadDetail, ThreadDetailResponse, ThreadMessageDetail } from "@/services/messages";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TaskItem } from "./TaskItem";
import { ReplyComposer } from "./ReplyComposer";
import {
    AlertCircle, X,
    Mail, Clock, Users, Calendar,
    CheckCircle2, ArrowRight, Zap, Archive, RotateCcw, UserPlus,
} from "lucide-react";
import { ContactDialog } from "./ContactDialog";
import { PreReplyContextCard } from "@/components/contacts/PreReplyContextCard";
import { InlineContextCaptureCard } from "@/components/vault/InlineContextCaptureCard";
import { formatDistanceToNow, parseISO, format } from "date-fns";
import { cn } from "@/lib/utils";
import React from "react";
import { useMessageMutations } from "@/hooks/useInbox";

interface ThreadDetailPanelProps {
    threadId: string | null;
    onClose: () => void;
    statusContext?: "inbox" | "archived";
}

export function ThreadDetailPanel({ threadId, onClose, statusContext = "inbox" }: ThreadDetailPanelProps) {
    const { data, isLoading, error } = useQuery({
        queryKey: ["thread-detail", threadId],
        queryFn: () => fetchThreadDetail(threadId!),
        enabled: !!threadId,
        staleTime: 60_000,
    });

    return (
        <div className="h-full flex flex-col bg-background animate-in slide-in-from-right-4 duration-300">
            {/* Top bar */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-border/40 shrink-0">
                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                    Thread
                </p>
                <button
                    onClick={onClose}
                    className="p-1 rounded-[6px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                    <X size={15} />
                </button>
            </div>

            {isLoading ? (
                <div className="flex-1 px-6 py-5 space-y-4 animate-pulse">
                    <div className="h-4 w-3/4 rounded bg-muted-foreground/10" />
                    <div className="h-4 w-1/2 rounded bg-muted-foreground/10" />
                    <div className="rounded-[14px] border border-muted-foreground/10 p-4 space-y-3">
                        <div className="h-3 w-24 rounded bg-muted-foreground/10" />
                        <div className="h-4 w-5/6 rounded bg-muted-foreground/10" />
                        <div className="h-4 w-2/3 rounded bg-muted-foreground/10" />
                    </div>
                    <div className="flex gap-2">
                        <div className="h-8 w-28 rounded-[8px] bg-muted-foreground/10" />
                        <div className="h-8 w-20 rounded-[8px] bg-muted-foreground/10" />
                        <div className="h-8 w-20 rounded-[8px] bg-muted-foreground/10" />
                    </div>
                    <div className="rounded-[14px] border border-muted-foreground/10 p-3 space-y-2">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-muted-foreground/10" />
                            <div className="h-4 w-32 rounded bg-muted-foreground/10" />
                        </div>
                        <div className="pl-11 space-y-2">
                            <div className="h-3 w-full rounded bg-muted-foreground/8" />
                            <div className="h-3 w-5/6 rounded bg-muted-foreground/8" />
                        </div>
                    </div>
                </div>
            ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 text-destructive">
                    <AlertCircle size={24} />
                    <p className="text-sm font-inter">Failed to load thread.</p>
                </div>
            ) : data ? (
                <ThreadContent data={data} threadId={threadId!} onClose={onClose} statusContext={statusContext} />
            ) : null}
        </div>
    );
}

function ThreadContent({
    data,
    threadId,
    onClose,
    statusContext,
}: {
    data: ThreadDetailResponse;
    threadId: string;
    onClose: () => void;
    statusContext: "inbox" | "archived";
}) {
    const { thread_state, messages, tasks, scheduling_suggestions } = data;
    const latestMessage = messages[messages.length - 1];
    const archivedTarget = [...messages].reverse().find((m) => m.status === "archived");
    const actionTargetMessage = statusContext === "archived" ? (archivedTarget || latestMessage) : latestMessage;
    const { markDone, archive, restore } = useMessageMutations();

    const { email: senderEmail, name: senderName } = parseSender(latestMessage?.sender || "");

    return (
        <ScrollArea className="flex-1">
            <div className="px-6 py-5 space-y-0">

                {/* Action Points Hero */}
                <ActionPointsHero
                    actionPoints={thread_state.action_points}
                    needsReply={thread_state.needs_reply}
                    summary={thread_state.summary}
                />

                {/* Pre-reply contact context */}
                {senderEmail && (
                    <div className="py-3">
                        <PreReplyContextCard senderEmail={senderEmail} senderName={senderName} />
                    </div>
                )}

                {latestMessage?.id && (
                    <div className="pb-1">
                        <InlineContextCaptureCard
                            scopeType="message"
                            scopeId={latestMessage.id}
                            linkedTo={latestMessage.subject || senderName || senderEmail || "Email"}
                            heading="Remember this"
                            description="What came out of this conversation that Teeks should hold onto?"
                            placeholder="A decision, a preference, something said…"
                            className="bg-accent/[0.02]"
                            revealStoredCaptureByDefault={false}
                            allowStoredCaptureCorrection={false}
                        />
                    </div>
                )}

                {/* Quick Actions */}
                <div className="flex items-center gap-2 py-4">
                    <ReplyComposer
                        messageId={latestMessage?.id}
                        originalSender={latestMessage?.sender || ""}
                        originalSubject={latestMessage?.subject || ""}
                        threadId={threadId}
                    />

                    {actionTargetMessage?.status !== "archived" && (
                        <button
                            onClick={() => {
                                if (actionTargetMessage) markDone.mutate(actionTargetMessage.id);
                                onClose();
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] border border-sage/40 text-sage hover:bg-sage/10 text-[13px] font-medium font-inter transition-colors"
                        >
                            <CheckCircle2 size={13} />
                            Done
                        </button>
                    )}

                    {actionTargetMessage?.status === "archived" ? (
                        <button
                            onClick={() => {
                                if (actionTargetMessage) restore.mutate(actionTargetMessage.id);
                                onClose();
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] border border-border text-muted-foreground hover:bg-linen text-[13px] font-medium font-inter transition-colors"
                        >
                            <RotateCcw size={13} />
                            Restore
                        </button>
                    ) : (
                        <button
                            onClick={() => {
                                if (actionTargetMessage) archive.mutate(actionTargetMessage.id);
                                onClose();
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] border border-border text-muted-foreground hover:bg-linen text-[13px] font-medium font-inter transition-colors"
                        >
                            <Archive size={13} />
                            Archive
                        </button>
                    )}
                </div>

                <div className="h-px bg-border/40 my-1" />

                {/* Last message */}
                <div className="py-4 space-y-3">
                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                        Last message
                        {messages.length > 1 && (
                            <span className="ml-2 normal-case tracking-normal font-normal text-muted-foreground/40">
                                {messages.length} in thread
                            </span>
                        )}
                    </p>

                    {latestMessage && <MessageBubble message={latestMessage} expanded isLatest />}
                </div>

                {/* Tasks & Scheduling */}
                {(tasks.length > 0 || scheduling_suggestions.length > 0) && (
                    <>
                        <div className="h-px bg-border/40 my-1" />
                        <div className="py-4 space-y-4">
                            {tasks.length > 0 && (
                                <div className="space-y-2">
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                        Tasks
                                    </p>
                                    <div className="flex flex-col gap-2">
                                        {tasks.map(task => (
                                            <div key={task.id} onClick={(e) => e.stopPropagation()}>
                                                <TaskItem task={task} />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {scheduling_suggestions.length > 0 && (
                                <div className="space-y-2">
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                        Scheduling
                                    </p>
                                    {scheduling_suggestions.map(suggestion => (
                                        <div key={suggestion.id} className="p-3 rounded-[8px] bg-copper/[0.06] border border-copper/20 space-y-2">
                                            <div className="flex items-center gap-2">
                                                <Calendar size={13} className="text-copper" />
                                                <span className="text-sm font-medium font-inter text-foreground/80">
                                                    {suggestion.meeting_type} &middot; {suggestion.duration_minutes} min
                                                </span>
                                            </div>
                                            {suggestion.suggested_slots.length > 0 && (
                                                <div className="pl-5 space-y-1">
                                                    {suggestion.suggested_slots.slice(0, 3).map((slot, i) => (
                                                        <p key={i} className="text-[12px] font-inter text-muted-foreground">
                                                            {format(parseISO(slot.start_time), "EEE, MMM d 'at' h:mm a")}
                                                            {slot.has_conflict && <span className="text-destructive ml-1">(conflict)</span>}
                                                        </p>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* Metadata footer */}
                <div className="flex items-center gap-4 text-muted-foreground/40 font-inter pt-4 pb-8" style={{ fontSize: '11px' }}>
                    <div className="flex items-center gap-1">
                        <Mail size={11} />
                        <span>Gmail</span>
                    </div>
                    {latestMessage && (
                        <div className="flex items-center gap-1">
                            <Clock size={11} />
                            <span>{format(parseISO(latestMessage.received_at), "MMM d, yyyy 'at' h:mm a")}</span>
                        </div>
                    )}
                    <div className="flex items-center gap-1">
                        <Users size={11} />
                        <span>{thread_state.message_count} {thread_state.message_count === 1 ? "msg" : "msgs"}</span>
                    </div>
                </div>
            </div>
        </ScrollArea>
    );
}

// ─── ACTION POINTS HERO ──────────────────────────────────────────────────────

function ActionPointsHero({
    actionPoints,
    needsReply,
    summary,
}: {
    actionPoints: string[];
    needsReply: boolean;
    summary?: string;
}) {
    const hasActionPoints = actionPoints.length > 0;

    return (
        <div className="space-y-3">
            {summary && (
                <p className="text-sm text-muted-foreground/80 leading-relaxed font-inter">
                    {summary}
                </p>
            )}

            {needsReply && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-[11px] font-bold uppercase tracking-[1.2px] font-inter">
                    <Zap size={9} className="fill-current" />
                    Reply needed
                </span>
            )}

            {hasActionPoints && (
                <div className="rounded-[14px] bg-linen/60 border border-border p-4 space-y-3">
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded-full bg-primary/15 flex items-center justify-center shrink-0">
                            <ArrowRight size={9} className="text-primary" />
                        </div>
                        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                            What matters
                        </p>
                    </div>
                    <ul className="space-y-2.5">
                        {actionPoints.map((point, i) => (
                            <li key={i} className="flex items-start gap-3">
                                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                                <span className="text-[15px] font-medium leading-snug text-foreground/90">
                                    {point}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {!hasActionPoints && !needsReply && (
                <p className="text-muted-foreground/50 text-sm font-inter italic">
                    No action items detected.
                </p>
            )}
        </div>
    );
}

// ─── MESSAGE BUBBLE ──────────────────────────────────────────────────────────

function parseSender(sender: string): { name: string; email: string } {
    const match = sender.match(/^(.+?)\s*<(.+?)>$/);
    if (match) return { name: match[1].trim().replace(/"/g, ''), email: match[2].trim() };
    if (sender.includes('@')) return { name: sender.split('@')[0], email: sender };
    return { name: sender, email: sender };
}

function MessageBubble({
    message,
}: {
    message: ThreadMessageDetail;
    expanded?: boolean;
    isLatest?: boolean;
}) {
    const [contactOpen, setContactOpen] = React.useState(false);
    const { name: senderName, email: senderEmail } = parseSender(message.sender);
    const initials = senderName.split(' ').filter(Boolean).map((w: string) => w[0]).join('').slice(0, 2).toUpperCase();

    const colors = ["bg-primary", "bg-copper", "bg-sage", "bg-teal", "bg-obsidian/60", "bg-burgundy"];
    const colorIndex = message.sender.split('').reduce((a: number, c: string) => a + c.charCodeAt(0), 0) % colors.length;

    return (
        <div className="rounded-[14px] border border-border/60 bg-background">
            <div className="flex items-center gap-3 p-3">
                <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-white text-[11px] font-bold shrink-0",
                    colors[colorIndex]
                )}>
                    {initials}
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setContactOpen(true)}
                            className="text-sm font-semibold font-inter truncate hover:underline decoration-primary/40 underline-offset-2 cursor-pointer text-left"
                        >
                            {senderName}
                        </button>
                        <button
                            type="button"
                            onClick={() => setContactOpen(true)}
                            className="p-0.5 rounded text-muted-foreground/40 hover:text-primary/70 transition-colors shrink-0"
                            aria-label="View contact"
                        >
                            <UserPlus size={12} />
                        </button>
                        <span className="text-[11px] text-muted-foreground/50 font-inter shrink-0">
                            {formatDistanceToNow(parseISO(message.received_at), { addSuffix: true })}
                        </span>
                    </div>
                </div>
            </div>
            <div className="px-3 pb-4 pt-0">
                <div className="pl-11">
                    <FormattedEmailBody body={message.body} />
                </div>
            </div>

            <ContactDialog
                open={contactOpen}
                onOpenChange={setContactOpen}
                senderEmail={senderEmail}
                senderDisplayName={senderName}
            />
        </div>
    );
}

// ─── FORMATTED EMAIL BODY ────────────────────────────────────────────────────

function FormattedEmailBody({ body }: { body: string }) {
    const normalizedBody = normalizeEmailBody(body);
    const lines = normalizedBody.split('\n');
    const elements: React.ReactElement[] = [];
    let inQuote = false;
    let quoteLines: string[] = [];
    let paragraphBuffer: string[] = [];

    const flushParagraph = () => {
        if (paragraphBuffer.length > 0) {
            const text = paragraphBuffer.join(' ').trim();
            if (text) {
                elements.push(
                    <p key={`p-${elements.length}`} className="text-sm text-foreground/85 leading-relaxed mb-2.5">
                        {text}
                    </p>
                );
            }
            paragraphBuffer = [];
        }
    };

    const flushQuote = () => {
        if (quoteLines.length > 0) {
            elements.push(
                <blockquote key={`q-${elements.length}`} className="border-l-2 border-muted-foreground/20 pl-3 py-1 mb-2.5 text-xs text-muted-foreground/60 leading-relaxed">
                    {quoteLines.join('\n')}
                </blockquote>
            );
            quoteLines = [];
        }
    };

    for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('>') || trimmed.match(/^On .+ wrote:$/)) {
            flushParagraph();
            if (!inQuote) inQuote = true;
            quoteLines.push(trimmed.replace(/^>\s?/, ''));
            continue;
        }

        if (inQuote) {
            flushQuote();
            inQuote = false;
        }

        if (!trimmed) {
            flushParagraph();
            continue;
        }

        if (trimmed === '--' || trimmed.match(/^(Best|Regards|Thanks|Cheers|Sent from|Get Outlook),?\s*$/i)) {
            flushParagraph();
            elements.push(
                <p key={`sig-${elements.length}`} className="text-xs text-muted-foreground/40 leading-relaxed mt-3 border-t border-border/30 pt-2">
                    {lines.slice(lines.indexOf(line)).filter(l => l.trim()).join('\n')}
                </p>
            );
            break;
        }

        paragraphBuffer.push(trimmed);
    }

    flushParagraph();
    flushQuote();

    if (elements.length === 0) {
        return <p className="text-sm text-muted-foreground/60 italic font-inter">No content</p>;
    }

    return <div>{elements}</div>;
}

function normalizeEmailBody(rawBody: string): string {
    const body = (rawBody || "").replace(/\r\n/g, "\n").trim();
    if (!body) return "";

    const looksLikeHtml = /<\/?[a-z][\s\S]*>/i.test(body);
    if (!looksLikeHtml) return body;

    const text = body
        .replace(/<style[\s\S]*?<\/style>/gi, " ")
        .replace(/<script[\s\S]*?<\/script>/gi, " ")
        .replace(/<head[\s\S]*?<\/head>/gi, " ")
        .replace(/<\s*br\s*\/?\s*>/gi, "\n")
        .replace(/<\/\s*(p|div|li|tr|h[1-6]|blockquote)\s*>/gi, "\n")
        .replace(/<\s*li[^>]*>/gi, "- ")
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/gi, " ")
        .replace(/&amp;/gi, "&")
        .replace(/&lt;/gi, "<")
        .replace(/&gt;/gi, ">")
        .replace(/&quot;/gi, '"')
        .replace(/&#39;/gi, "'")
        .replace(/\u00A0/g, " ")
        .replace(/[ \t]+\n/g, "\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim();

    return text || body;
}
