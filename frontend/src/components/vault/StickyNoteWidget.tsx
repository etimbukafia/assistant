"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { StickyNote, X, Check, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useDiaryMutations } from "@/hooks/useVault"
import { useMentionComposer } from "@/hooks/useMentionComposer"
import {
    CONTEXT_CAPTURE_MAX_CHARS,
    type DiaryCaptureScopeType,
} from "@/services/vault"

// Sticky note paper palettes — physical-object material metaphor.
// These are not brand colours; justified exception to the no-hardcoded-values rule.
// Each entry: [gradientFrom, gradientTo, tapeRgba]
const NOTE_PALETTES: [string, string, string][] = [
    ["#fefce8", "#fef9c2", "rgba(254,252,232,0.85)"], // yellow  — classic
    ["#fdf2f8", "#fce7f3", "rgba(253,242,248,0.85)"], // rose    — pink note
    ["#f0fdf4", "#dcfce7", "rgba(240,253,244,0.85)"], // mint    — green note
    ["#f0f9ff", "#e0f2fe", "rgba(240,249,255,0.85)"], // sky     — blue note
    ["#faf5ff", "#f3e8ff", "rgba(250,245,255,0.85)"], // lavender
    ["#fff7ed", "#ffedd5", "rgba(255,247,237,0.85)"], // peach   — orange note
]

