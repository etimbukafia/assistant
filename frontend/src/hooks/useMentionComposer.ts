"use client";

import * as React from "react";

import { chatService, type ChatMention, type MentionSuggestion as ApiMentionSuggestion } from "@/services/chat";

export type MentionKind = "contact" | "thread" | "event" | "message" | "task" | "memory";

export type MentionContext = {
    trigger: "@" | "/";
    start: number;
    end: number;
    query: string;
};

export type MentionSuggestion = {
    key: string;
    display: string;
    subtitle?: string;
    kind: MentionKind;
    searchText?: string;
    updatedAt?: string;
    createdAt?: string;
    mention: ChatMention;
};

type UseMentionComposerArgs = {
    inputValue: string;
    setInputValue: React.Dispatch<React.SetStateAction<string>>;
    inputRef: React.RefObject<HTMLInputElement | null>;
    sessionId?: string;
    onMentionSelected?: (mention: ChatMention) => void;
};

function detectMentionContext(value: string, cursor: number): MentionContext | null {
    const prefix = value.slice(0, cursor);
    const atIndex = prefix.lastIndexOf("@");
    const slashIndex = prefix.lastIndexOf("/");
    const idx = Math.max(atIndex, slashIndex);
    if (idx < 0) return null;
    const trigger = prefix[idx] as "@" | "/";

    if (idx > 0) {
        const prior = prefix[idx - 1];
        if (!/\s|\(|\[/.test(prior)) return null;
    }
    const token = prefix.slice(idx + 1);
    if (token.includes("\n") || token.includes(" ")) return null;
    return { trigger, start: idx, end: cursor, query: token };
}

function mentionLabelToken(mention: ChatMention) {
    const prefix = mention.kind === "memory" ? "/" : "@";
    return `${prefix}${mention.label}`;
}

export function useMentionComposer({
    inputValue,
    setInputValue,
    inputRef,
    sessionId,
    onMentionSelected,
}: UseMentionComposerArgs) {
    const [selectedMentions, setSelectedMentions] = React.useState<ChatMention[]>([]);
    const [mentionContext, setMentionContext] = React.useState<MentionContext | null>(null);
    const [mentionSuggestions, setMentionSuggestions] = React.useState<MentionSuggestion[]>([]);
    const [activeSuggestionIndex, setActiveSuggestionIndex] = React.useState(0);
    const [loadingSuggestions, setLoadingSuggestions] = React.useState(false);

    const suggestionsCacheRef = React.useRef<Record<string, MentionSuggestion[]>>({});
    const requestSeqRef = React.useRef(0);
    const listboxId = React.useId();

    const parseMentions = React.useCallback((content: string): ChatMention[] => {
        const mentions: ChatMention[] = [];
        const dedupe = new Set<string>();

        for (const m of selectedMentions) {
            const token = mentionLabelToken(m);
            if (!content.includes(token)) continue;
            const key = `${m.kind}:${m.ref}`;
            if (dedupe.has(key)) continue;
            dedupe.add(key);
            mentions.push(m);
        }

        const rawMatches = content.match(/[@/]([^\s]+)/g) || [];
        for (const match of rawMatches) {
            const value = match.slice(1).trim();
            if (!value) continue;
            const known = selectedMentions.find((m) => m.label === value || m.ref === value);
            if (!known) continue;
            const key = `${known.kind}:${known.ref}`;
            if (dedupe.has(key)) continue;
            dedupe.add(key);
            mentions.push(known);
        }

        return mentions;
    }, [selectedMentions]);

    React.useEffect(() => {
        let cancelled = false;
        const loadSuggestions = async () => {
            if (!mentionContext) {
                setMentionSuggestions([]);
                setActiveSuggestionIndex(0);
                setLoadingSuggestions(false);
                return;
            }

            const queryKey = `${sessionId || "default"}:${mentionContext.trigger}:${mentionContext.query.trim().toLowerCase()}`;
            const cached = suggestionsCacheRef.current[queryKey];
            if (cached) {
                setMentionSuggestions(cached);
                setActiveSuggestionIndex(0);
                setLoadingSuggestions(false);
                return;
            }

            const requestId = ++requestSeqRef.current;
            setLoadingSuggestions(true);
            try {
                const suggestions = mentionContext.trigger === "@"
                    ? await chatService.getMentionSuggestions(
                        mentionContext.query,
                        8,
                        sessionId || "default"
                    )
                    : await chatService.getSlashSuggestions(
                        mentionContext.query,
                        8,
                        sessionId || "default"
                    );
                if (cancelled || requestId !== requestSeqRef.current) return;
                const nextSuggestions: MentionSuggestion[] = suggestions.map((item: ApiMentionSuggestion) => {
                    const displayLabel = item.display_label || item.label;
                    const isMemory = mentionContext.trigger === "/" || item.kind === "memory";
                    const normalizedKind: MentionKind = isMemory ? "memory" : (item.kind as MentionKind);
                    return {
                        key: `${normalizedKind}:${item.ref}`,
                        display: `${isMemory ? "/" : "@"}${displayLabel}`,
                        subtitle: item.subtitle,
                        kind: normalizedKind,
                        searchText: item.search_text,
                        updatedAt: item.updated_at || item.last_seen_at,
                        createdAt: item.created_at,
                        mention: {
                            kind: normalizedKind,
                            ref: item.ref,
                            label: displayLabel,
                            metadata: {
                                kind: normalizedKind,
                                label: displayLabel,
                                last_updated_at: item.updated_at || item.last_seen_at || null,
                                created_at: item.created_at || null,
                                tiny_search_text: item.search_text || null,
                                trigger: mentionContext.trigger,
                            },
                        },
                    };
                });
                suggestionsCacheRef.current[queryKey] = nextSuggestions;
                setMentionSuggestions(nextSuggestions);
                setActiveSuggestionIndex(0);
            } catch {
                if (!cancelled && requestId === requestSeqRef.current) {
                    setMentionSuggestions([]);
                }
            } finally {
                if (!cancelled && requestId === requestSeqRef.current) {
                    setLoadingSuggestions(false);
                }
            }
        };

        const timer = setTimeout(loadSuggestions, 150);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [mentionContext, sessionId]);

    const applySuggestion = React.useCallback((suggestion: MentionSuggestion) => {
        if (!mentionContext) return;
        onMentionSelected?.(suggestion.mention);

        const before = inputValue.slice(0, mentionContext.start);
        const after = inputValue.slice(mentionContext.end);
        const replacement = `${mentionContext.trigger}${suggestion.mention.label} `;
        const nextValue = `${before}${replacement}${after}`;

        setInputValue(nextValue);
        setSelectedMentions((prev) => {
            const key = `${suggestion.mention.kind}:${suggestion.mention.ref}`;
            if (prev.some((m) => `${m.kind}:${m.ref}` === key)) return prev;
            return [...prev, suggestion.mention];
        });
        setMentionContext(null);
        setMentionSuggestions([]);
        setActiveSuggestionIndex(0);

        requestAnimationFrame(() => {
            inputRef.current?.focus();
            const nextCaret = before.length + replacement.length;
            inputRef.current?.setSelectionRange(nextCaret, nextCaret);
        });
    }, [inputRef, inputValue, mentionContext, onMentionSelected, setInputValue]);

    const onInputChange = React.useCallback((value: string, cursor: number) => {
        setInputValue(value);
        setMentionContext(detectMentionContext(value, cursor));
    }, [setInputValue]);

    const onInputKeyDown = React.useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!mentionSuggestions.length) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveSuggestionIndex((idx) => (idx + 1) % mentionSuggestions.length);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveSuggestionIndex((idx) => (idx - 1 + mentionSuggestions.length) % mentionSuggestions.length);
        } else if (e.key === "Enter" || e.key === "Tab") {
            e.preventDefault();
            applySuggestion(mentionSuggestions[activeSuggestionIndex]);
        } else if (e.key === "Escape") {
            setMentionContext(null);
            setMentionSuggestions([]);
        }
    }, [activeSuggestionIndex, applySuggestion, mentionSuggestions]);

    const clearMentionState = React.useCallback(() => {
        setSelectedMentions([]);
        setMentionContext(null);
        setMentionSuggestions([]);
        setActiveSuggestionIndex(0);
    }, []);

    const addSelectedMention = React.useCallback((mention: ChatMention) => {
        setSelectedMentions((prev) => {
            const key = `${mention.kind}:${mention.ref}`;
            if (prev.some((m) => `${m.kind}:${m.ref}` === key)) return prev;
            return [...prev, mention];
        });
    }, []);

    const removeSelectedMention = React.useCallback((mention: ChatMention) => {
        setSelectedMentions((prev) => prev.filter((m) => !(m.kind === mention.kind && m.ref === mention.ref)));
    }, []);

    return {
        listboxId,
        mentionContext,
        mentionSuggestions,
        activeSuggestionIndex,
        loadingSuggestions,
        selectedMentions,
        parseMentions,
        onInputChange,
        onInputKeyDown,
        applySuggestion,
        clearMentionState,
        addSelectedMention,
        removeSelectedMention,
    };
}

