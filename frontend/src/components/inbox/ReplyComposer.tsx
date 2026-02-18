"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sendReply, generateDraftReply } from "@/services/messages";
import { useSettings } from "@/hooks/useSettings";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaText } from "@/components/ui/DonnaText";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Pen, Send, Loader2, X, ChevronDown, ChevronUp,
    CheckCircle2, AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

type ComposerState = "idle" | "drafting" | "composing" | "confirming" | "sending" | "sent" | "error";

interface ReplyComposerProps {
    messageId: number;
    originalSender: string;
    originalSubject: string;
    threadId?: string;
}

export function ReplyComposer({ messageId, originalSender, originalSubject, threadId }: ReplyComposerProps) {
    const queryClient = useQueryClient();
    const { settings } = useSettings();

    const [state, setState] = useState<ComposerState>("idle");
    const [to, setTo] = useState("");
    const [cc, setCc] = useState("");
    const [bcc, setBcc] = useState("");
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [showCcBcc, setShowCcBcc] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");

    // Extract sender email from "Name <email>" format
    const extractEmail = (sender: string) => {
        const match = sender.match(/<(.+?)>/);
        return match ? match[1] : sender.trim();
    };

    const draftMutation = useMutation({
        mutationFn: () => generateDraftReply(messageId),
        onSuccess: (res) => {
            setTo(extractEmail(originalSender));
            setSubject(`Re: ${originalSubject.replace(/^Re:\s*/i, "")}`);
            setBody(res.draft);
            setState("composing");
        },
        onError: () => {
            setErrorMessage("Failed to generate draft. Try again.");
            setState("error");
        },
    });

    const sendMutation = useMutation({
        mutationFn: () => {
            const ccList = cc.split(",").map(s => s.trim()).filter(Boolean);
            const bccList = bcc.split(",").map(s => s.trim()).filter(Boolean);
            return sendReply(messageId, {
                body,
                to,
                subject,
                cc: ccList.length > 0 ? ccList : undefined,
                bcc: bccList.length > 0 ? bccList : undefined,
            });
        },
        onSuccess: (res) => {
            if (res.sent) {
                setState("sent");
                // Refresh thread detail to clear needs_reply
                if (threadId) {
                    queryClient.invalidateQueries({ queryKey: ["thread-detail", threadId] });
                }
                queryClient.invalidateQueries({ queryKey: ["messages"] });
                // Auto-reset after brief success indicator
                setTimeout(() => setState("idle"), 3000);
            } else {
                setErrorMessage(res.error || "Failed to send. Please try again.");
                setState("error");
            }
        },
        onError: (err) => {
            setErrorMessage(err instanceof Error ? err.message : "Network error. Please try again.");
            setState("error");
        },
    });

    const handleDraftReply = () => {
        setState("drafting");
        draftMutation.mutate();
    };

    const handleSendClick = () => {
        if (!to.trim() || !body.trim()) return;
        setState("confirming");
    };

    const handleConfirmSend = () => {
        setState("sending");
        sendMutation.mutate();
    };

    const handleDiscard = () => {
        setState("idle");
        setTo("");
        setCc("");
        setBcc("");
        setSubject("");
        setBody("");
        setShowCcBcc(false);
        setErrorMessage("");
    };

    const fromEmail = settings?.user_email || "your-email@gmail.com";

    // Idle state — just the Draft Reply button
    if (state === "idle") {
        return (
            <DonnaButton
                size="sm"
                className="gap-2 bg-auburn hover:bg-auburn/90 text-white"
                onClick={handleDraftReply}
            >
                <Pen size={14} />
                Draft Reply
            </DonnaButton>
        );
    }

    // Drafting state — loading indicator
    if (state === "drafting") {
        return (
            <DonnaButton size="sm" className="gap-2 bg-auburn text-white" disabled>
                <Loader2 size={14} className="animate-spin" />
                Drafting...
            </DonnaButton>
        );
    }

    // Sent state — success indicator
    if (state === "sent") {
        return (
            <div className="flex items-center gap-2 p-3 rounded-xl border border-sage/30 bg-sage/5 animate-in fade-in duration-300">
                <CheckCircle2 size={16} className="text-sage" />
                <DonnaText variant="body" className="text-sage text-sm font-medium">
                    Reply sent successfully
                </DonnaText>
            </div>
        );
    }

    // Composing / Error state — full compose form
    const isDisabled = state === "sending";

    return (
        <>
            <div className="rounded-xl border border-auburn/20 bg-background overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-2.5 bg-auburn/5 border-b border-auburn/10">
                    <DonnaText variant="label" className="text-[10px] text-auburn uppercase tracking-[0.2em] font-bold">
                        Compose Reply
                    </DonnaText>
                    <button
                        onClick={handleDiscard}
                        className="text-muted-foreground/50 hover:text-foreground transition-colors"
                        disabled={isDisabled}
                    >
                        <X size={14} />
                    </button>
                </div>

                <div className="px-4 py-3 space-y-2.5">
                    {/* From */}
                    <div className="flex items-center gap-3 text-sm">
                        <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium">From</span>
                        <span className="text-foreground/70 text-xs">{fromEmail}</span>
                    </div>

                    {/* To */}
                    <div className="flex items-center gap-3">
                        <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium">To</span>
                        <Input
                            value={to}
                            onChange={(e) => setTo(e.target.value)}
                            className="h-7 text-xs border-border/40 focus-visible:ring-auburn/30"
                            disabled={isDisabled}
                        />
                        {!showCcBcc && (
                            <button
                                onClick={() => setShowCcBcc(true)}
                                className="text-[10px] text-auburn hover:text-auburn/80 font-medium whitespace-nowrap"
                                disabled={isDisabled}
                            >
                                CC BCC
                            </button>
                        )}
                    </div>

                    {/* CC / BCC */}
                    {showCcBcc && (
                        <>
                            <div className="flex items-center gap-3 animate-in fade-in slide-in-from-top-1 duration-200">
                                <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium">CC</span>
                                <Input
                                    value={cc}
                                    onChange={(e) => setCc(e.target.value)}
                                    placeholder="comma-separated"
                                    className="h-7 text-xs border-border/40 focus-visible:ring-auburn/30"
                                    disabled={isDisabled}
                                />
                            </div>
                            <div className="flex items-center gap-3 animate-in fade-in slide-in-from-top-1 duration-200">
                                <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium">BCC</span>
                                <Input
                                    value={bcc}
                                    onChange={(e) => setBcc(e.target.value)}
                                    placeholder="comma-separated"
                                    className="h-7 text-xs border-border/40 focus-visible:ring-auburn/30"
                                    disabled={isDisabled}
                                />
                            </div>
                        </>
                    )}

                    {/* Subject */}
                    <div className="flex items-center gap-3">
                        <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium">Subj</span>
                        <Input
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            className="h-7 text-xs border-border/40 focus-visible:ring-auburn/30"
                            disabled={isDisabled}
                        />
                    </div>

                    {/* Separator */}
                    <div className="h-px bg-border/40" />

                    {/* Body */}
                    <Textarea
                        value={body}
                        onChange={(e) => setBody(e.target.value)}
                        rows={8}
                        className="text-sm leading-relaxed border-border/40 focus-visible:ring-auburn/30 resize-none"
                        disabled={isDisabled}
                    />

                    {/* Error inline */}
                    {state === "error" && errorMessage && (
                        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20 animate-in fade-in duration-200">
                            <AlertCircle size={14} className="text-destructive shrink-0" />
                            <span className="text-xs text-destructive">{errorMessage}</span>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center justify-between pt-1">
                        <DonnaButton
                            variant="ghost"
                            size="sm"
                            className="text-muted-foreground hover:text-foreground text-xs"
                            onClick={handleDiscard}
                            disabled={isDisabled}
                        >
                            Discard
                        </DonnaButton>

                        <DonnaButton
                            size="sm"
                            className="gap-2 bg-auburn hover:bg-auburn/90 text-white"
                            onClick={handleSendClick}
                            disabled={isDisabled || !to.trim() || !body.trim()}
                        >
                            {state === "sending" ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Send size={14} />
                            )}
                            {state === "sending" ? "Sending..." : "Send"}
                        </DonnaButton>
                    </div>
                </div>
            </div>

            {/* Confirmation Dialog */}
            <Dialog open={state === "confirming"} onOpenChange={(open) => !open && setState("composing")}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Send Reply</DialogTitle>
                        <DialogDescription>
                            Send this reply to <strong>{to}</strong>?
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2">
                        <DonnaButton
                            variant="outline"
                            onClick={() => setState("composing")}
                        >
                            Cancel
                        </DonnaButton>
                        <DonnaButton
                            className="bg-auburn hover:bg-auburn/90 text-white gap-2"
                            onClick={handleConfirmSend}
                        >
                            <Send size={14} />
                            Send
                        </DonnaButton>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
