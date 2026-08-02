"use client";

import { useRef, useState, useCallback, useMemo, useEffect } from "react";
import { toast } from "sonner";
import { Plus, Link2, X, Trash2, SlidersHorizontal } from "lucide-react";
import { useMentionComposer } from "@/hooks/useMentionComposer";
import { useDiaryEntries, useDiaryContacts, useDiaryMutations } from "@/hooks/useVault";
import { useNotificationsFeed } from "@/hooks/useNotifications";
import { useAuth } from "@/context/AuthContext";
import { VoiceCaptureButton } from "@/components/vault/VoiceCaptureButton";
import {
    CONTEXT_CAPTURE_MAX_CHARS,
    type DiaryEntryType,
    type DiaryCaptureScopeType,
    type DiaryContextEntry,
    type DiaryContact,
} from "@/services/vault";

// ── Constants ──────────────────────────────────────────────────────────────
const CARD_SHADOW = "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)";

const ENTRY_TYPES: { value: DiaryEntryType; label: string }[] = [
    { value: "risk", label: "Risk" },
    { value: "decision", label: "Decision" },
    { value: "commitment", label: "Commitment" },
    { value: "preference", label: "Preference" },
    { value: "insight", label: "Insight" },
];

const TYPE_COLORS: Record<DiaryEntryType, string> = {
    risk: "border-obsidian/30 text-obsidian/70 bg-obsidian/[0.04]",
    decision: "border-copper/40 text-copper bg-copper/[0.06]",
    commitment: "border-sage/40 text-sage bg-sage/[0.06]",
    preference: "border-teal/40 text-teal bg-teal/[0.06]",
    insight: "border-burgundy/40 text-burgundy bg-burgundy/[0.06]",
};
const PENDING_TYPE_COLOR = "border-secondary/40 text-secondary bg-secondary/[0.08]";

const ENTITY_ICONS: Record<string, string> = {
    contact: "👤",
    task: "✓",
    event: "📅",
    thread: "✉",
    message: "✉",
};

function groupEntriesByDate(entries: DiaryContextEntry[]) {
    const groups: { dateLabel: string; entries: DiaryContextEntry[] }[] = [];
    const seen = new Map<string, number>();

    for (const entry of entries) {
        const date = new Date(entry.created_at);
        const label = date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
        if (!seen.has(label)) {
            seen.set(label, groups.length);
            groups.push({ dateLabel: label, entries: [] });
        }
        groups[seen.get(label)!].entries.push(entry);
    }
    return groups;
}

function renderContentWithMentions(content: string, links: DiaryContextEntry["links"]) {
    if (!links.length) return <span>{content}</span>;

    const parts: React.ReactNode[] = [];
    let remaining = content;
    let key = 0;

    for (const link of links) {
        const token = `@${link.display_name}`;
        const idx = remaining.indexOf(token);
        if (idx === -1) continue;
        if (idx > 0) parts.push(<span key={key++}>{remaining.slice(0, idx)}</span>);
        parts.push(
            <mark key={key++} className="bg-primary/10 text-primary rounded px-0.5 not-italic font-medium">
                {token}
            </mark>
        );
        remaining = remaining.slice(idx + token.length);
    }
    if (remaining) parts.push(<span key={key++}>{remaining}</span>);
    return <>{parts}</>;
}

// ── Sub-components ─────────────────────────────────────────────────────────

const CONFIDENCE_UNCERTAIN_THRESHOLD = 0.7;

