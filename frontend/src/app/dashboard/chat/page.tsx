"use client";

import * as React from "react";
import { ArrowUp, Check, Plus, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { ActionBubble } from "@/components/chat/ActionBubble";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useChat, useChatActionChips, useChatMessages, useChatSessions } from "@/hooks/useChat";
import { useMentionComposer } from "@/hooks/useMentionComposer";
import { cn } from "@/lib/utils";
import { chatService, type ChatMention, type MentionSuggestion as ApiMentionSuggestion } from "@/services/chat";
import { trackUIEvent } from "@/services/telemetry";

const SESSIONS_QUERY_KEY = ["chat", "sessions", { limit: 20, offset: 0 }] as const;
type SessionsCache = { sessions: Array<{ id: string; title?: string | null }> };

const FALLBACK_ACTION_CHIPS = [
    { id: "fallback_1", label: "Draft quick update to a contact", prompt: "Draft a concise update email I can send now." },
    { id: "fallback_2", label: "Prep me for a meeting", prompt: "Prep me for my next meeting: agenda, risks, decisions, and talking points." },
    { id: "fallback_3", label: "Turn notes into a brief", prompt: "Turn this into a one-page brief with decisions, commitments, and open questions." },
    { id: "fallback_4", label: "What changed since yesterday?", prompt: "What changed since yesterday? Keep it tight and action-oriented." },
    { id: "fallback_5", label: "Extract commitments", prompt: "Extract commitments and owners from recent messages, then suggest next actions." },
];

type ActionChip = { id: string; label: string; prompt: string };
type PaneTab = "all" | "entities" | "remember";
type PaneSource = "entity" | "memory";

type ReferencePaneItem = {
    id: string;
    source: PaneSource;
    mention: ChatMention;
    title: string;
    subtitle?: string;
    kindLabel: string;
    dateLabel?: string;
    searchText?: string;
    updatedAt?: string;
};

const CARD_SHADOW = "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)";

function mentionKey(mention: ChatMention): string {
    return `${mention.kind}:${mention.ref}`;
}

