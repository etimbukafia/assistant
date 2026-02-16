"use client";

import * as React from "react";
import { Loader2, Send, Sparkles, Check, X, FileWarning, Plus, PanelRightOpen, PanelRightClose } from "lucide-react";
import { toast } from "sonner";

import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaText } from "@/components/ui/DonnaText";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ActionBubble } from "@/components/chat/ActionBubble";
import { trackUIEvent } from "@/services/telemetry";
import { useChat, useChatMessages, useChatSessions } from "@/hooks/useChat";
import { useVaultMutations, useVaultProposals } from "@/hooks/useVault";
import { useMentionComposer } from "@/hooks/useMentionComposer";

type WorkspaceTab = "chat" | "knowledge";

type ResolvedMentionContext = {
    contacts?: Array<{ email?: string; label?: string }>;
    emails?: Array<{ message_id?: number; subject?: string; sender?: string }>;
    knowledge?: Array<{ note_id?: number; slug?: string; title?: string; note_type?: string }>;
};

const ACTION_CHIPS = [
    {
        id: "draft_email",
        label: "Draft an email",
        prompt: "Draft a reply to @contacts/[name] about @email/[subject (contact email)].",
    },
    {
        id: "prep_meeting",
        label: "Prep a meeting",
        prompt: "Prep me for my meeting with @contacts/[name] on [date/time].",
    },
    {
        id: "work_doc",
        label: "Work on a document",
        prompt: "Create a brief on [topic] for [audience] with key risks and decisions.",
    },
    {
        id: "organize_files",
        label: "Organize files",
        prompt: "Propose a folder and naming structure for [project], then list file moves.",
    },
    {
        id: "create_presentation",
        label: "Create a presentation",
        prompt: "Build a slide outline for [topic] with milestones, decisions, and open questions.",
    },
];

