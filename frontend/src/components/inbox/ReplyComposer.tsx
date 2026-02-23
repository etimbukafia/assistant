"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sendReply, generateDraftReply } from "@/services/messages";
import { useSettings } from "@/hooks/useSettings";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Pen, Send, Loader2, X, CheckCircle2, AlertCircle } from "lucide-react";
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

    const [state, setState]           = useState<ComposerState>("idle");
    const [to, setTo]                 = useState("");
    const [cc, setCc]                 = useState("");
    const [bcc, setBcc]               = useState("");
    const [subject, setSubject]       = useState("");
    const [body, setBody]             = useState("");
    const [showCcBcc, setShowCcBcc]   = useState(false);
    const [errorMessage, setErrorMessage] = useState("");

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
            const ccList  = cc.split(",").map((s) => s.trim()).filter(Boolean);
            const bccList = bcc.split(",").map((s) => s.trim()).filter(Boolean);
            return sendReply(messageId, {
                body,
                to,
                subject,
                cc:  ccList.length  > 0 ? ccList  : undefined,
                bcc: bccList.length > 0 ? bccList : undefined,
            });
        },
        onSuccess: (res) => {
            if (res.sent) {
                setState("sent");
                if (threadId) {
                    queryClient.invalidateQueries({ queryKey: ["thread-detail", threadId] });
                }
                queryClient.invalidateQueries({ queryKey: ["messages"] });
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

    const handleDraftReply  = () => { setState("drafting"); draftMutation.mutate(); };
    const handleSendClick   = () => { if (!to.trim() || !body.trim()) return; setState("confirming"); };
    const handleConfirmSend = () => { setState("sending"); sendMutation.mutate(); };

    const handleDiscard = () => {
        setState("idle");
        setTo(""); setCc(""); setBcc(""); setSubject(""); setBody("");
        setShowCcBcc(false);
        setErrorMessage("");
    };

    const fromEmail  = settings?.user_email || "your-email@gmail.com";
    const isDisabled = state === "sending";

    // ── Idle ──────────────────────────────────────────────────────────────────
    if (state === "idle") {
        return (
            <button
                type="button"
                onClick={handleDraftReply}
                className="h-8 px-3 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-medium font-inter flex items-center gap-1.5 transition-colors"
            >
                <Pen size={13} />
                Draft Reply
            </button>
        );
    }

    // ── Drafting ──────────────────────────────────────────────────────────────
    if (state === "drafting") {
        return (
            <button
                type="button"
                disabled
                className="h-8 px-3 rounded-lg bg-primary text-white text-xs font-medium font-inter flex items-center gap-1.5 opacity-70"
            >
                <Loader2 size={13} className="animate-spin" />
                Drafting…
            </button>
        );
    }

    // ── Sent ──────────────────────────────────────────────────────────────────
    if (state === "sent") {
        return (
            <div className="flex items-center gap-2 p-3 rounded-xl border border-sage/30 bg-sage/5 animate-in fade-in duration-300">
                <CheckCircle2 size={15} className="text-sage" />
                <span className="text-sm font-medium font-inter text-sage">Reply sent successfully</span>
            </div>
        );
    }

    // ── Composing / Error ─────────────────────────────────────────────────────
    return (
        <>
            <div className="rounded-xl border border-primary/20 bg-background overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-2.5 bg-primary/[0.04] border-b border-primary/10">
                    <p className="text-[10px] font-bold uppercase tracking-[1.2px] text-primary font-inter">
                        Compose Reply
                    </p>
                    <button
                        type="button"
                        onClick={handleDiscard}
                        disabled={isDisabled}
                        className="text-muted-foreground/50 hover:text-foreground transition-colors"
                    >
                        <X size={14} />
                    </button>
                </div>

                <div className="px-4 py-3 space-y-2.5">
                    {/* From */}
                    <div className="flex items-center gap-3 text-sm">
                        <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium font-inter">From</span>
                        <span className="text-foreground/70 text-xs font-inter">{fromEmail}</span>
                    </div>

                    {/* To */}
                    <div className="flex items-center gap-3">
                        <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium font-inter">To</span>
                        <Input
                            value={to}
                            onChange={(e) => setTo(e.target.value)}
                            className="h-7 text-xs border-border/40 focus-visible:ring-primary/30"
                            disabled={isDisabled}
                        />
                        {!showCcBcc && (
                            <button
                                type="button"
                                onClick={() => setShowCcBcc(true)}
                                disabled={isDisabled}
                                className="text-[10px] text-primary hover:text-primary/80 font-medium font-inter whitespace-nowrap transition-colors"
                            >
                                CC BCC
                            </button>
                        )}
                    </div>

                    {/* CC / BCC */}
                    {showCcBcc && (
                        <>
                            <div className="flex items-center gap-3 animate-in fade-in slide-in-from-top-1 duration-200">
                                <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium font-inter">CC</span>
                                <Input
                                    value={cc}
                                    onChange={(e) => setCc(e.target.value)}
                                    placeholder="comma-separated"
                                    className="h-7 text-xs border-border/40 focus-visible:ring-primary/30"
                                    disabled={isDisabled}
                                />
                            </div>
                            <div className="flex items-center gap-3 animate-in fade-in slide-in-from-top-1 duration-200">
                                <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium font-inter">BCC</span>
                                <Input
                                    value={bcc}
                                    onChange={(e) => setBcc(e.target.value)}
                                    placeholder="comma-separated"
                                    className="h-7 text-xs border-border/40 focus-visible:ring-primary/30"
                                    disabled={isDisabled}
                                />
                            </div>
                        </>
                    )}

                    {/* Subject */}
                    <div className="flex items-center gap-3">
                        <span className="text-muted-foreground/60 w-12 text-right text-xs font-medium font-inter">Subj</span>
                        <Input
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            className="h-7 text-xs border-border/40 focus-visible:ring-primary/30"
                            disabled={isDisabled}
                        />
                    </div>

                    <div className="h-px bg-border/40" />

                    {/* Body */}
                    <Textarea
                        value={body}
                        onChange={(e) => setBody(e.target.value)}
                        rows={8}
                        className="text-sm leading-relaxed border-border/40 focus-visible:ring-primary/30 resize-none font-inter"
                        disabled={isDisabled}
                    />

                    {/* Error */}
                    {state === "error" && errorMessage && (
                        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20 animate-in fade-in duration-200">
                            <AlertCircle size={14} className="text-destructive shrink-0" />
                            <span className="text-xs text-destructive font-inter">{errorMessage}</span>
                        </div>
                    )}

                    {/* Footer actions */}
                    <div className="flex items-center justify-between pt-1">
                        <button
                            type="button"
                            onClick={handleDiscard}
                            disabled={isDisabled}
                            className="h-8 px-3 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors font-inter disabled:opacity-40"
                        >
                            Discard
                        </button>

                        <button
                            type="button"
                            onClick={handleSendClick}
                            disabled={isDisabled || !to.trim() || !body.trim()}
                            className="h-8 px-3 rounded-lg bg-primary hover:bg-primary/90 text-white text-xs font-medium font-inter flex items-center gap-1.5 transition-colors disabled:opacity-40"
                        >
                            {state === "sending" ? (
                                <Loader2 size={13} className="animate-spin" />
                            ) : (
                                <Send size={13} />
                            )}
                            {state === "sending" ? "Sending…" : "Send"}
                        </button>
                    </div>
                </div>
            </div>

            {/* Confirmation dialog */}
            <Dialog open={state === "confirming"} onOpenChange={(open) => !open && setState("composing")}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle className="font-playfair text-[18px]">Send Reply</DialogTitle>
                        <DialogDescription className="text-[13px] font-inter">
                            Send this reply to <strong>{to}</strong>?
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2">
                        <button
                            type="button"
                            onClick={() => setState("composing")}
                            className="h-9 px-4 rounded-lg text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors font-inter"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={handleConfirmSend}
                            className="h-9 px-4 rounded-lg bg-primary hover:bg-primary/90 text-white text-[13px] font-medium font-inter flex items-center gap-1.5 transition-colors"
                        >
                            <Send size={14} />
                            Send
                        </button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