function formatMentionDate(value?: string): string {
    if (!value) return "";
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return "";
    return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function normalizeKindLabel(kind: string): string {
    const value = (kind || "").trim().toLowerCase();
    if (!value) return "reference";
    return value === "memory" ? "remember" : value;
}

function toReferencePaneItem(item: ApiMentionSuggestion, source: PaneSource): ReferencePaneItem {
    const displayLabel = (item.display_label || item.label || "").trim() || item.ref;
    const isMemory = source === "memory" || item.kind === "memory";
    const mentionKind: ChatMention["kind"] = isMemory ? "memory" : (item.kind as ChatMention["kind"]);
    const updatedAt = item.updated_at || item.last_seen_at || item.created_at || "";
    const tinySearchText = (item.search_text || "").trim();
    return {
        id: `${source}:${mentionKind}:${item.ref}`,
        source,
        mention: {
            kind: mentionKind,
            ref: item.ref,
            label: displayLabel,
            metadata: {
                kind: mentionKind,
                label: displayLabel,
                last_updated_at: item.updated_at || item.last_seen_at || null,
                created_at: item.created_at || null,
                tiny_search_text: tinySearchText || null,
                source: source === "memory" ? "slash_pane" : "entity_pane",
            },
        },
        title: displayLabel,
        subtitle: item.subtitle || undefined,
        kindLabel: normalizeKindLabel(mentionKind),
        dateLabel: formatMentionDate(updatedAt),
        searchText: tinySearchText || undefined,
        updatedAt: updatedAt || undefined,
    };
}

export default function ChatWorkspacePage() {
    const [inputValue, setInputValue] = React.useState("");
    const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);
    const [isPaneOpen, setIsPaneOpen] = React.useState(true);
    const [paneTab, setPaneTab] = React.useState<PaneTab>("all");
    const [paneQuery, setPaneQuery] = React.useState("");
    const [paneLoading, setPaneLoading] = React.useState(false);
    const [entityItems, setEntityItems] = React.useState<ReferencePaneItem[]>([]);
    const [memoryItems, setMemoryItems] = React.useState<ReferencePaneItem[]>([]);
    const [selectedPaneMentions, setSelectedPaneMentions] = React.useState<ChatMention[]>([]);

    const inputRef = React.useRef<HTMLInputElement>(null);
    const scrollRef = React.useRef<HTMLDivElement>(null);
    const frozenActionChipsBySessionRef = React.useRef<Record<string, ActionChip[]>>({});

    const queryClient = useQueryClient();

    const {
        currentSessionId,
        setCurrentSessionId,
        sendMessage,
        createSession,
        deleteSession,
        approveAction,
        rejectAction,
        isSending,
        isCreating,
        isApproving,
        isRejecting,
    } = useChat();

    const { data: sessionList } = useChatSessions({ limit: 20, offset: 0, enabled: true });
    const { data: messages, pendingActions } = useChatMessages(currentSessionId);
    const { data: personalizedActionChips } = useChatActionChips({ limit: 5, enabled: true });

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

    React.useEffect(() => {
        setSelectedPaneMentions([]);
    }, [currentSessionId]);

    React.useEffect(() => {
        const activeIds = new Set((sessionList?.sessions || []).map((s) => s.id));
        for (const key of Object.keys(frozenActionChipsBySessionRef.current)) {
            if (key === "__unsaved_session__") continue;
            if (!activeIds.has(key)) delete frozenActionChipsBySessionRef.current[key];
        }
    }, [sessionList?.sessions]);

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
        sessionId: currentSessionId || "default",
        onMentionSelected: (mention) => {
            trackUIEvent("mention_selected", { mention_type: mention.kind, source: "inline" });
        },
    });

    React.useEffect(() => {
        let cancelled = false;
        const timer = setTimeout(async () => {
            setPaneLoading(true);
            try {
                const [entitySuggestions, slashSuggestions] = await Promise.all([
                    chatService.getMentionSuggestions(paneQuery, 120, currentSessionId || "default"),
                    chatService.getSlashSuggestions(paneQuery, 180, currentSessionId || "default"),
                ]);
                if (cancelled) return;
                setEntityItems(entitySuggestions.map((item) => toReferencePaneItem(item, "entity")));
                setMemoryItems(slashSuggestions.map((item) => toReferencePaneItem(item, "memory")));
            } catch {
                if (!cancelled) {
                    setEntityItems([]);
                    setMemoryItems([]);
                }
            } finally {
                if (!cancelled) setPaneLoading(false);
            }
        }, 120);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [paneQuery, currentSessionId]);

    const paneItems = React.useMemo(() => {
        let items: ReferencePaneItem[];
        if (paneTab === "entities") {
            items = entityItems;
        } else if (paneTab === "remember") {
            items = memoryItems;
        } else {
            items = [...entityItems, ...memoryItems];
        }
        return items
            .slice()
            .sort((a, b) => {
                const aTs = a.updatedAt ? Date.parse(a.updatedAt) : 0;
                const bTs = b.updatedAt ? Date.parse(b.updatedAt) : 0;
                return bTs - aTs;
            });
    }, [entityItems, memoryItems, paneTab]);

    const selectedPaneMentionKeys = React.useMemo(
        () => new Set(selectedPaneMentions.map((mention) => mentionKey(mention))),
        [selectedPaneMentions]
    );

    const togglePaneMention = React.useCallback((mention: ChatMention) => {
        const key = mentionKey(mention);
        setSelectedPaneMentions((prev) => {
            if (prev.some((m) => mentionKey(m) === key)) {
                return prev.filter((m) => mentionKey(m) !== key);
            }
            return [...prev, mention];
        });
    }, []);

    const removePaneMention = React.useCallback((mention: ChatMention) => {
        const key = mentionKey(mention);
        setSelectedPaneMentions((prev) => prev.filter((m) => mentionKey(m) !== key));
    }, []);

    const compileMentionsForMessage = React.useCallback((content: string): ChatMention[] => {
        const inlineMentions = parseMentions(content);
        const merged: ChatMention[] = [];
        const seen = new Set<string>();
        for (const mention of [...inlineMentions, ...selectedPaneMentions]) {
            const key = mentionKey(mention);
            if (seen.has(key)) continue;
            seen.add(key);
            merged.push(mention);
        }
        return merged;
    }, [parseMentions, selectedPaneMentions]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputValue.trim() || isSending || isCreating) return;

        const content = inputValue.trim();
        const mentions = compileMentionsForMessage(content);
        setInputValue("");

        try {
            if (!currentSessionId) {
                const session = await createSession({ mode: "action" });
                await sendMessage({ session_id: session.id, content, mode: "action", mentions });
            } else {
                await sendMessage({ session_id: currentSessionId, content, mode: "action", mentions });
            }
            clearMentionState();
            setSelectedPaneMentions([]);
            trackUIEvent("chat_message_sent", {
                has_mentions: mentions.length > 0,
                mention_count: mentions.length,
                source: "dashboard_chat",
            });
        } catch {
            toast.error("That didn't send. Try again.");
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

    const handleDeleteSession = async (sessionId: string) => {
        if (pendingDeleteId !== sessionId) {
            setPendingDeleteId(sessionId);
            setTimeout(() => setPendingDeleteId((prev) => (prev === sessionId ? null : prev)), 2500);
            return;
        }

        setPendingDeleteId(null);
        const snapshot = queryClient.getQueryData<SessionsCache>(SESSIONS_QUERY_KEY);
        const previousSessionId = currentSessionId;

        queryClient.setQueryData<SessionsCache>(SESSIONS_QUERY_KEY, (old) => ({
            ...old,
            sessions: (old?.sessions ?? []).filter((s) => s.id !== sessionId),
        }));

        if (currentSessionId === sessionId) {
            const remaining = (snapshot?.sessions ?? []).filter((s) => s.id !== sessionId);
            setCurrentSessionId(remaining[0]?.id ?? null);
        }

        try {
            await deleteSession(sessionId);
        } catch {
            queryClient.setQueryData(SESSIONS_QUERY_KEY, snapshot);
            setCurrentSessionId(previousSessionId);
            toast.error("That didn't delete. Try again.");
        }
    };

    const handleNewThread = async () => {
        try {
            const session = await createSession({ mode: "action" });
            setCurrentSessionId(session.id);
        } catch {
            toast.error("Something went wrong. Try again.");
        }
    };

    const chipSessionKey = currentSessionId || "__unsaved_session__";
    const candidateChips: ActionChip[] = (
        personalizedActionChips && personalizedActionChips.length > 0 ? personalizedActionChips : FALLBACK_ACTION_CHIPS
    ).slice(0, 5);
    const actionChips = React.useMemo(() => {
        const existing = frozenActionChipsBySessionRef.current[chipSessionKey];
        if (existing && existing.length > 0) return existing;
        const frozen = candidateChips.slice(0, 5);
        frozenActionChipsBySessionRef.current[chipSessionKey] = frozen;
        return frozen;
    }, [candidateChips, chipSessionKey]);

    const hasMessages = Boolean(messages && messages.length > 0);
    const activeSession = sessionList?.sessions?.find((s) => s.id === currentSessionId);

    return (
        <div className={cn(
            "grid grid-cols-1 gap-6 min-h-[calc(100vh-10rem)]",
            isPaneOpen ? "lg:grid-cols-[240px_1fr_320px]" : "lg:grid-cols-[240px_1fr]"
        )}>
            <aside
                className="rounded-[14px] border border-border bg-white flex flex-col"
                style={{ boxShadow: CARD_SHADOW }}
            >
                <div className="px-4 pt-5 pb-3 border-b border-border">
                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                        {new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
                    </p>
                </div>

                <div className="flex-1 overflow-y-auto py-2 px-2 min-h-0">
                    {!sessionList?.sessions?.length && (
                        <p className="px-2 py-8 text-xs text-muted-foreground text-center font-inter">
                            Your conversations appear here.
                        </p>
                    )}
                    {sessionList?.sessions?.slice(0, 20).map((session) => {
                        const isActive = currentSessionId === session.id;
                        const isPendingDelete = pendingDeleteId === session.id;
                        return (
                            <div
                                key={session.id}
                                className={cn(
                                    "group flex items-center rounded-[8px] mb-0.5 transition-all border",
                                    isActive ? "bg-primary/[0.07] border-primary/20" : "border-transparent hover:bg-linen"
                                )}
                            >
                                <button
                                    aria-label={`Open ${session.title || "Untitled chat"}`}
                                    className="flex-1 text-left px-3 py-2.5 min-w-0"
                                    onClick={() => setCurrentSessionId(session.id)}
                                >
                                    <span className={cn(
                                        "block text-[13px] truncate font-inter",
                                        isActive ? "text-primary font-medium" : "text-foreground"
                                    )}>
                                        {session.title || "Untitled"}
                                    </span>
                                </button>

                                {isPendingDelete ? (
                                    <button
                                        className="shrink-0 mr-1.5 px-2 py-1 text-[11px] font-semibold text-destructive bg-destructive/10 rounded-[6px] transition-all font-inter"
                                        onClick={(e) => { e.stopPropagation(); handleDeleteSession(session.id); }}
                                    >
                                        Delete?
                                    </button>
                                ) : (
                                    <button
                                        aria-label={`Delete ${session.title || "Untitled chat"}`}
                                        className="shrink-0 p-1.5 mr-1 rounded-[6px] opacity-0 group-hover:opacity-100 transition-all text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                        onClick={(e) => { e.stopPropagation(); handleDeleteSession(session.id); }}
                                    >
                                        <Trash2 size={13} />
                                    </button>
                                )}
                            </div>
                        );
                    })}
                </div>

                <div className="p-3 border-t border-border">
                    <button
                        onClick={handleNewThread}
                        disabled={isCreating}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-[8px] text-[13px] font-medium text-primary border border-primary/25 bg-primary/[0.04] hover:bg-primary/[0.09] active:scale-[0.98] transition-all font-inter disabled:opacity-50"
                    >
                        <Plus size={15} strokeWidth={2.5} />
                        New chat
                    </button>
                </div>
            </aside>

            <section
                className="rounded-[14px] border border-border bg-white flex flex-col min-h-[calc(100vh-10rem)]"
                style={{ boxShadow: CARD_SHADOW }}
            >
                {hasMessages && (
                    <div className="px-6 py-3 border-b border-border flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-foreground truncate font-inter">
                            {activeSession?.title || "Chat"}
                        </p>
                        <button
                            type="button"
                            onClick={() => setIsPaneOpen((prev) => !prev)}
                            className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-linen font-inter"
                        >
                            {isPaneOpen ? "Hide references" : "Show references"}
                        </button>
                    </div>
                )}

                {!hasMessages && !isPaneOpen && (
                    <div className="px-6 pt-4">
                        <button
                            type="button"
                            onClick={() => setIsPaneOpen(true)}
                            className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-linen font-inter"
                        >
                            Show references
                        </button>
                    </div>
                )}

                <ScrollArea className="flex-1 px-6 py-6">
                    <div className="flex flex-col gap-3 min-h-full">
                        {!hasMessages && (
                            <div className="flex flex-col pt-8">
                                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-3 font-inter">
                                    {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
                                </p>
                                <h1 className="font-playfair text-[28px] font-semibold text-foreground leading-tight tracking-tight">
                                    What can I help you with?
                                </h1>
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
                                                trackUIEvent("chat_action_approved", { action_id: id, source: "dashboard_chat" });
                                            }}
                                            onReject={(id) => rejectAction({ sessionId: currentSessionId, actionId: id })}
                                            isApproving={isApproving}
                                            isRejecting={isRejecting}
                                        />
                                    )}
                                </div>
                            );
                        })}

                        {isSending && (
                            <div className="flex justify-start">
                                <div
                                    className="bg-white border border-border rounded-2xl rounded-bl-[4px] px-4 py-3.5 flex items-center gap-1.5"
                                    style={{ boxShadow: CARD_SHADOW }}
                                >
                                    <span className="teeks-dot" style={{ animationDelay: "0ms" }} />
                                    <span className="teeks-dot" style={{ animationDelay: "200ms" }} />
                                    <span className="teeks-dot" style={{ animationDelay: "400ms" }} />
                                </div>
                            </div>
                        )}

                        <div ref={scrollRef} />
                    </div>
                </ScrollArea>

                <div className="p-4 border-t border-border">
                    {!hasMessages && (
                        <div className="flex flex-wrap gap-2 mb-3">
                            {actionChips.map((chip) => (
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
                    )}

                    {selectedPaneMentions.length > 0 && (
                        <div className="mb-3 flex flex-wrap gap-1.5">
                            {selectedPaneMentions.map((mention) => (
                                <span
                                    key={mentionKey(mention)}
                                    className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/[0.06] px-2.5 py-1 text-[11px] text-primary font-inter"
                                >
                                    {mention.kind === "memory" ? "/" : "@"}{mention.label}
                                    <button
                                        type="button"
                                        className="text-primary/70 hover:text-primary"
                                        onClick={() => removePaneMention(mention)}
                                        aria-label={`Remove ${mention.label}`}
                                    >
                                        <X size={12} />
                                    </button>
                                </span>
                            ))}
                        </div>
                    )}

                    <form className="flex gap-2.5 items-center" onSubmit={handleSubmit}>
                        <div className="relative flex-1">
                            <Input
                                ref={inputRef}
                                aria-label="Chat message input"
                                value={inputValue}
                                role="combobox"
                                aria-autocomplete="list"
                                aria-expanded={Boolean(mentionContext || loadingSuggestions)}
                                aria-controls={listboxId}
                                aria-activedescendant={
                                    mentionSuggestions[activeSuggestionIndex]
                                        ? `${listboxId}-option-${activeSuggestionIndex}`
                                        : undefined
                                }
                                placeholder="Ask Teeks?"
                                className="bg-linen border-border focus-visible:bg-white focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30 h-11 text-sm transition-colors font-inter"
                                onChange={(e) => {
                                    const value = e.target.value;
                                    const cursor = e.target.selectionStart ?? value.length;
                                    onInputChange(value, cursor);
                                }}
                                onKeyDown={onInputKeyDown}
                                disabled={isSending || isCreating}
                            />

                            {(mentionContext || loadingSuggestions) && (
                                <div
                                    id={listboxId}
                                    role="listbox"
                                    className="absolute left-0 right-0 bottom-full z-40 mb-1 rounded-[8px] border border-border bg-white shadow-md overflow-hidden"
                                >
                                    {loadingSuggestions ? (
                                        <div className="px-3 py-2 text-xs text-muted-foreground font-inter" aria-live="polite">
                                            Loading...
                                        </div>
                                    ) : mentionSuggestions.length > 0 ? (
                                        mentionSuggestions.map((suggestion, index) => (
                                            <button
                                                key={suggestion.key}
                                                id={`${listboxId}-option-${index}`}
                                                type="button"
                                                role="option"
                                                aria-selected={index === activeSuggestionIndex}
                                                className={cn(
                                                    "w-full px-3 py-2 text-left text-xs font-inter hover:bg-linen transition-colors",
                                                    index === activeSuggestionIndex ? "bg-linen ring-1 ring-inset ring-primary/30" : ""
                                                )}
                                                onMouseDown={(evt) => { evt.preventDefault(); applySuggestion(suggestion); }}
                                            >
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="font-medium text-foreground">{suggestion.display}</span>
                                                    <span className="rounded-full border border-border/60 px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                                                        {suggestion.kind}
                                                    </span>
                                                </div>
                                                {(suggestion.updatedAt || suggestion.createdAt) && (
                                                    <div className="mt-1 text-[11px] text-muted-foreground">
                                                        {formatMentionDate(suggestion.updatedAt || suggestion.createdAt)}
                                                    </div>
                                                )}
                                                {suggestion.searchText && (
                                                    <div className="mt-1 text-[11px] text-muted-foreground line-clamp-1">
                                                        {suggestion.searchText}
                                                    </div>
                                                )}
                                                {suggestion.subtitle && (
                                                    <div className="mt-1 text-[11px] text-muted-foreground line-clamp-1">
                                                        {suggestion.subtitle}
                                                    </div>
                                                )}
                                            </button>
                                        ))
                                    ) : (
                                        <div className="px-3 py-2 text-xs text-muted-foreground font-inter" aria-live="polite">
                                            No matches
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        <button
                            type="submit"
                            aria-label="Send message"
                            disabled={!inputValue.trim() || isSending || isCreating}
                            className="h-11 w-11 rounded-full bg-primary text-white flex items-center justify-center shrink-0 disabled:opacity-35 hover:bg-primary/90 active:scale-[0.94] transition-all shadow-sm"
                        >
                            <ArrowUp size={18} strokeWidth={2.5} />
                        </button>
                    </form>
                </div>
            </section>

            {isPaneOpen && (
            <aside
                className="rounded-[14px] border border-border bg-white flex flex-col min-h-[calc(100vh-10rem)]"
                style={{ boxShadow: CARD_SHADOW }}
            >
                <div className="px-4 py-4 border-b border-border">
                    <div className="flex items-center justify-between gap-2">
                        <div>
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                References
                            </p>
                            <p className="text-sm text-foreground mt-1 font-inter">
                                Select what Teeks should use on your next message.
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={() => setIsPaneOpen(false)}
                            className="rounded-full border border-border p-1.5 text-muted-foreground hover:bg-linen"
                            aria-label="Hide references pane"
                        >
                            <X size={14} />
                        </button>
                    </div>
                    <div className="relative mt-3">
                        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            aria-label="Search references"
                            value={paneQuery}
                            onChange={(e) => setPaneQuery(e.target.value)}
                            placeholder="Search entities and remember entries"
                            className="h-9 pl-8 text-xs bg-linen border-border focus-visible:bg-white focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30"
                        />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                        {([
                            { key: "all", label: "All" },
                            { key: "entities", label: "@ Entities" },
                            { key: "remember", label: "/ Remember" },
                        ] as Array<{ key: PaneTab; label: string }>).map((tab) => (
                            <button
                                key={tab.key}
                                type="button"
                                onClick={() => setPaneTab(tab.key)}
                                className={cn(
                                    "rounded-full border px-2.5 py-1 text-[11px] font-inter transition",
                                    paneTab === tab.key
                                        ? "bg-primary/[0.08] text-primary border-primary/25"
                                        : "bg-white text-muted-foreground border-border hover:bg-linen"
                                )}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>
                </div>

                <ScrollArea className="flex-1">
                    <div className="p-3 space-y-2">
                        {paneLoading ? (
                            <div className="rounded-[10px] border border-border px-3 py-3 text-xs text-muted-foreground font-inter">
                                Loading references...
                            </div>
                        ) : paneItems.length === 0 ? (
                            <div className="rounded-[10px] border border-border px-3 py-3 text-xs text-muted-foreground font-inter">
                                No references found.
                            </div>
                        ) : (
                            paneItems.map((item) => {
                                const selected = selectedPaneMentionKeys.has(mentionKey(item.mention));
                                return (
                                    <button
                                        key={item.id}
                                        type="button"
                                        onClick={() => togglePaneMention(item.mention)}
                                        className={cn(
                                            "w-full rounded-[10px] border px-3 py-2.5 text-left transition font-inter",
                                            selected
                                                ? "border-primary/30 bg-primary/[0.06]"
                                                : "border-border bg-white hover:bg-linen"
                                        )}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <p className="text-[12px] font-medium text-foreground truncate">
                                                    {item.source === "memory" ? "/" : "@"}
                                                    {item.title}
                                                </p>
                                                <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
                                                    {item.kindLabel}
                                                </p>
                                            </div>
                                            <span className={cn(
                                                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]",
                                                selected
                                                    ? "border-primary/30 text-primary bg-primary/[0.08]"
                                                    : "border-border text-muted-foreground"
                                            )}>
                                                {selected ? (
                                                    <>
                                                        <Check size={10} />
                                                        Added
                                                    </>
                                                ) : (
                                                    "Add"
                                                )}
                                            </span>
                                        </div>
                                        {item.subtitle && (
                                            <p className="mt-1 text-[11px] text-muted-foreground line-clamp-1">
                                                {item.subtitle}
                                            </p>
                                        )}
                                        {(item.dateLabel || item.searchText) && (
                                            <p className="mt-1 text-[11px] text-muted-foreground line-clamp-1">
                                                {item.dateLabel}
                                                {item.dateLabel && item.searchText ? " | " : ""}
                                                {item.searchText}
                                            </p>
                                        )}
                                    </button>
                                );
                            })
                        )}
                    </div>
                </ScrollArea>
            </aside>
            )}
        </div>
    );
}