function EntryCard({
    entry,
    onForget,
    onEdit,
    onCorrectCategory,
}: {
    entry: DiaryContextEntry;
    onForget: (id: number) => void;
    onEdit: (entry: DiaryContextEntry) => void;
    onCorrectCategory: (id: number, category: DiaryEntryType) => void;
}) {
    const [pickerOpen, setPickerOpen] = useState(false);
    const typeLabel = ENTRY_TYPES.find((t) => t.value === entry.type)?.label ?? entry.type;
    const time = new Date(entry.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

    const isPending = entry.classification_status === "pending";
    const isUncertain =
        entry.classification_status === "classified" &&
        typeof entry.classification_confidence === "number" &&
        entry.classification_confidence < CONFIDENCE_UNCERTAIN_THRESHOLD;
    const badgeLabel = isPending ? "Remembering" : typeLabel;
    const badgeClass = isPending ? PENDING_TYPE_COLOR : TYPE_COLORS[entry.type];

    const handlePickCategory = (e: React.MouseEvent, category: DiaryEntryType) => {
        e.stopPropagation();
        onCorrectCategory(entry.id, category);
        setPickerOpen(false);
    };

    return (
        <div
            className="bg-white border border-border rounded-[14px] p-4 space-y-3 teeks-bubble-in group cursor-pointer hover:border-border/70 transition-colors"
            style={{ boxShadow: CARD_SHADOW }}
            onClick={() => onEdit(entry)}
        >
            <div className="flex items-center justify-between gap-2">
                {/* Type badge — doubles as the picker trigger */}
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setPickerOpen((v) => !v); }}
                        className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[1.2px] px-2 py-0.5 rounded-full border font-inter transition-opacity hover:opacity-80 ${badgeClass}`}
                        title={isPending ? "Remembering" : "Change category"}
                    >
                        {isUncertain ? (
                            <span className="font-bold">?</span>
                        ) : null}
                        {badgeLabel}
                    </button>
                    {isUncertain && (
                        <span className="text-[12px] text-muted-foreground font-inter">Teeks wasn't certain</span>
                    )}
                    {entry.entity_type !== "global" && entry.scope_resolved !== false && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground border border-border/60 rounded-full px-2 py-0.5 font-inter max-w-[150px]">
                            <span aria-hidden>{ENTITY_ICONS[entry.entity_type] ?? ""}</span>
                            <span className="truncate">{entry.linked_to ?? entry.entity_type}</span>
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {entry.created_by === "Teeks" ? (
                        <span className="text-[10px] font-medium border border-secondary/30 bg-secondary/[0.06] text-secondary rounded-full px-2 py-0.5 font-inter">
                            Teeks
                        </span>
                    ) : (
                        <span className="text-[10px] text-muted-foreground/50 font-inter">You</span>
                    )}
                    <span className="text-[11px] text-muted-foreground font-inter">{time}</span>
                    <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onForget(entry.id); }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-[11px] font-medium text-muted-foreground hover:text-burgundy font-inter"
                        aria-label="Forget this entry"
                    >
                        Forget this
                    </button>
                </div>
            </div>

            {/* Inline category picker */}
            {pickerOpen && (
                <div
                    className="flex flex-wrap gap-1.5 pt-1 border-t border-border/40"
                    onClick={(e) => e.stopPropagation()}
                >
                    <span className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground font-inter self-center mr-1">
                        Change to:
                    </span>
                    {ENTRY_TYPES.filter((t) => t.value !== entry.type).map((t) => (
                        <button
                            key={t.value}
                            type="button"
                            onClick={(e) => handlePickCategory(e, t.value)}
                            className={`text-[10px] font-bold uppercase tracking-[1.2px] px-2 py-0.5 rounded-full border font-inter transition-opacity hover:opacity-80 ${TYPE_COLORS[t.value]}`}
                        >
                            {t.label}
                        </button>
                    ))}
                </div>
            )}

            <p className="text-sm text-foreground leading-relaxed font-inter whitespace-pre-wrap">
                {renderContentWithMentions(entry.content, entry.links ?? [])}
            </p>

            {entry.links && entry.links.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1 border-t border-border/40">
                    {entry.links.map((link, i) => (
                        <span
                            key={i}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground border border-border/60 rounded-full px-2 py-0.5 font-inter"
                        >
                            <span>{ENTITY_ICONS[link.entity_type] ?? <Link2 size={10} />}</span>
                            {link.display_name}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

function ContactCard({
    contact,
    onDelete,
    onEdit,
}: {
    contact: DiaryContact;
    onDelete: (id: number) => void;
    onEdit: (contact: DiaryContact) => void;
}) {
    return (
        <div
            className="bg-white border border-border rounded-[8px] p-3 space-y-1 group relative cursor-pointer hover:border-border/70 transition-colors"
            style={{ boxShadow: CARD_SHADOW }}
            onClick={() => onEdit(contact)}
        >
            <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onDelete(contact.id); }}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-burgundy"
                aria-label="Delete contact"
            >
                <Trash2 size={12} />
            </button>
            <p className="text-sm font-semibold text-foreground font-inter pr-4">{contact.name}</p>
            {(contact.role || contact.organization) && (
                <p className="text-[11px] text-muted-foreground font-inter">
                    {[contact.role, contact.organization].filter(Boolean).join(" · ")}
                </p>
            )}
            {contact.email && (
                <p className="text-[11px] text-primary/80 font-inter">{contact.email}</p>
            )}
            {contact.notes && (
                <p className="text-[11px] text-muted-foreground font-inter italic mt-1">{contact.notes}</p>
            )}
        </div>
    );
}

// ── Feed skeleton ──────────────────────────────────────────────────────────

function FeedSkeleton() {
    return (
        <div className="space-y-8">
            {[0, 1].map((g) => (
                <div key={g} className="space-y-3">
                    <div className="flex items-center gap-3">
                        <div className="h-3 w-36 rounded bg-muted-foreground/10 animate-pulse" />
                        <div className="flex-1 h-px bg-border/40" />
                    </div>
                    <div className="space-y-3">
                        {[0, 1, 2].map((i) => (
                            <div
                                key={i}
                                className="bg-white border border-border rounded-[14px] p-4 space-y-3 animate-pulse"
                                style={{ boxShadow: CARD_SHADOW }}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-2">
                                        <div className="h-5 w-16 rounded-full bg-muted-foreground/10" />
                                        <div className="h-4 w-20 rounded-full bg-muted-foreground/[0.07]" />
                                    </div>
                                    <div className="h-3 w-10 rounded bg-muted-foreground/[0.07]" />
                                </div>
                                <div className="space-y-2">
                                    <div className="h-3.5 w-full rounded bg-muted-foreground/[0.07]" />
                                    <div className="h-3.5 w-4/5 rounded bg-muted-foreground/[0.07]" />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function DiaryPage() {
    const { settings } = useAuth();
    const isPro = settings?.subscription_tier === "pro";

    const [activeView, setActiveView] = useState<"diary" | "people">("diary");
    const recentCaptureIdsRef = useRef<Set<number>>(new Set());
    const seenClassificationNotificationIdsRef = useRef<Set<number>>(new Set());

    // Composer state
    const [content, setContent] = useState("");
    const [entryType, setEntryType] = useState<DiaryEntryType | "all">("all");
    const [selectedScopeKey, setSelectedScopeKey] = useState("global");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // People state
    const [contactSearch, setContactSearch] = useState("");
    const [showNewContact, setShowNewContact] = useState(false);
    const [newContact, setNewContact] = useState({ name: "", email: "", role: "", organization: "", notes: "" });

    // Edit state — entries
    const [editingEntry, setEditingEntry] = useState<DiaryContextEntry | null>(null);
    const [editEntryFields, setEditEntryFields] = useState<{
        content: string;
        type: DiaryEntryType;
    }>({ content: "", type: "insight" });

    // Edit state — contacts
    const [editingContact, setEditingContact] = useState<DiaryContact | null>(null);
    const [editContactFields, setEditContactFields] = useState({ name: "", email: "", role: "", organization: "", notes: "" });
    const [pendingRefreshMs, setPendingRefreshMs] = useState<number | false>(false);
    const [filterOpen, setFilterOpen] = useState(false);

    // Data
    const { data: entriesData, isLoading: entriesLoading } = useDiaryEntries(undefined, { refetchInterval: pendingRefreshMs });
    const { data: contacts = [], isLoading: contactsLoading } = useDiaryContacts(contactSearch || undefined);
    const { createEntry, updateEntry, correctCategory, createContact, updateContact, deleteContact } = useDiaryMutations();

    // @mention support
    const {
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
    } = useMentionComposer({
        inputValue: content,
        setInputValue: setContent,
        inputRef: textareaRef,
        sessionId: "diary",
    });

    const entries = useMemo(() => entriesData ?? [], [entriesData]);
    const pendingEntryCount = useMemo(
        () => entries.filter((entry) => entry.classification_status === "pending").length,
        [entries]
    );
    const hasPendingEntries = pendingEntryCount > 0;
    const classificationNotifications = useNotificationsFeed(10, 0, activeView === "diary" && hasPendingEntries);
    const scopeOptions = useMemo(() => {
        const options: Array<{
            key: string;
            label: string;
            scopeType: DiaryCaptureScopeType;
            scopeId: string | null;
            linkedTo: string | null;
        }> = [
            { key: "global", label: "Global", scopeType: "global", scopeId: null, linkedTo: null },
        ];

        for (const mention of selectedMentions) {
            if (!["contact", "message", "event", "task"].includes(mention.kind)) continue;
            options.push({
                key: `${mention.kind}:${mention.ref}`,
                label: `${mention.kind[0].toUpperCase()}${mention.kind.slice(1)}: ${mention.label}`,
                scopeType: mention.kind as DiaryCaptureScopeType,
                scopeId: mention.ref,
                linkedTo: mention.label,
            });
        }

        return options;
    }, [selectedMentions]);
    const selectedScope = useMemo(
        () => scopeOptions.find((option) => option.key === selectedScopeKey) ?? scopeOptions[0],
        [scopeOptions, selectedScopeKey]
    );
    const activeEntryTypeLabel = useMemo(
        () => entryType === "all" ? "All" : (ENTRY_TYPES.find((type) => type.value === entryType)?.label ?? entryType),
        [entryType]
    );

    // Timeline: show all entries by default, optionally filtered by category
    const grouped = useMemo(() => {
        const filtered = entryType === "all" ? entries : entries.filter((e) => e.type === entryType);
        return groupEntriesByDate([...filtered].reverse());
    }, [entries, entryType]);

    const showDropdown = Boolean(mentionContext || loadingSuggestions);

    useEffect(() => {
        setPendingRefreshMs(activeView === "diary" && hasPendingEntries ? 5_000 : false);
    }, [activeView, hasPendingEntries]);

    useEffect(() => {
        const notifications = classificationNotifications.data?.notifications ?? [];
        if (!notifications.length) return;

        for (const notification of notifications) {
            if (seenClassificationNotificationIdsRef.current.has(notification.id)) {
                continue;
            }
            seenClassificationNotificationIdsRef.current.add(notification.id);

            if (notification.target_type !== "context_entry" || !notification.target_id) {
                continue;
            }

            const entryId = Number(notification.target_id);
            if (!Number.isFinite(entryId) || !recentCaptureIdsRef.current.has(entryId)) {
                continue;
            }

            toast(notification.title, {
                description: notification.body || undefined,
            });
            recentCaptureIdsRef.current.delete(entryId);
        }
    }, [classificationNotifications.data]);

    const handleSubmit = useCallback(async () => {
        const trimmed = content.trim();
        if (!trimmed) return;
        if (trimmed.length > CONTEXT_CAPTURE_MAX_CHARS) {
            toast.error(`Keep this under ${CONTEXT_CAPTURE_MAX_CHARS} characters.`);
            return;
        }

        const links = parseMentions(trimmed).map((m) => ({
            entity_type: m.kind,
            entity_id: m.ref,
            display_name: m.label,
            source: "user" as const,
        }));

        setContent("");
        setSelectedScopeKey("global");
        clearMentionState();

        try {
            const created = await createEntry.mutateAsync({
                text: trimmed,
                scope_type: selectedScope.scopeType,
                scope_id: selectedScope.scopeId,
                linked_to: selectedScope.linkedTo,
                links,
            });
            recentCaptureIdsRef.current.add(created.id);
            toast("Got it.");
        } catch {
            toast.error("Didn't save. Try again.");
        }
    }, [content, parseMentions, createEntry, clearMentionState, selectedScope]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        onInputKeyDown(e);
        if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !mentionSuggestions.length) {
            e.preventDefault();
            handleSubmit();
        }
    }, [onInputKeyDown, mentionSuggestions.length, handleSubmit]);

    const handleForgetEntry = useCallback(async (id: number) => {
        if (editingEntry?.id === id) setEditingEntry(null);
        try {
            await updateEntry.mutateAsync({ id, payload: { status: "forgotten" } });
            toast("Forgotten.");
        } catch {
            toast.error("Couldn't forget that. Try again later.");
        }
    }, [editingEntry, updateEntry]);

    const handleResolveEntry = useCallback(async (id: number) => {
        setEditingEntry(null);
        try {
            await updateEntry.mutateAsync({ id, payload: { status: "resolved" } });
        } catch {
            toast.error("That didn't go through. Try again.");
        }
    }, [updateEntry]);

    const handleEditEntry = useCallback((entry: DiaryContextEntry) => {
        setEditingEntry(entry);
        setEditEntryFields({
            content: entry.content,
            type: entry.type,
        });
    }, []);

    const handleCorrectCategory = useCallback(async (id: number, category: DiaryEntryType) => {
        try {
            await correctCategory.mutateAsync({ id, category });
            toast.success("Category updated.");
        } catch {
            toast.error("Could not update the category. Try again.");
        }
    }, [correctCategory]);

    const handleUpdateEntry = useCallback(async () => {
        if (!editingEntry) return;
        const id = editingEntry.id;
        const typeChanged = editEntryFields.type !== editingEntry.type;
        const textChanged = editEntryFields.content !== editingEntry.content;
        setEditingEntry(null);
        try {
            const updates: Array<Promise<unknown>> = [];
            if (textChanged) {
                updates.push(updateEntry.mutateAsync({ id, payload: { text: editEntryFields.content } }));
            }
            if (typeChanged) {
                updates.push(correctCategory.mutateAsync({ id, category: editEntryFields.type }));
            }
            if (updates.length > 0) await Promise.all(updates);
        } catch {
            toast.error("Couldn't update. Try again later.");
        }
    }, [editingEntry, editEntryFields, updateEntry, correctCategory]);

    const handleSaveContact = useCallback(async () => {
        if (!newContact.name.trim()) {
            toast.error("Name is required.");
            return;
        }
        try {
            await createContact.mutateAsync({
                name: newContact.name.trim(),
                email: newContact.email.trim() || null,
                role: newContact.role.trim() || null,
                organization: newContact.organization.trim() || null,
                notes: newContact.notes.trim() || null,
            });
            setNewContact({ name: "", email: "", role: "", organization: "", notes: "" });
            setShowNewContact(false);
        } catch (err: unknown) {
            const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
            if (typeof detail === "string") {
                toast.error(detail);
                return;
            }
            if (detail && typeof detail === "object" && "message" in detail && typeof (detail as { message?: unknown }).message === "string") {
                toast.error((detail as { message: string }).message);
                return;
            }
            toast.error("Could not save the contact. Try again later.");
        }
    }, [newContact, createContact]);

    const handleDeleteContact = useCallback(async (id: number) => {
        try {
            await deleteContact.mutateAsync(id);
        } catch {
            toast.error("Couldn't delete. Try again later.");
        }
    }, [deleteContact]);

    const handleEditContact = useCallback((contact: DiaryContact) => {
        setEditingContact(contact);
        setEditContactFields({
            name: contact.name,
            email: contact.email ?? "",
            role: contact.role ?? "",
            organization: contact.organization ?? "",
            notes: contact.notes ?? "",
        });
    }, []);

    const handleUpdateContact = useCallback(async () => {
        if (!editingContact) return;
        if (!editContactFields.name.trim()) {
            toast.error("Name is required.");
            return;
        }
        const id = editingContact.id;
        setEditingContact(null);
        try {
            await updateContact.mutateAsync({
                id,
                payload: {
                    name: editContactFields.name.trim(),
                    email: editContactFields.email.trim() || null,
                    role: editContactFields.role.trim() || null,
                    organization: editContactFields.organization.trim() || null,
                    notes: editContactFields.notes.trim() || null,
                },
            });
        } catch {
            toast.error("Couldn't update contact. Try again later.");
        }
    }, [editingContact, editContactFields, updateContact]);

    return (
        <div className="max-w-3xl mx-auto space-y-8">
            {/* ── Header ── */}
            <div>
                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-2 font-inter">
                    Diary
                </p>
                <h1 className="font-playfair text-[28px] font-semibold text-foreground leading-tight tracking-tight">
                    EA Diary
                </h1>
            </div>

            {/* ── View toggle ── */}
            <div className="flex gap-2">
                {(["diary", "people"] as const).map((view) => (
                    <button
                        key={view}
                        type="button"
                        onClick={() => setActiveView(view)}
                        className={`rounded-full border px-4 py-1.5 text-[13px] font-medium transition-all font-inter capitalize ${
                            activeView === view
                                ? "border-obsidian bg-obsidian text-white"
                                : "border-border text-muted-foreground hover:text-foreground hover:border-border/80"
                        }`}
                    >
                        {view === "diary" ? "Diary" : "People"}
                    </button>
                ))}
            </div>

            {/* ══ CONTEXT VIEW ══ */}
            {activeView === "diary" && (
                <div className="space-y-6">
                    {hasPendingEntries && (
                        <div
                            className="relative overflow-hidden rounded-[14px] border border-border bg-white px-4 py-3"
                            style={{ boxShadow: CARD_SHADOW }}
                        >
                            <div className="absolute inset-x-0 top-0 h-px bg-secondary/70" />
                            <p className="text-[13px] font-medium text-foreground font-inter">
                                Teeks is filing {pendingEntryCount} recent {pendingEntryCount === 1 ? "memory" : "memories"}.
                            </p>
                        </div>
                    )}

                    {/* Composer */}
                    <div
                        className="bg-white border border-border rounded-[14px] p-4 space-y-3"
                        style={{ boxShadow: CARD_SHADOW }}
                    >
                        <div className="space-y-1">
                            <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground font-inter">
                                Remember this
                            </p>
                            <p className="text-[13px] text-muted-foreground font-inter leading-relaxed">
                                Write the moment in plain language. Teeks will hold onto it.
                            </p>
                        </div>

                        {/* Textarea + mention dropdown */}
                        <div className="relative">
                            {showDropdown && (
                                <div
                                    id={listboxId}
                                    role="listbox"
                                    className="absolute bottom-full mb-1 left-0 right-0 bg-white border border-border rounded-[10px] shadow-lg overflow-hidden z-50 max-h-56 overflow-y-auto"
                                    style={{ boxShadow: "0 4px 16px rgba(0,0,0,0.10)" }}
                                >
                                    {loadingSuggestions && !mentionSuggestions.length ? (
                                        <div className="px-3 py-2 text-xs text-muted-foreground font-inter">
                                            <span className="teeks-dot" style={{ animationDelay: "0ms" }} />
                                            <span className="teeks-dot mx-0.5" style={{ animationDelay: "200ms" }} />
                                            <span className="teeks-dot" style={{ animationDelay: "400ms" }} />
                                        </div>
                                    ) : mentionSuggestions.length === 0 ? (
                                        <div className="px-3 py-2 text-xs text-muted-foreground font-inter">No results</div>
                                    ) : (
                                        mentionSuggestions.map((s, i) => (
                                            <button
                                                key={s.key}
                                                type="button"
                                                role="option"
                                                aria-selected={i === activeSuggestionIndex}
                                                onClick={() => applySuggestion(s)}
                                                className={`w-full text-left px-3 py-2 flex items-center gap-2 transition-colors font-inter ${
                                                    i === activeSuggestionIndex ? "bg-linen" : "hover:bg-linen/60"
                                                }`}
                                            >
                                                <span className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground w-14 shrink-0">
                                                    {s.kind}
                                                </span>
                                                <span className="text-sm font-medium text-foreground">{s.display}</span>
                                                {s.subtitle && (
                                                    <span className="text-xs text-muted-foreground truncate">{s.subtitle}</span>
                                                )}
                                            </button>
                                        ))
                                    )}
                                </div>
                            )}

                            <textarea
                                ref={textareaRef}
                                value={content}
                                onChange={(e) => onInputChange(e.target.value, e.target.selectionStart ?? e.target.value.length)}
                                onKeyDown={handleKeyDown}
                                placeholder="What just happened? A decision, a risk, something said — @mention what it's linked to."
                                rows={4}
                                className="w-full resize-none rounded-[8px] border border-border bg-linen/20 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary transition-colors"
                            />
                        </div>

                        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                            <div>
                                <label className="block text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground font-inter mb-1">
                                    Save To
                                </label>
                                <select
                                    value={selectedScope.key}
                                    onChange={(e) => setSelectedScopeKey(e.target.value)}
                                    className="w-full rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary bg-white"
                                >
                                    {scopeOptions.map((option) => (
                                        <option key={option.key} value={option.key}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex items-end justify-end">
                                <p className="text-[11px] text-muted-foreground font-inter">
                                    {content.length}/{CONTEXT_CAPTURE_MAX_CHARS}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center justify-between">
                            {selectedMentions.length > 0 ? (
                                <div className="flex flex-wrap gap-1.5">
                                    {selectedMentions.map((m) => (
                                        <span
                                            key={`${m.kind}:${m.ref}`}
                                            className="inline-flex items-center gap-1 text-[11px] font-medium text-primary border border-primary/30 rounded-full px-2 py-0.5 font-inter"
                                        >
                                            @{m.label}
                                        </span>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-[11px] text-muted-foreground/60 font-inter">⌘↵ to save</p>
                            )}
                            <div className="flex items-center gap-2">
                                <VoiceCaptureButton
                                    scopeType={selectedScope.scopeType}
                                    scopeId={selectedScope.scopeId}
                                    linkedTo={selectedScope.linkedTo}
                                    isPro={isPro}
                                    disabled={createEntry.isPending}
                                    onCaptureSaved={(entry) => {
                                        recentCaptureIdsRef.current.add(entry.id);
                                    }}
                                />
                                <button
                                    type="button"
                                    onClick={handleSubmit}
                                    disabled={!content.trim() || createEntry.isPending}
                                    className="rounded-[8px] bg-primary px-4 py-2 text-[13px] font-semibold text-white hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                                >
                                    {createEntry.isPending ? "Saving…" : "Remember"}
                                </button>
                            </div>
                        </div>
                    </div>
                    {/* Feed header */}
                    <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                Memory
                            </p>
                            {entryType !== "all" && (
                                <span className={`text-[10px] font-bold uppercase tracking-[1.2px] px-2 py-0.5 rounded-full border font-inter ${TYPE_COLORS[entryType]}`}>
                                    {activeEntryTypeLabel}
                                </span>
                            )}
                        </div>
                        <button
                            type="button"
                            onClick={() => setFilterOpen((v) => !v)}
                            title="Filter by type"
                            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium font-inter transition-colors ${
                                filterOpen || entryType !== "all"
                                    ? "border-foreground/30 text-foreground bg-card"
                                    : "border-border text-muted-foreground hover:text-foreground hover:border-border/80"
                            }`}
                        >
                            <SlidersHorizontal size={11} />
                            Filter
                        </button>
                    </div>

                    {/* Filter pills — hidden by default */}
                    {filterOpen && (
                        <div className="flex flex-wrap gap-2">
                            <button
                                type="button"
                                onClick={() => setEntryType("all")}
                                className={`rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[1.2px] transition-all font-inter ${
                                    entryType === "all"
                                        ? "border-border text-foreground bg-card"
                                        : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground bg-white"
                                }`}
                            >
                                All
                            </button>
                            {ENTRY_TYPES.map((t) => (
                                <button
                                    key={t.value}
                                    type="button"
                                    onClick={() => setEntryType(t.value)}
                                    className={`rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[1.2px] transition-all font-inter ${
                                        entryType === t.value
                                            ? TYPE_COLORS[t.value]
                                            : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground bg-white"
                                    }`}
                                >
                                    {t.label}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Entry feed — filtered by selected type */}
                    {entriesLoading ? (
                        <FeedSkeleton />
                    ) : entries.length === 0 ? (
                        <div className="py-16 text-center space-y-1">
                            <p className="text-[15px] text-foreground font-inter">Nothing here yet.</p>
                            <p className="text-[13px] text-muted-foreground font-inter">The best insights disappear in hours. Capture one now — Teeks will hold onto it.</p>
                        </div>
                    ) : grouped.length === 0 ? (
                        <p className="py-12 text-sm text-muted-foreground font-inter text-center">
                            Nothing {activeEntryTypeLabel.toLowerCase()}-related yet.
                        </p>
                    ) : (
                        <div className="space-y-8">
                            {grouped.map((group) => (
                                <div key={group.dateLabel} className="space-y-3">
                                    <div className="flex items-center gap-3">
                                        <span className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter whitespace-nowrap">
                                            {group.dateLabel}
                                        </span>
                                        <div className="flex-1 h-px bg-border/40" />
                                    </div>
                                    <div className="space-y-3">
                                        {group.entries.map((entry) => (
                                            <EntryCard
                                                key={entry.id}
                                                entry={entry}
                                                onForget={handleForgetEntry}
                                                onEdit={handleEditEntry}
                                                onCorrectCategory={handleCorrectCategory}
                                            />
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ══ PEOPLE VIEW ══ */}
            {activeView === "people" && (
                <div className="space-y-5">
                    {/* Search + add button */}
                    <div className="flex items-center gap-3">
                        <input
                            type="text"
                            value={contactSearch}
                            onChange={(e) => setContactSearch(e.target.value)}
                            placeholder="Search people…"
                            className="flex-1 rounded-[8px] border border-border bg-white px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary transition-colors"
                        />
                        <button
                            type="button"
                            onClick={() => setShowNewContact((v) => !v)}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-[13px] font-medium text-primary border border-primary/25 bg-primary/[0.04] hover:bg-primary/[0.09] active:scale-[0.98] transition-all font-inter shrink-0"
                        >
                            {showNewContact ? <X size={13} /> : <Plus size={13} strokeWidth={2.5} />}
                            {showNewContact ? "Cancel" : "New contact"}
                        </button>
                    </div>

                    {/* New contact form */}
                    {showNewContact && (
                        <div
                            className="bg-white border border-border rounded-[14px] p-4 space-y-3"
                            style={{ boxShadow: CARD_SHADOW }}
                        >
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                New contact
                            </p>
                            <div className="grid grid-cols-2 gap-3">
                                <input
                                    placeholder="Name *"
                                    value={newContact.name}
                                    onChange={(e) => setNewContact((p) => ({ ...p, name: e.target.value }))}
                                    className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                                />
                                <input
                                    placeholder="Email"
                                    value={newContact.email}
                                    onChange={(e) => setNewContact((p) => ({ ...p, email: e.target.value }))}
                                    className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                                />
                                <input
                                    placeholder="Role"
                                    value={newContact.role}
                                    onChange={(e) => setNewContact((p) => ({ ...p, role: e.target.value }))}
                                    className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                                />
                                <input
                                    placeholder="Organization"
                                    value={newContact.organization}
                                    onChange={(e) => setNewContact((p) => ({ ...p, organization: e.target.value }))}
                                    className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                                />
                            </div>
                            <textarea
                                placeholder="Notes (optional)"
                                value={newContact.notes}
                                onChange={(e) => setNewContact((p) => ({ ...p, notes: e.target.value }))}
                                rows={2}
                                className="w-full resize-none rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                            />
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={handleSaveContact}
                                    disabled={!newContact.name.trim() || createContact.isPending}
                                    className="rounded-[8px] bg-primary px-4 py-2 text-[13px] font-semibold text-white hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                                >
                                    {createContact.isPending ? "Saving…" : "Save contact"}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Contact grid */}
                    {contactsLoading ? (
                        <p className="text-sm text-muted-foreground font-inter">Loading people…</p>
                    ) : contacts.length === 0 ? (
                        <p className="py-12 text-sm text-muted-foreground font-inter text-center">
                            {contactSearch ? "No people match that search." : "No people yet. Add your first contact above."}
                        </p>
                    ) : (
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                            {contacts.map((contact) => (
                                <ContactCard
                                    key={contact.id}
                                    contact={contact}
                                    onDelete={handleDeleteContact}
                                    onEdit={handleEditContact}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ══ EDIT ENTRY MODAL ══ */}
            {editingEntry && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div
                        className="absolute inset-0 bg-black/30 backdrop-blur-[2px]"
                        onClick={() => setEditingEntry(null)}
                    />
                    <div
                        className="relative bg-white rounded-[16px] w-full max-w-md p-5 space-y-4 teeks-bubble-in"
                        style={{ boxShadow: "0 8px 32px rgba(0,0,0,0.14)" }}
                    >
                        <div className="flex items-center justify-between">
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                Edit {ENTRY_TYPES.find((t) => t.value === editingEntry.type)?.label ?? editingEntry.type}
                            </p>
                            <button
                                type="button"
                                onClick={() => setEditingEntry(null)}
                                className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <X size={16} />
                            </button>
                        </div>

                        <textarea
                            value={editEntryFields.content}
                            onChange={(e) => setEditEntryFields((p) => ({ ...p, content: e.target.value }))}
                            rows={4}
                            className="w-full resize-none rounded-[8px] border border-border px-3 py-2.5 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                        />

                        <div>
                            <label className="block text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground font-inter mb-1">
                                Category
                            </label>
                            <select
                                value={editEntryFields.type}
                                onChange={(e) => setEditEntryFields((p) => ({ ...p, type: e.target.value as DiaryEntryType }))}
                                className="w-full rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary bg-white"
                            >
                                {ENTRY_TYPES.map((type) => (
                                    <option key={type.value} value={type.value}>
                                        {type.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="flex gap-2 pt-1">
                            <button
                                type="button"
                                onClick={handleUpdateEntry}
                                disabled={!editEntryFields.content.trim()}
                                className="rounded-[8px] bg-primary px-4 py-2 text-[13px] font-semibold text-white hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                            >
                                Save
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleResolveEntry(editingEntry.id)}
                                className="rounded-[8px] border border-border px-4 py-2 text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors font-inter"
                            >
                                Resolved
                            </button>
                            <button
                                type="button"
                                onClick={() => setEditingEntry(null)}
                                className="rounded-[8px] border border-border px-4 py-2 text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors font-inter"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ══ EDIT CONTACT MODAL ══ */}
            {editingContact && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div
                        className="absolute inset-0 bg-black/30 backdrop-blur-[2px]"
                        onClick={() => setEditingContact(null)}
                    />
                    <div
                        className="relative bg-white rounded-[16px] w-full max-w-md p-5 space-y-4 teeks-bubble-in"
                        style={{ boxShadow: "0 8px 32px rgba(0,0,0,0.14)" }}
                    >
                        <div className="flex items-center justify-between">
                            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                Edit contact
                            </p>
                            <button
                                type="button"
                                onClick={() => setEditingContact(null)}
                                className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <X size={16} />
                            </button>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <input
                                placeholder="Name *"
                                value={editContactFields.name}
                                onChange={(e) => setEditContactFields((p) => ({ ...p, name: e.target.value }))}
                                className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                            />
                            <input
                                placeholder="Email"
                                value={editContactFields.email}
                                onChange={(e) => setEditContactFields((p) => ({ ...p, email: e.target.value }))}
                                className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                            />
                            <input
                                placeholder="Role"
                                value={editContactFields.role}
                                onChange={(e) => setEditContactFields((p) => ({ ...p, role: e.target.value }))}
                                className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                            />
                            <input
                                placeholder="Organization"
                                value={editContactFields.organization}
                                onChange={(e) => setEditContactFields((p) => ({ ...p, organization: e.target.value }))}
                                className="rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                            />
                        </div>

                        <textarea
                            placeholder="Notes (optional)"
                            value={editContactFields.notes}
                            onChange={(e) => setEditContactFields((p) => ({ ...p, notes: e.target.value }))}
                            rows={2}
                            className="w-full resize-none rounded-[8px] border border-border px-3 py-2 text-sm font-inter focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary"
                        />

                        <div className="flex gap-2">
                            <button
                                type="button"
                                onClick={handleUpdateContact}
                                disabled={!editContactFields.name.trim() || updateContact.isPending}
                                className="rounded-[8px] bg-primary px-4 py-2 text-[13px] font-semibold text-white hover:bg-primary/90 active:scale-[0.97] transition-all disabled:opacity-40 font-inter"
                            >
                                {updateContact.isPending ? "Saving…" : "Save changes"}
                            </button>
                            <button
                                type="button"
                                onClick={() => setEditingContact(null)}
                                className="rounded-[8px] border border-border px-4 py-2 text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors font-inter"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}