export default function ChatWorkspacePage() {
    const [tab, setTab] = React.useState<WorkspaceTab>("chat");
    const [contextDrawerOpen, setContextDrawerOpen] = React.useState(true);
    const [inputValue, setInputValue] = React.useState("");
    const [selectedProposalIds, setSelectedProposalIds] = React.useState<Set<number>>(new Set());

    const inputRef = React.useRef<HTMLInputElement>(null);
    const scrollRef = React.useRef<HTMLDivElement>(null);

    const {
        currentSessionId,
        setCurrentSessionId,
        sendMessage,
        createSession,
        approveAction,
        rejectAction,
        isSending,
        isCreating,
        isApproving,
        isRejecting,
    } = useChat();
    const { data: sessionList } = useChatSessions({ limit: 20, offset: 0, enabled: true });
    const { data: messages, pendingActions } = useChatMessages(currentSessionId);

    const { data: pendingProposals, isLoading: proposalsLoading } = useVaultProposals("pending");
    const vaultMutations = useVaultMutations();

    const latestUserContext = React.useMemo(() => {
        const reversed = [...(messages || [])].reverse();
        for (const msg of reversed) {
            if (msg.role !== "user") continue;
            const meta = (msg.metadata || {}) as Record<string, unknown>;
            const resolved = meta["resolved_mentions"];
            if (resolved && typeof resolved === "object") {
                return resolved as ResolvedMentionContext;
            }
        }
        return null;
    }, [messages]);

    React.useEffect(() => {
        if (!currentSessionId && sessionList?.sessions?.length) {
            setCurrentSessionId(sessionList.sessions[0].id);
        }
    }, [currentSessionId, sessionList?.sessions, setCurrentSessionId]);

    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages, pendingActions, isSending]);
    const {
        listboxId,
        mentionContext,
        mentionSuggestions,
        activeSuggestionIndex,
        loadingSuggestions,
        parseMentions,
        onInputChange,
        onInputKeyDown,
        applySuggestion,
        clearMentionState,
    } = useMentionComposer({
        inputValue,
        setInputValue,
        inputRef,
        onMentionSelected: (mention) => {
            trackUIEvent("mention_selected", { mention_type: mention.type });
        },
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputValue.trim() || isSending || isCreating) return;
        const content = inputValue.trim();
        const mentions = parseMentions(content);
        setInputValue("");
        clearMentionState();
        try {
            if (!currentSessionId) {
                const session = await createSession({ mode: "action" });
                await sendMessage({ session_id: session.id, content, mode: "action", mentions });
                trackUIEvent("chat_message_sent", {
                    has_mentions: mentions.length > 0,
                    mention_count: mentions.length,
                    source: "dashboard_chat",
                });
            } else {
                await sendMessage({ session_id: currentSessionId, content, mode: "action", mentions });
                trackUIEvent("chat_message_sent", {
                    has_mentions: mentions.length > 0,
                    mention_count: mentions.length,
                    source: "dashboard_chat",
                });
            }
        } catch {
            toast.error("Failed to send message");
            setInputValue(content);
        }
    };

    const insertPrompt = (prompt: string) => {
        trackUIEvent("chat_chip_clicked", { prompt });
        setInputValue(prompt);
        requestAnimationFrame(() => {
            inputRef.current?.focus();
            const start = prompt.indexOf("[");
            const caret = start >= 0 ? start + 1 : prompt.length;
            inputRef.current?.setSelectionRange(caret, caret);
        });
    };

    const toggleProposalSelection = (id: number, checked: boolean) => {
        setSelectedProposalIds((prev) => {
            const next = new Set(prev);
            if (checked) next.add(id);
            else next.delete(id);
            return next;
        });
    };

    const handleBulkApprove = async () => {
        const ids = Array.from(selectedProposalIds);
        if (!ids.length) return;
        try {
            await vaultMutations.bulkApprove.mutateAsync(ids);
            trackUIEvent("proposal_bulk_approved", { count: ids.length, proposal_ids: ids });
            setSelectedProposalIds(new Set());
            toast.success(`Approved ${ids.length} proposal${ids.length === 1 ? "" : "s"}`);
        } catch {
            toast.error("Bulk approve failed");
        }
    };

    return (
        <div className={`grid grid-cols-1 gap-5 min-h-[calc(100vh-10rem)] ${
            contextDrawerOpen ? "xl:grid-cols-[260px_1fr_280px] lg:grid-cols-[260px_1fr]" : "lg:grid-cols-[260px_1fr]"
        }`}>
            <aside className="rounded-xl border border-border/60 bg-white/70 p-4">
                <div className="flex items-center justify-between mb-4">
                    <DonnaText variant="h4" className="text-auburn">Workspace</DonnaText>
                    <DonnaButton
                        aria-label="Start new chat"
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={async () => {
                            try {
                                const session = await createSession({ mode: "action" });
                                setCurrentSessionId(session.id);
                                setTab("chat");
                            } catch {
                                toast.error("Could not start a new chat");
                            }
                        }}
                    >
                        <Plus size={16} />
                    </DonnaButton>
                </div>
                <div className="flex gap-2 mb-4">
                    <DonnaButton
                        aria-label="Show chat workspace"
                        variant={tab === "chat" ? "secondary" : "ghost"}
                        className="flex-1"
                        onClick={() => setTab("chat")}
                    >
                        Chat
                    </DonnaButton>
                    <DonnaButton
                        aria-label="Show knowledge workspace"
                        variant={tab === "knowledge" ? "secondary" : "ghost"}
                        className="flex-1"
                        onClick={() => setTab("knowledge")}
                    >
                        Knowledge
                    </DonnaButton>
                </div>
                <DonnaText variant="caption" className="text-muted-foreground uppercase tracking-wide">Recent chats</DonnaText>
                <div className="mt-2 space-y-2">
                    {sessionList?.sessions?.slice(0, 12).map((session) => (
                        <button
                            key={session.id}
                            aria-label={`Open chat session ${session.title || "Untitled chat"}`}
                            className={`w-full text-left rounded-md px-3 py-2 text-sm transition ${
                                currentSessionId === session.id ? "bg-auburn text-white" : "hover:bg-linen"
                            }`}
                            onClick={() => {
                                setCurrentSessionId(session.id);
                                setTab("chat");
                            }}
                        >
                            {session.title || "Untitled chat"}
                        </button>
                    ))}
                </div>
            </aside>

            <section className="rounded-xl border border-border/60 bg-white/80 flex flex-col min-h-[calc(100vh-10rem)]">
                {tab === "chat" ? (
                    <>
                        <div className="px-6 py-4 border-b border-border/50">
                            <div className="flex items-center justify-between">
                                <DonnaText variant="h3" className="text-auburn">What needs to move today?</DonnaText>
                                <DonnaButton
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="gap-2"
                                    onClick={() => setContextDrawerOpen((v) => !v)}
                                    aria-label={contextDrawerOpen ? "Hide context drawer" : "Show context drawer"}
                                >
                                    {contextDrawerOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
                                    Context
                                </DonnaButton>
                            </div>
                        </div>

                        <ScrollArea className="flex-1 px-6 py-5 bg-linen/30">
                            <div className="flex flex-col gap-4 min-h-full">
                                {(!messages || messages.length === 0) && (
                                    <div className="flex flex-col items-center justify-center flex-1 mt-20 opacity-70">
                                        <Sparkles size={36} className="text-copper mb-3" />
                                        <DonnaText variant="h4" className="text-muted-foreground">
                                            Start with an action chip or ask directly.
                                        </DonnaText>
                                    </div>
                                )}
                                {messages?.map((msg) => {
                                    const action = pendingActions?.find((a) => a.message_id === Number(msg.id));
                                    return (
                                        <div key={msg.id} className="flex flex-col">
                                            <MessageBubble role={msg.role} content={msg.content} timestamp={msg.created_at} />
                                            {action && currentSessionId && (
                                            <ActionBubble
                                                action={action}
                                                onApprove={async (id) => {
                                                    await approveAction({ sessionId: currentSessionId, actionId: id });
                                                    trackUIEvent("chat_action_approved", {
                                                        action_id: id,
                                                        source: "dashboard_chat",
                                                    });
                                                }}
                                                onReject={(id) => rejectAction({ sessionId: currentSessionId, actionId: id })}
                                                isApproving={isApproving}
                                                isRejecting={isRejecting}
                                                />
                                            )}
                                        </div>
                                    );
                                })}
                                {(isSending || isCreating) && (
                                    <div className="flex justify-start mb-2">
                                        <div className="bg-white border border-border/40 rounded-2xl rounded-tl-sm p-3 shadow-sm flex items-center gap-2">
                                            <Loader2 className="h-4 w-4 animate-spin text-auburn" />
                                            <span className="text-sm text-muted-foreground">Teeks is thinking...</span>
                                        </div>
                                    </div>
                                )}
                                <div ref={scrollRef} />
                            </div>
                        </ScrollArea>

                        <div className="p-4 border-t border-border/50 bg-white">
                            <div className="flex flex-wrap gap-2 mb-3">
                                {ACTION_CHIPS.map((chip) => (
                                    <button
                                        key={chip.id}
                                        aria-label={`Insert prompt: ${chip.label}`}
                                        type="button"
                                        className="rounded-full border border-border/60 bg-linen/40 hover:bg-linen px-3 py-1.5 text-sm transition"
                                        onClick={() => insertPrompt(chip.prompt)}
                                    >
                                        {chip.label}
                                    </button>
                                ))}
                            </div>
                            <form className="flex gap-2" onSubmit={handleSubmit}>
                                <div className="relative flex-1">
                                    <Input
                                        ref={inputRef}
                                        aria-label="Chat message input"
                                        value={inputValue}
                                        role="combobox"
                                        aria-autocomplete="list"
                                        aria-expanded={Boolean(mentionContext || loadingSuggestions)}
                                        aria-controls={listboxId}
                                        aria-activedescendant={mentionSuggestions[activeSuggestionIndex] ? `${listboxId}-option-${activeSuggestionIndex}` : undefined}
                                        placeholder="Type your message..."
                                        className="bg-linen border-border focus-visible:ring-auburn/20"
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            const cursor = e.target.selectionStart ?? value.length;
                                            onInputChange(value, cursor);
                                        }}
                                        onKeyDown={onInputKeyDown}
                                        disabled={isSending || isCreating}
                                    />
                                    {(mentionContext || loadingSuggestions) && (
                                        <div id={listboxId} role="listbox" className="absolute left-0 right-0 top-full z-40 mt-1 rounded-md border border-border/60 bg-white shadow-md">
                                            {loadingSuggestions ? (
                                                <div className="px-3 py-2 text-xs text-muted-foreground" aria-live="polite">Loading mentions...</div>
                                            ) : mentionSuggestions.length > 0 ? (
                                                mentionSuggestions.map((suggestion, index) => (
                                                    <button
                                                        key={suggestion.key}
                                                        id={`${listboxId}-option-${index}`}
                                                        type="button"
                                                        role="option"
                                                        aria-selected={index === activeSuggestionIndex}
                                                        className={`w-full px-3 py-2 text-left text-xs hover:bg-linen ${
                                                            index === activeSuggestionIndex ? "bg-linen ring-1 ring-auburn/30" : ""
                                                        }`}
                                                        onMouseDown={(evt) => {
                                                            evt.preventDefault();
                                                            applySuggestion(suggestion);
                                                        }}
                                                    >
                                                        {suggestion.display}
                                                    </button>
                                                ))
                                            ) : (
                                                <div className="px-3 py-2 text-xs text-muted-foreground" aria-live="polite">No matches</div>
                                            )}
                                        </div>
                                    )}
                                </div>
                                <DonnaButton type="submit" size="icon" variant="secondary" disabled={!inputValue.trim() || isSending || isCreating}>
                                    {isSending || isCreating ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                                </DonnaButton>
                            </form>
                        </div>
                    </>
                ) : (
                    <div className="p-6 flex-1">
                        <div className="flex items-start justify-between mb-4">
                            <div>
                                <DonnaText variant="h3" className="text-auburn">Proposals Inbox</DonnaText>
                                <DonnaText variant="body" className="text-muted-foreground">Review and approve updates to your knowledge graph.</DonnaText>
                            </div>
                            <DonnaButton
                                aria-label="Approve selected proposals"
                                variant="secondary"
                                onClick={handleBulkApprove}
                                disabled={!selectedProposalIds.size || vaultMutations.bulkApprove.isPending}
                            >
                                {vaultMutations.bulkApprove.isPending ? <Loader2 size={16} className="animate-spin mr-2" /> : <Check size={16} className="mr-2" />}
                                Approve Selected
                            </DonnaButton>
                        </div>

                        {proposalsLoading ? (
                            <div className="h-48 flex items-center justify-center">
                                <Loader2 className="h-6 w-6 animate-spin text-auburn" />
                            </div>
                        ) : pendingProposals?.proposals?.length ? (
                            <div className="space-y-3">
                                {pendingProposals.proposals.map((proposal) => (
                                    <div key={proposal.id} className="rounded-lg border border-border/60 p-4 bg-linen/20">
                                        <div className="flex items-start justify-between gap-4">
                                            <div>
                                                <DonnaText variant="h4">{proposal.diff_summary || "Proposed vault update"}</DonnaText>
                                                <DonnaText variant="caption" className="text-muted-foreground">
                                                    Type: {proposal.proposal_type} | Confidence: {Math.round((proposal.confidence || 0) * 100)}%
                                                </DonnaText>
                                            </div>
                                            <input
                                                aria-label={`Select proposal ${proposal.id} for bulk approve`}
                                                type="checkbox"
                                                className="mt-1 h-4 w-4"
                                                checked={selectedProposalIds.has(proposal.id)}
                                                onChange={(e) => toggleProposalSelection(proposal.id, e.target.checked)}
                                            />
                                        </div>
                                        <div className="flex gap-2 mt-3">
                                            <DonnaButton
                                                variant="secondary"
                                                size="sm"
                                                disabled={vaultMutations.approveProposal.isPending}
                                                onClick={async () => {
                                                    try {
                                                        await vaultMutations.approveProposal.mutateAsync(proposal.id);
                                                        trackUIEvent("proposal_approved", { proposal_id: proposal.id });
                                                        toast.success("Proposal approved");
                                                    } catch {
                                                        toast.error("Could not approve proposal");
                                                    }
                                                }}
                                            >
                                                <Check size={14} className="mr-1" /> Approve
                                            </DonnaButton>
                                            <DonnaButton
                                                variant="ghost"
                                                size="sm"
                                                disabled={vaultMutations.rejectProposal.isPending}
                                                onClick={async () => {
                                                    try {
                                                        await vaultMutations.rejectProposal.mutateAsync({
                                                            id: proposal.id,
                                                            payload: { category: "not_relevant", reason: "Rejected from chat workspace" },
                                                        });
                                                        trackUIEvent("proposal_rejected", { proposal_id: proposal.id, category: "not_relevant" });
                                                        toast.success("Proposal rejected");
                                                    } catch {
                                                        toast.error("Could not reject proposal");
                                                    }
                                                }}
                                            >
                                                <X size={14} className="mr-1" /> Reject
                                            </DonnaButton>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="h-56 border border-dashed border-border/70 rounded-xl flex flex-col items-center justify-center text-center">
                                <FileWarning className="h-8 w-8 text-muted-foreground mb-2" />
                                <DonnaText variant="h4">No pending proposals</DonnaText>
                                <DonnaText variant="body" className="text-muted-foreground">New memory suggestions will appear here for review.</DonnaText>
                            </div>
                        )}
                    </div>
                )}
            </section>

            {contextDrawerOpen && (
                <aside className="hidden xl:flex flex-col rounded-xl border border-border/60 bg-white/80 p-4">
                    <DonnaText variant="h4" className="text-auburn mb-3">Context Used</DonnaText>
                    <DonnaText variant="caption" className="text-muted-foreground mb-4">
                        Latest context packet from your most recent user message.
                    </DonnaText>

                    <div className="space-y-4 overflow-y-auto">
                        <section>
                            <DonnaText variant="label" className="uppercase tracking-wide text-muted-foreground">Contacts</DonnaText>
                            <div className="mt-1 space-y-1">
                                {(latestUserContext?.contacts || []).length ? (
                                    latestUserContext?.contacts?.map((c, idx) => (
                                        <div key={`contact-${idx}`} className="text-sm rounded bg-linen/50 px-2 py-1">
                                            {c.label || c.email || "Unknown contact"}
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-xs text-muted-foreground">No contact context</div>
                                )}
                            </div>
                        </section>

                        <section>
                            <DonnaText variant="label" className="uppercase tracking-wide text-muted-foreground">Emails</DonnaText>
                            <div className="mt-1 space-y-1">
                                {(latestUserContext?.emails || []).length ? (
                                    latestUserContext?.emails?.map((e, idx) => (
                                        <div key={`email-${idx}`} className="text-sm rounded bg-linen/50 px-2 py-1">
                                            {e.subject || "Untitled"} {e.sender ? `(${e.sender})` : ""}
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-xs text-muted-foreground">No email context</div>
                                )}
                            </div>
                        </section>

                        <section>
                            <DonnaText variant="label" className="uppercase tracking-wide text-muted-foreground">Knowledge Notes</DonnaText>
                            <div className="mt-1 space-y-1">
                                {(latestUserContext?.knowledge || []).length ? (
                                    latestUserContext?.knowledge?.map((n, idx) => (
                                        <div key={`note-${idx}`} className="text-sm rounded bg-linen/50 px-2 py-1">
                                            {n.title || n.slug || "Untitled note"}
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-xs text-muted-foreground">No knowledge context</div>
                                )}
                            </div>
                        </section>

                        <section>
                            <DonnaText variant="label" className="uppercase tracking-wide text-muted-foreground">Pending Actions</DonnaText>
                            <div className="mt-1 text-sm rounded bg-linen/50 px-2 py-1">
                                {(pendingActions || []).length} pending
                            </div>
                        </section>

                        <section>
                            <DonnaText variant="label" className="uppercase tracking-wide text-muted-foreground">Proposal Queue</DonnaText>
                            <div className="mt-1 text-sm rounded bg-linen/50 px-2 py-1">
                                {pendingProposals?.total || 0} pending proposals
                            </div>
                        </section>
                    </div>
                </aside>
            )}
        </div>
    );
}