// ── StickyNoteWidget ────────────────────────────────────────────────────────
//
// Floating quick-capture widget for capturing context from any
// screen. Sits above the OmniChat FAB in the bottom-right corner.
//
// Design decisions:
// - FAB uses ghost/secondary styling — Peony is reserved for the chat FAB
//   (Peony appears once per screen, per design system)
// - Save button uses `bg-secondary` (Brass, #A07850) — secondary interactive token
// - Note paper colour is randomised on each open from NOTE_PALETTES — justified
//   exception to the no-hardcoded-values rule (physical sticky-note metaphor)
// - Touch target: 48×48pt (h-12 w-12) — design system minimum
//
export function StickyNoteWidget() {
    const [isOpen, setIsOpen]   = React.useState(false)
    const [content, setContent] = React.useState("")
    const [selectedScopeKey, setSelectedScopeKey] = React.useState("global")
    // Palette is picked once per open; stable for the lifetime of that session
    const [palette, setPalette] = React.useState(NOTE_PALETTES[0])

    const panelRef    = React.useRef<HTMLDivElement>(null)
    const textareaRef = React.useRef<HTMLTextAreaElement>(null)
    const pathname    = usePathname()
    const isChatRoute =
        pathname === "/chat" ||
        pathname.startsWith("/dashboard/chat")

    const { createEntry } = useDiaryMutations()

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
        sessionId: "sticky-note",
    })

    const showDropdown = Boolean(mentionContext || loadingSuggestions)
    const scopeOptions = React.useMemo(() => {
        const options: Array<{
            key: string
            label: string
            scopeType: DiaryCaptureScopeType
            scopeId: string | null
            linkedTo: string | null
        }> = [
            { key: "global", label: "Global", scopeType: "global", scopeId: null, linkedTo: null },
        ]

        for (const mention of selectedMentions) {
            if (!["contact", "message", "event", "task"].includes(mention.kind)) continue
            options.push({
                key: `${mention.kind}:${mention.ref}`,
                label: `${mention.kind[0].toUpperCase()}${mention.kind.slice(1)}: ${mention.label}`,
                scopeType: mention.kind as DiaryCaptureScopeType,
                scopeId: mention.ref,
                linkedTo: mention.label,
            })
        }

        return options
    }, [selectedMentions])
    const selectedScope = React.useMemo(
        () => scopeOptions.find((option) => option.key === selectedScopeKey) ?? scopeOptions[0],
        [scopeOptions, selectedScopeKey],
    )

    // Close panel on outside click
    React.useEffect(() => {
        if (!isOpen) return
        const handler = (e: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
                setIsOpen(false)
            }
        }
        document.addEventListener("mousedown", handler)
        return () => document.removeEventListener("mousedown", handler)
    }, [isOpen])

    // Focus textarea when panel opens
    React.useEffect(() => {
        if (isOpen) {
            const t = setTimeout(() => textareaRef.current?.focus(), 80)
            return () => clearTimeout(t)
        }
    }, [isOpen])

    const handleSave = React.useCallback(async () => {
        const trimmed = content.trim()
        if (!trimmed || createEntry.isPending) return
        if (trimmed.length > CONTEXT_CAPTURE_MAX_CHARS) {
            toast.error(`Keep captures under ${CONTEXT_CAPTURE_MAX_CHARS} characters.`)
            return
        }

        const links = parseMentions(trimmed).map((m) => ({
            entity_type: m.kind,
            entity_id: m.ref,
            display_name: m.label,
            source: "user" as const,
        }))

        try {
            await createEntry.mutateAsync({
                text: trimmed,
                scope_type: selectedScope.scopeType,
                scope_id: selectedScope.scopeId,
                linked_to: selectedScope.linkedTo,
                links,
            })
            setContent("")
            setSelectedScopeKey("global")
            clearMentionState()
            setIsOpen(false)
            toast("Saved. Organizing.")
        } catch {
            toast.error("That didn't save. Try again.")
        }
    }, [content, createEntry, parseMentions, clearMentionState, selectedScope])

    const handleKeyDown = React.useCallback(
        (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
            // Let mention composer handle arrow/enter/escape navigation first
            onInputKeyDown(e)
            // Only trigger save if no suggestion list is open
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !mentionSuggestions.length) {
                e.preventDefault()
                handleSave()
            }
            if (e.key === "Escape" && !mentionSuggestions.length) setIsOpen(false)
        },
        [handleSave, onInputKeyDown, mentionSuggestions.length],
    )

    // Mirror OmniChatOverlay route exclusions
    if (
        pathname.startsWith("/dashboard/vault") ||
        pathname.startsWith("/dashboard/diary") ||
        pathname.startsWith("/dashboard/remember") ||
        pathname === "/login" ||
        pathname.startsWith("/auth")
    ) return null

    return (
        // On chat route, this is the only floating control; elsewhere it stacks above chat FAB.
        <div
            ref={panelRef}
            className={cn(
                "fixed right-6 z-50 w-14 flex justify-center",
                isChatRoute ? "bottom-6" : "bottom-[5.5rem]"
            )}
        >

            {/* ── Sticky note panel ─────────────────────────────────────────── */}
            {isOpen && (
                <div
                    className={cn(
                        "absolute bottom-full mb-2 right-0",
                        "w-72",
                        // Sticky notes have virtually no radius — they're paper
                        "rounded-[3px]",
                        "flex flex-col overflow-hidden",
                        // Enter from below-right (near FAB)
                        "origin-bottom-right",
                        "animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-2 duration-200",
                    )}
                    style={{
                        background: `linear-gradient(170deg, ${palette[0]} 0%, ${palette[1]} 100%)`,
                        boxShadow: [
                            "3px 6px 20px rgba(0,0,0,0.20)",
                            "0 1px 3px  rgba(0,0,0,0.10)",
                            "inset 0 1px 0 rgba(255,255,255,0.55)",
                        ].join(", "),
                    }}
                >
                    {/* Tape strip — purely decorative, conveys the "pinned" metaphor */}
                    <div
                        aria-hidden
                        className="absolute -top-[10px] left-1/2 -translate-x-1/2 w-10 h-[14px] rounded-[2px]"
                        style={{
                            background: palette[2],
                            boxShadow: "0 1px 2px rgba(0,0,0,0.12)",
                            border: "1px solid rgba(0,0,0,0.07)",
                        }}
                    />

                    {/* Header */}
                    <div className="px-3.5 pt-5 pb-0.5 space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-[9px] font-bold uppercase tracking-[1.6px] font-inter text-stone/60 select-none">
                                Capture Context
                            </span>
                            <button
                                type="button"
                                onClick={() => setIsOpen(false)}
                                aria-label="Close note"
                                className="p-0.5 rounded text-stone/50 hover:text-foreground transition-colors"
                            >
                                <X size={13} strokeWidth={2} />
                            </button>
                        </div>
                        <p className="text-[11px] leading-relaxed text-stone/60 font-inter">
                            Capture the moment. Teeks will organize it after you save.
                        </p>
                    </div>

                    {/* Content textarea + mention dropdown */}
                    <div className="relative mx-3.5 mt-2">
                        <textarea
                            ref={textareaRef}
                            id={listboxId + "-input"}
                            role="combobox"
                            aria-autocomplete="list"
                            aria-expanded={showDropdown}
                            aria-controls={listboxId}
                            aria-activedescendant={
                                mentionSuggestions[activeSuggestionIndex]
                                    ? `${listboxId}-option-${activeSuggestionIndex}`
                                    : undefined
                            }
                            value={content}
                            onChange={(e) => {
                                const value = e.target.value
                                const cursor = e.target.selectionStart ?? value.length
                                onInputChange(value, cursor)
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder="Capture what matters in plain language. @mention supporting context if it helps."
                            rows={4}
                            className={cn(
                                "w-full resize-none rounded-sm px-2 py-1.5",
                                "text-[13px] leading-relaxed text-foreground font-inter",
                                "bg-transparent border-none outline-none",
                                "placeholder:text-stone/40",
                                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50",
                            )}
                        />

                        {/* Mention suggestions dropdown — opens below textarea */}
                        {showDropdown && (
                            <div
                                id={listboxId}
                                role="listbox"
                                className="absolute top-full left-0 right-0 z-50 mt-0.5 rounded-[10px] border border-border bg-card shadow-md max-h-40 overflow-y-auto overscroll-contain"
                            >
                                {loadingSuggestions ? (
                                    <div className="px-3 py-2 text-xs text-muted-foreground font-inter" aria-live="polite">
                                        Loading…
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
                                                "w-full px-3 py-2 text-left text-xs font-inter hover:bg-muted/40 transition-colors",
                                                index === activeSuggestionIndex && "bg-muted/40 ring-1 ring-inset ring-primary/20",
                                            )}
                                            onMouseDown={(e) => { e.preventDefault(); applySuggestion(suggestion) }}
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="font-medium text-foreground">{suggestion.display}</span>
                                                <span className="text-[10px] uppercase tracking-wide text-muted-foreground border border-border/60 rounded-full px-1.5 py-0.5">
                                                    {suggestion.kind}
                                                </span>
                                            </div>
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

                    {/* Ruled lines — decorative, reinforces the paper metaphor */}
                    <div className="mx-3.5 mt-1 mb-3 flex flex-col gap-[9px] pointer-events-none" aria-hidden>
                        {[0, 1, 2].map((i) => (
                            <div key={i} className="h-px bg-stone/15" />
                        ))}
                    </div>

                    {/* Scope selector */}
                    <div className="px-3.5 pb-3">
                        <p className="text-[8.5px] font-bold uppercase tracking-widest font-inter text-stone/50 mb-1.5 select-none">
                            Save To
                        </p>
                        <p className="text-[10px] font-inter text-stone/55 mb-2 leading-relaxed">
                            Choose where this lives. Teeks will categorize it after you save.
                        </p>
                        <select
                            value={selectedScope.key}
                            onChange={(e) => setSelectedScopeKey(e.target.value)}
                            className="w-full rounded-[10px] border border-stone/20 bg-white/80 px-2.5 py-1.5 text-[11px] font-medium font-inter text-stone/80 focus:outline-none focus:ring-1 focus:ring-secondary/40"
                        >
                            {scopeOptions.map((option) => (
                                <option key={option.key} value={option.key}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Footer — hint + save */}
                    <div className="flex items-center justify-between px-3.5 pb-3.5 pt-2 border-t border-stone/15">
                        <span className="text-[10px] font-inter text-stone/45 select-none">
                            {content.length}/{CONTEXT_CAPTURE_MAX_CHARS}
                        </span>
                        {/* Save button uses Brass (--secondary) — not Peony, which belongs to OmniChat */}
                        <button
                            type="button"
                            onClick={handleSave}
                            disabled={!content.trim() || createEntry.isPending}
                            className={cn(
                                "h-7 px-3 rounded-full",
                                "text-[11px] font-semibold font-inter",
                                "bg-secondary text-secondary-foreground",
                                "hover:opacity-90 active:scale-[0.96] transition-all",
                                "disabled:opacity-35 disabled:pointer-events-none",
                                "flex items-center gap-1.5",
                                "shadow-sm",
                            )}
                        >
                            {createEntry.isPending
                                ? <Loader2 size={11} className="animate-spin" />
                                : <Check size={11} strokeWidth={2.5} />
                            }
                            Capture
                        </button>
                    </div>
                </div>
            )}

            {/* ── FAB trigger ───────────────────────────────────────────────── */}
            {/* h-12 w-12 = 48px — design system minimum touch target */}
            {/* Ghost/secondary styling — Peony is reserved for the chat FAB   */}
            <button
                type="button"
                aria-label={isOpen ? "Close note" : "Capture context"}
                onClick={() => {
                    if (!isOpen) {
                        // Pick a new random palette each time the note opens
                        const idx = Math.floor(Math.random() * NOTE_PALETTES.length)
                        setPalette(NOTE_PALETTES[idx])
                    }
                    setIsOpen((v) => !v)
                }}
                className={cn(
                    "h-12 w-12 rounded-full",
                    "flex items-center justify-center",
                    "transition-all duration-150",
                    "active:scale-[0.94]",
                    "border",
                    isOpen
                        ? "bg-secondary/15 text-secondary border-secondary/40 shadow-sm"
                        : "bg-[#fef08a] text-amber-800 border-amber-300/60 hover:bg-[#fde047]",
                    "shadow-[0_2px_8px_rgba(0,0,0,0.10),0_1px_2px_rgba(0,0,0,0.06)]",
                )}
            >
                {isOpen
                    ? <X size={17} strokeWidth={1.8} />
                    : <StickyNote size={17} strokeWidth={1.8} />
                }
            </button>
        </div>
    )
}


