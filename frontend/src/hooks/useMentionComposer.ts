"use client";

import * as React from "react";

import { chatService, type ChatMention } from "@/services/chat";

export type MentionType = "contact" | "email" | "knowledge";

export type MentionContext = {
    type: MentionType;
    start: number;
    end: number;
    query: string;
};

export type MentionSuggestion = {
    key: string;
    display: string;
    mention: ChatMention;
};

type UseMentionComposerArgs = {
    inputValue: string;
    setInputValue: React.Dispatch<React.SetStateAction<string>>;
    inputRef: React.RefObject<HTMLInputElement | null>;
    onMentionSelected?: (mention: ChatMention) => void;
};

function detectMentionContext(value: string, cursor: number): MentionContext | null {
    const prefix = value.slice(0, cursor);
    const atIndex = prefix.lastIndexOf("@");
    if (atIndex < 0) return null;
    if (atIndex > 0) {
        const prior = prefix[atIndex - 1];
        if (!/\s|\(|\[/.test(prior)) return null;
    }
    const token = prefix.slice(atIndex);
    if (token.includes("\n")) return null;
    if (token.startsWith("@contacts/")) {
        return { type: "contact", start: atIndex, end: cursor, query: token.slice("@contacts/".length) };
    }
    if (token.startsWith("@email/")) {
        return { type: "email", start: atIndex, end: cursor, query: token.slice("@email/".length) };
    }
    if (token.startsWith("@knowledge/")) {
        return { type: "knowledge", start: atIndex, end: cursor, query: token.slice("@knowledge/".length) };
    }
    return null;
}

export function useMentionComposer({
    inputValue,
    setInputValue,
    inputRef,
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
        const mentions: ChatMention[] = [...selectedMentions.filter((m) => content.includes(m.label))];
        const dedupe = new Set(mentions.map((m) => `${m.type}:${m.ref_id}`));

        const contactRe = /@contacts\/([^\s]+)/g;
        const knowledgeRe = /@knowledge\/([^\s]+)/g;
        const emailParenRe = /@email\/([^\n]*?\([^)\n]*\))/g;
        const emailFallbackRe = /@email\/([^\s]+)/g;

        let match: RegExpExecArray | null = null;
        while ((match = contactRe.exec(content)) !== null) {
            const raw = match[1].trim();
            const mention = { type: "contact" as const, ref_id: raw, label: `@contacts/${raw}` };
            const key = `${mention.type}:${mention.ref_id}`;
            if (!dedupe.has(key)) {
                dedupe.add(key);
                mentions.push(mention);
            }
        }
        while ((match = emailParenRe.exec(content)) !== null) {
            const raw = match[1].trim();
            const mention = { type: "email" as const, ref_id: raw, label: `@email/${raw}` };
            const key = `${mention.type}:${mention.ref_id}`;
            if (!dedupe.has(key)) {
                dedupe.add(key);
                mentions.push(mention);
            }
        }
        while ((match = emailFallbackRe.exec(content)) !== null) {
            const raw = match[1].trim().replace(/[.,;:!?]+$/g, "");
            const mention = { type: "email" as const, ref_id: raw, label: `@email/${raw}` };
            const key = `${mention.type}:${mention.ref_id}`;
            if (!dedupe.has(key)) {
                dedupe.add(key);
                mentions.push(mention);
            }
        }
        while ((match = knowledgeRe.exec(content)) !== null) {
            const raw = match[1].trim();
            const mention = { type: "knowledge" as const, ref_id: raw, label: `@knowledge/${raw}` };
            const key = `${mention.type}:${mention.ref_id}`;
            if (!dedupe.has(key)) {
                dedupe.add(key);
                mentions.push(mention);
            }
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

            const queryKey = `${mentionContext.type}:${mentionContext.query.trim().toLowerCase()}`;
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
                if (mentionContext.type === "contact") {
                    const contacts = await chatService.getMentionableContacts(mentionContext.query, 8);
                    if (cancelled || requestId !== requestSeqRef.current) return;
                    const nextSuggestions: MentionSuggestion[] = contacts.map((contact) => {
                        const ref = contact.email || contact.name || "";
                        return {
                            key: `contact:${ref}`,
                            display: `@contacts/${contact.name || contact.email}`,
                            mention: {
                                type: "contact",
                                ref_id: ref,
                                label: `@contacts/${contact.email || contact.name || ref}`,
                                metadata: { email: contact.email, name: contact.name },
                            },
                        };
                    });
                    suggestionsCacheRef.current[queryKey] = nextSuggestions;
                    setMentionSuggestions(nextSuggestions);
                } else if (mentionContext.type === "email") {
                    const emails = await chatService.getMentionableEmails(mentionContext.query, 8);
                    if (cancelled || requestId !== requestSeqRef.current) return;
                    const nextSuggestions: MentionSuggestion[] = emails.map((email) => ({
                        key: `email:${email.message_id}`,
                        display: `@email/${email.subject || "(no subject)"} (${email.sender || "unknown"})`,
                        mention: {
                            type: "email",
                            ref_id: `msg:${email.message_id}`,
                            label: `@email/${email.subject || "(no subject)"} (${email.sender || "unknown"})`,
                            metadata: { message_id: email.message_id, sender: email.sender, thread_id: email.thread_id },
                        },
                    }));
                    suggestionsCacheRef.current[queryKey] = nextSuggestions;
                    setMentionSuggestions(nextSuggestions);
                } else {
                    const notes = await chatService.getMentionableNotes(mentionContext.query, 8);
                    if (cancelled || requestId !== requestSeqRef.current) return;
                    const nextSuggestions: MentionSuggestion[] = notes.map((note) => ({
                        key: `knowledge:${note.note_id}`,
                        display: `@knowledge/${note.slug}`,
                        mention: {
                            type: "knowledge",
                            ref_id: note.slug,
                            label: `@knowledge/${note.slug}`,
                            metadata: {
                                note_id: note.note_id,
                                slug: note.slug,
                                note_type: note.note_type,
                                title: note.title,
                            },
                        },
                    }));
                    suggestionsCacheRef.current[queryKey] = nextSuggestions;
                    setMentionSuggestions(nextSuggestions);
                }
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

        const timer = setTimeout(loadSuggestions, 180);
        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [mentionContext]);

    const applySuggestion = React.useCallback((suggestion: MentionSuggestion) => {
        if (!mentionContext) return;
        onMentionSelected?.(suggestion.mention);
        const before = inputValue.slice(0, mentionContext.start);
        const after = inputValue.slice(mentionContext.end);
        const replacement = `${suggestion.mention.label} `;
        const nextValue = `${before}${replacement}${after}`;
        setInputValue(nextValue);
        setSelectedMentions((prev) => {
            const key = `${suggestion.mention.type}:${suggestion.mention.ref_id}`;
            if (prev.some((m) => `${m.type}:${m.ref_id}` === key)) return prev;
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

    return {
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
    };
}
