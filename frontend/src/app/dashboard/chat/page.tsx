"use client";

import * as React from "react";
import { ArrowUp, Check, PanelLeftClose, PanelLeftOpen, Plus, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { ApprovalGateComposer } from "@/components/chat/ApprovalGateComposer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
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
type PaneFilter =
    | "all"
    | "contact"
    | "thread"
    | "event"
    | "task"
    | "decision"
    | "commitment"
    | "preferences"
    | "relationships"
    | "risks";
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
const ENTITY_PAGE_SIZE = 30;
const MEMORY_PAGE_SIZE = 30;
const PANE_FILTERS: Array<{ key: PaneFilter; label: string }> = [
    { key: "all", label: "All" },
    { key: "contact", label: "@ Contacts" },
    { key: "thread", label: "@ Threads" },
    { key: "event", label: "@ Events" },
    { key: "task", label: "@ Tasks" },
    { key: "decision", label: "/ Decisions" },
    { key: "commitment", label: "/ Commitments" },
    { key: "preferences", label: "/ Preferences" },
    { key: "relationships", label: "/ Relationships" },
    { key: "risks", label: "/ Risks" },
];

function mentionToneClass(kind: ChatMention["kind"]): string {
    if (kind === "memory") return "border-amber-300/70 bg-amber-50 text-amber-900";
    if (kind === "contact") return "border-sky-300/70 bg-sky-50 text-sky-900";
    if (kind === "event") return "border-emerald-300/70 bg-emerald-50 text-emerald-900";
    if (kind === "thread") return "border-violet-300/70 bg-violet-50 text-violet-900";
    if (kind === "task") return "border-rose-300/70 bg-rose-50 text-rose-900";
    return "border-primary/30 bg-primary/[0.06] text-primary";
}

function isEntityFilter(filter: PaneFilter): filter is "contact" | "thread" | "event" | "task" {
    return filter === "contact" || filter === "thread" || filter === "event" || filter === "task";
}

function isMemoryFilter(filter: PaneFilter): filter is "decision" | "commitment" | "preferences" | "relationships" | "risks" {
    return (
        filter === "decision" ||
        filter === "commitment" ||
        filter === "preferences" ||
        filter === "relationships" ||
        filter === "risks"
    );
}

function mentionKey(mention: ChatMention): string {
    return `${mention.kind}:${mention.ref}`;
}

function formatMentionDate(value?: string): string {
    if (!value) return "";
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return "";
    return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function withEllipsis(value: string | undefined, maxChars: number): string {
    const text = (value || "").trim();
    if (!text) return "";
    if (text.length <= maxChars) return text;
    return `${text.slice(0, Math.max(0, maxChars - 3)).trim()}...`;
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
    const [isSessionsOpen, setIsSessionsOpen] = React.useState(true);
    const [isPaneOpen, setIsPaneOpen] = React.useState(true);
    const [isMobileReferencesOpen, setIsMobileReferencesOpen] = React.useState(false);
    const [paneFilter, setPaneFilter] = React.useState<PaneFilter>("all");
    const [paneQuery, setPaneQuery] = React.useState("");
    const [paneLoading, setPaneLoading] = React.useState(false);
    const [paneLoadingMore, setPaneLoadingMore] = React.useState(false);
    const [entityItems, setEntityItems] = React.useState<ReferencePaneItem[]>([]);
    const [memoryItems, setMemoryItems] = React.useState<ReferencePaneItem[]>([]);
    const [entityOffset, setEntityOffset] = React.useState(0);
    const [memoryOffset, setMemoryOffset] = React.useState(0);
    const [hasMoreEntities, setHasMoreEntities] = React.useState(true);
    const [hasMoreMemory, setHasMoreMemory] = React.useState(true);
    const [selectedPaneMentions, setSelectedPaneMentions] = React.useState<ChatMention[]>([]);
    const [previewItem, setPreviewItem] = React.useState<ReferencePaneItem | null>(null);

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
        isSending,
        isCreating,
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

    const mergeUniqueItems = React.useCallback((prev: ReferencePaneItem[], next: ReferencePaneItem[]) => {
        const seen = new Set(prev.map((item) => item.id));
        const merged = prev.slice();
        for (const item of next) {
            if (seen.has(item.id)) continue;
            seen.add(item.id);
            merged.push(item);
        }
        return merged;
    }, []);

    const isReferencesActive = isPaneOpen || isMobileReferencesOpen;

    React.useEffect(() => {
        if (!isReferencesActive) {
            setPaneLoading(false);
            return;
        }
        let cancelled = false;
        const timer = setTimeout(async () => {
            setPaneLoading(true);
            try {
                const entityKind = isEntityFilter(paneFilter) ? paneFilter : undefined;
                const memoryType = isMemoryFilter(paneFilter) ? paneFilter : undefined;
                const needEntity = paneFilter === "all" || Boolean(entityKind);
                const needMemory = paneFilter === "all" || Boolean(memoryType);
                const [entitySuggestions, slashSuggestions] = await Promise.all([
                    needEntity
                        ? chatService.getMentionSuggestions(
                            paneQuery,
                            ENTITY_PAGE_SIZE,
                            currentSessionId || "default",
                            0,
                            entityKind
                        )
                        : Promise.resolve([]),
                    needMemory
                        ? chatService.getSlashSuggestions(
                            paneQuery,
                            MEMORY_PAGE_SIZE,
                            currentSessionId || "default",
                            0,
                            memoryType
                        )
                        : Promise.resolve([]),
                ]);
                if (cancelled) return;
                setEntityItems(entitySuggestions.map((item) => toReferencePaneItem(item, "entity")));
                setMemoryItems(slashSuggestions.map((item) => toReferencePaneItem(item, "memory")));
                setEntityOffset(entitySuggestions.length);
                setMemoryOffset(slashSuggestions.length);
                setHasMoreEntities(needEntity ? entitySuggestions.length === ENTITY_PAGE_SIZE : false);
                setHasMoreMemory(needMemory ? slashSuggestions.length === MEMORY_PAGE_SIZE : false);
            } catch {
                if (!cancelled) {
                    setEntityItems([]);
                    setMemoryItems([]);
                    setEntityOffset(0);
                    setMemoryOffset(0);
                    setHasMoreEntities(false);
                    setHasMoreMemory(false);
                }
            } finally {
                if (!cancelled) setPaneLoading(false);
            }
        }, 140);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [paneQuery, currentSessionId, isReferencesActive, paneFilter]);

    const handleLoadMorePane = React.useCallback(async () => {
        if (paneLoadingMore || !isReferencesActive) return;
        const entityKind = isEntityFilter(paneFilter) ? paneFilter : undefined;
        const memoryType = isMemoryFilter(paneFilter) ? paneFilter : undefined;
        const needEntity = (paneFilter === "all" || Boolean(entityKind)) && hasMoreEntities;
        const needMemory = (paneFilter === "all" || Boolean(memoryType)) && hasMoreMemory;
        if (!needEntity && !needMemory) return;

        setPaneLoadingMore(true);
        try {
            const [entitySuggestions, slashSuggestions] = await Promise.all([
                needEntity
                    ? chatService.getMentionSuggestions(
                        paneQuery,
                        ENTITY_PAGE_SIZE,
                        currentSessionId || "default",
                        entityOffset,
                        entityKind
                    )
                    : Promise.resolve([]),
                needMemory
                    ? chatService.getSlashSuggestions(
                        paneQuery,
                        MEMORY_PAGE_SIZE,
                        currentSessionId || "default",
                        memoryOffset,
                        memoryType
                    )
                    : Promise.resolve([]),
            ]);

            if (needEntity) {
                const mapped = entitySuggestions.map((item) => toReferencePaneItem(item, "entity"));
                setEntityItems((prev) => mergeUniqueItems(prev, mapped));
                setEntityOffset((prev) => prev + entitySuggestions.length);
                setHasMoreEntities(entitySuggestions.length === ENTITY_PAGE_SIZE);
            }
            if (needMemory) {
                const mapped = slashSuggestions.map((item) => toReferencePaneItem(item, "memory"));
                setMemoryItems((prev) => mergeUniqueItems(prev, mapped));
                setMemoryOffset((prev) => prev + slashSuggestions.length);
                setHasMoreMemory(slashSuggestions.length === MEMORY_PAGE_SIZE);
            }
        } finally {
            setPaneLoadingMore(false);
        }
    }, [
        paneLoadingMore,
        isReferencesActive,
        paneFilter,
        hasMoreEntities,
        hasMoreMemory,
        paneQuery,
        currentSessionId,
        entityOffset,
        memoryOffset,
        mergeUniqueItems,
    ]);

    const paneItems = React.useMemo(() => {
        let items: ReferencePaneItem[];
        if (isEntityFilter(paneFilter)) {
            items = entityItems;
        } else if (isMemoryFilter(paneFilter)) {
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
    }, [entityItems, memoryItems, paneFilter]);
    const hasMorePaneItems =
        (isEntityFilter(paneFilter) && hasMoreEntities) ||
        (isMemoryFilter(paneFilter) && hasMoreMemory) ||
        (paneFilter === "all" && (hasMoreEntities || hasMoreMemory));

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
        const seenTokens = new Set<string>();
        for (const mention of [...inlineMentions, ...selectedPaneMentions]) {
            const key = mentionKey(mention);
            const tokenKey = `${mention.kind}:${(mention.label || "").trim().toLowerCase()}`;
            if (seen.has(key)) continue;
            if (seenTokens.has(tokenKey)) continue;
            seen.add(key);
            seenTokens.add(tokenKey);
            merged.push(mention);
        }
        return merged;
    }, [parseMentions, selectedPaneMentions]);

    const selectedInlineMentions = React.useMemo(() => {
        if (!inputValue.trim()) return [];
        return parseMentions(inputValue);
    }, [inputValue, parseMentions]);

    const selectedInputMentions = React.useMemo(() => {
        const merged: ChatMention[] = [];
        const seen = new Set<string>();
        for (const mention of [...selectedInlineMentions, ...selectedPaneMentions]) {
            const key = mentionKey(mention);
            if (seen.has(key)) continue;
            seen.add(key);
            merged.push(mention);
        }
        return merged;
    }, [selectedInlineMentions, selectedPaneMentions]);

    const removeInputMention = React.useCallback((mention: ChatMention) => {
        if (selectedPaneMentions.some((m) => mentionKey(m) === mentionKey(mention))) {
            removePaneMention(mention);
            return;
        }
        const token = `${mention.kind === "memory" ? "/" : "@"}${mention.label}`;
        setInputValue((prev) => prev.replace(token, "").replace(/\s{2,}/g, " ").trimStart());
    }, [removePaneMention, selectedPaneMentions]);

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
        const previousSessionId = currentSessionId;
        setCurrentSessionId(null);
        try {
            const session = await createSession({ mode: "action" });
            setCurrentSessionId(session.id);
        } catch {
            setCurrentSessionId(previousSessionId);
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
            "grid grid-cols-1 gap-6 h-[calc(100vh-7.5rem)] lg:h-[calc(100vh-4rem)] overflow-hidden",
            isSessionsOpen && isPaneOpen  ? "lg:grid-cols-[240px_1fr_320px]" :
            isSessionsOpen && !isPaneOpen ? "lg:grid-cols-[240px_1fr]" :
            !isSessionsOpen && isPaneOpen ? "lg:grid-cols-[1fr_320px]" :
                                            "lg:grid-cols-[1fr]"
        )}>
            {isSessionsOpen && (
            <aside
                className="hidden lg:flex rounded-[14px] border border-border bg-white flex-col h-full overflow-hidden"
                style={{ boxShadow: CARD_SHADOW }}
            >
                <div className="px-4 pt-4 pb-3 border-b border-border flex items-center justify-between gap-2">
                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                        {new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
                    </p>
                    <button
                        type="button"
                        onClick={() => setIsSessionsOpen(false)}
                        className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                        aria-label="Collapse sessions"
                        title="Collapse sessions"
                    >
                        <PanelLeftClose size={15} strokeWidth={1.8} />
                    </button>
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
            )}

            <section
                className="rounded-[14px] border border-border bg-white flex flex-col h-full overflow-hidden"
                style={{ boxShadow: CARD_SHADOW }}
            >
                <div className="px-4 py-3 border-b border-border hidden lg:flex items-center gap-2">
                    {!isSessionsOpen && (
                        <button
                            type="button"
                            onClick={() => setIsSessionsOpen(true)}
                            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                            aria-label="Expand sessions"
                            title="Expand sessions"
                        >
                            <PanelLeftOpen size={15} strokeWidth={1.8} />
                        </button>
                    )}
                    <p className="flex-1 text-sm font-medium text-foreground truncate font-inter">
                        {hasMessages ? (activeSession?.title || "Chat") : ""}
                    </p>
                    <button
                        type="button"
                        onClick={() => setIsPaneOpen((prev) => !prev)}
                        className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-linen font-inter"
                    >
                        {isPaneOpen ? "Hide references" : "Show references"}
                    </button>
                </div>

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

                        {messages?.map((msg) => (
                            <div key={msg.id} className="flex flex-col">
                                <MessageBubble role={msg.role} content={msg.content} timestamp={msg.created_at} />
                            </div>
                        ))}

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
                    {currentSessionId && pendingActions?.length > 0 && (
                        <ApprovalGateComposer
                            pendingActions={pendingActions}
                            disabled={isSending || isCreating}
                            onSendDecision={async (command) => {
                                await sendMessage({
                                    session_id: currentSessionId,
                                    content: command,
                                    mode: "action",
                                    mentions: [],
                                });
                                trackUIEvent("chat_approval_sent", {
                                    source: "dashboard_chat",
                                    pending_count: pendingActions.length,
                                });
                            }}
                        />
                    )}

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

                    {selectedInputMentions.length > 0 && (
                        <div className="mb-3 flex flex-wrap gap-1.5">
                            {selectedInputMentions.map((mention) => (
                                <span
                                    key={mentionKey(mention)}
                                    className={cn(
                                        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium font-inter",
                                        mentionToneClass(mention.kind)
                                    )}
                                >
                                    {mention.kind === "memory" ? "/" : "@"}{mention.label}
                                    <button
                                        type="button"
                                        className="opacity-70 hover:opacity-100"
                                        onClick={() => removeInputMention(mention)}
                                        aria-label={`Remove ${mention.label}`}
                                    >
                                        <X size={12} />
                                    </button>
                                </span>
                            ))}
                        </div>
                    )}

                    <form className="flex gap-2.5 items-center" onSubmit={handleSubmit}>
                        <button
                            type="button"
                            onClick={() => setIsMobileReferencesOpen(true)}
                            className="lg:hidden h-11 rounded-full border border-border px-3 text-[12px] text-muted-foreground hover:bg-linen font-inter shrink-0"
                        >
                            References
                        </button>
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
                                    className="absolute left-0 right-0 bottom-full z-40 mb-1 rounded-[8px] border border-border bg-white shadow-md max-h-72 overflow-y-auto overscroll-contain"
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
                className="hidden lg:flex rounded-[14px] border border-border bg-white flex-col h-full overflow-hidden"
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
                        {PANE_FILTERS.map((tab) => (
                            <button
                                key={tab.key}
                                type="button"
                                onClick={() => setPaneFilter(tab.key)}
                                className={cn(
                                    "rounded-full border px-2.5 py-1 text-[11px] font-inter transition",
                                    paneFilter === tab.key
                                        ? "bg-primary/[0.08] text-primary border-primary/25"
                                        : "bg-white text-muted-foreground border-border hover:bg-linen"
                                )}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>
                </div>

                <ScrollArea className="flex-1 min-h-0">
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
                                    <div
                                        key={item.id}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => togglePaneMention(item.mention)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault();
                                                togglePaneMention(item.mention);
                                            }
                                        }}
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
                                                    {withEllipsis(item.title, 78)}
                                                </p>
                                                <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
                                                    {item.kindLabel}{item.dateLabel ? ` - ${item.dateLabel}` : ""}
                                                </p>
                                            </div>
                                            <div className="flex flex-col items-end gap-1">
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setPreviewItem(item);
                                                    }}
                                                    className="text-[10px] text-primary hover:underline underline-offset-2"
                                                >
                                                    View
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        togglePaneMention(item.mention);
                                                    }}
                                                    className={cn(
                                                        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]",
                                                        selected
                                                            ? "border-primary/30 text-primary bg-primary/[0.08]"
                                                            : "border-border text-muted-foreground"
                                                    )}
                                                >
                                                    {selected ? (
                                                        <>
                                                            <Check size={10} />
                                                            Added
                                                        </>
                                                    ) : (
                                                        "Add"
                                                    )}
                                                </button>
                                            </div>
                                        </div>
                                        {(item.searchText || item.subtitle) && (
                                            <p className="mt-1 text-[11px] text-muted-foreground truncate">
                                                {withEllipsis(item.searchText || item.subtitle, 120)}
                                            </p>
                                        )}
                                    </div>
                                );
                            })
                        )}
                    </div>
                </ScrollArea>

                <div className="border-t border-border p-3">
                    <button
                        type="button"
                        onClick={handleLoadMorePane}
                        disabled={paneLoading || paneLoadingMore || !hasMorePaneItems}
                        className="w-full rounded-[8px] border border-border px-3 py-2 text-xs text-muted-foreground hover:bg-linen disabled:opacity-50 disabled:cursor-not-allowed font-inter"
                    >
                        {paneLoadingMore ? "Loading more..." : hasMorePaneItems ? "Load more" : "No more results"}
                    </button>
                </div>
            </aside>
            )}

            <Sheet open={isMobileReferencesOpen} onOpenChange={setIsMobileReferencesOpen}>
                <SheetContent side="bottom" className="h-[78vh] p-0">
                    <div className="h-full flex flex-col">
                        <SheetHeader className="px-4 py-3 border-b border-border">
                            <SheetTitle className="text-sm">References</SheetTitle>
                            <p className="text-xs text-muted-foreground">Select what Teeks should use on your next message.</p>
                        </SheetHeader>
                        <div className="px-4 py-3 border-b border-border space-y-3">
                            <div className="relative">
                                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    aria-label="Search references"
                                    value={paneQuery}
                                    onChange={(e) => setPaneQuery(e.target.value)}
                                    placeholder="Search entities and remember entries"
                                    className="h-9 pl-8 text-xs bg-linen border-border"
                                />
                            </div>
                            <ScrollArea className="w-full">
                                <div className="flex gap-1.5 pb-1">
                                    {PANE_FILTERS.map((tab) => (
                                        <button
                                            key={`mobile-${tab.key}`}
                                            type="button"
                                            onClick={() => setPaneFilter(tab.key)}
                                            className={cn(
                                                "whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-inter transition",
                                                paneFilter === tab.key
                                                    ? "bg-primary/[0.08] text-primary border-primary/25"
                                                    : "bg-white text-muted-foreground border-border hover:bg-linen"
                                            )}
                                        >
                                            {tab.label}
                                        </button>
                                    ))}
                                </div>
                            </ScrollArea>
                        </div>
                        <ScrollArea className="flex-1 min-h-0">
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
                                            <div
                                                key={`mobile-${item.id}`}
                                                role="button"
                                                tabIndex={0}
                                                onClick={() => togglePaneMention(item.mention)}
                                                onKeyDown={(e) => {
                                                    if (e.key === "Enter" || e.key === " ") {
                                                        e.preventDefault();
                                                        togglePaneMention(item.mention);
                                                    }
                                                }}
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
                                                            {withEllipsis(item.title, 78)}
                                                        </p>
                                                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
                                                            {item.kindLabel}{item.dateLabel ? ` - ${item.dateLabel}` : ""}
                                                        </p>
                                                    </div>
                                                    <div className="flex flex-col items-end gap-1">
                                                        <button
                                                            type="button"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setPreviewItem(item);
                                                            }}
                                                            className="text-[10px] text-primary hover:underline underline-offset-2"
                                                        >
                                                            View
                                                        </button>
                                                        <button
                                                            type="button"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                togglePaneMention(item.mention);
                                                            }}
                                                            className={cn(
                                                                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]",
                                                                selected
                                                                    ? "border-primary/30 text-primary bg-primary/[0.08]"
                                                                    : "border-border text-muted-foreground"
                                                            )}
                                                        >
                                                            {selected ? "Added" : "Add"}
                                                        </button>
                                                    </div>
                                                </div>
                                                {(item.searchText || item.subtitle) && (
                                                    <p className="mt-1 text-[11px] text-muted-foreground truncate">
                                                        {withEllipsis(item.searchText || item.subtitle, 120)}
                                                    </p>
                                                )}
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </ScrollArea>
                        <div className="border-t border-border p-3">
                            <button
                                type="button"
                                onClick={handleLoadMorePane}
                                disabled={paneLoading || paneLoadingMore || !hasMorePaneItems}
                                className="w-full rounded-[8px] border border-border px-3 py-2 text-xs text-muted-foreground hover:bg-linen disabled:opacity-50 disabled:cursor-not-allowed font-inter"
                            >
                                {paneLoadingMore ? "Loading more..." : hasMorePaneItems ? "Load more" : "No more results"}
                            </button>
                        </div>
                    </div>
                </SheetContent>
            </Sheet>

            <Dialog open={Boolean(previewItem)} onOpenChange={(open) => !open && setPreviewItem(null)}>
                <DialogContent className="max-w-[560px]">
                    <DialogHeader>
                        <DialogTitle className="text-base font-semibold font-inter">
                            {previewItem ? `${previewItem.source === "memory" ? "/" : "@"}${previewItem.title}` : "Reference details"}
                        </DialogTitle>
                    </DialogHeader>
                    {previewItem && (
                        <div className="space-y-3 font-inter">
                            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                                {previewItem.kindLabel}{previewItem.dateLabel ? ` - ${previewItem.dateLabel}` : ""}
                            </p>
                            {previewItem.subtitle && (
                                <div className="rounded-[10px] border border-border bg-linen/40 p-3">
                                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Summary</p>
                                    <p className="text-sm text-foreground whitespace-pre-wrap break-words">{previewItem.subtitle}</p>
                                </div>
                            )}
                            {previewItem.searchText && (
                                <div className="rounded-[10px] border border-border bg-linen/40 p-3">
                                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Details</p>
                                    <p className="text-sm text-foreground whitespace-pre-wrap break-words">{previewItem.searchText}</p>
                                </div>
                            )}
                            <div className="rounded-[10px] border border-border p-3">
                                <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Reference ID</p>
                                <p className="text-xs text-muted-foreground break-all">{previewItem.mention.ref}</p>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
