"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { StickyNote, X, Check, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useDiaryMutations } from "@/hooks/useVault"
import type { DiaryEntryType } from "@/services/vault"

// Entry type config — mirrors vault/page.tsx TYPE_COLORS with token-safe classes
const TYPES: { value: DiaryEntryType; label: string; activeClass: string }[] = [
    { value: "risks",         label: "Risk",         activeClass: "bg-obsidian/80  text-white  border-obsidian/80" },
    { value: "decision",      label: "Decision",     activeClass: "bg-copper       text-white  border-copper" },
    { value: "commitment",    label: "Commitment",   activeClass: "bg-sage         text-white  border-sage" },
    { value: "preferences",   label: "Preference",   activeClass: "bg-teal         text-white  border-teal" },
    { value: "relationships", label: "Relationship", activeClass: "bg-burgundy     text-white  border-burgundy" },
]

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
// Floating quick-capture widget for pinning diary context entries from any
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
    const [type, setType]       = React.useState<DiaryEntryType>("risks")
    // Palette is picked once per open; stable for the lifetime of that session
    const [palette, setPalette] = React.useState(NOTE_PALETTES[0])

    const panelRef    = React.useRef<HTMLDivElement>(null)
    const textareaRef = React.useRef<HTMLTextAreaElement>(null)
    const pathname    = usePathname()

    const { createEntry } = useDiaryMutations()

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
        try {
            await createEntry.mutateAsync({
                type,
                content: trimmed,
                importance_level: "normal",
                links: [],
            })
            setContent("")
            setIsOpen(false)
            toast.success("Note pinned to Diary.")
        } catch {
            toast.error("That didn't save. Try again.")
        }
    }, [content, type, createEntry])

    const handleKeyDown = React.useCallback(
        (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault()
                handleSave()
            }
            if (e.key === "Escape") setIsOpen(false)
        },
        [handleSave],
    )

    // Mirror OmniChatOverlay route exclusions
    if (
        pathname === "/chat" ||
        pathname.startsWith("/dashboard/chat") ||
        pathname === "/login" ||
        pathname.startsWith("/auth")
    ) return null

    return (
        // Sits above the chat FAB — same right-6 column, 8pt above it
        <div ref={panelRef} className="fixed bottom-[5.5rem] right-6 z-50">

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
                    <div className="flex items-center justify-between px-3.5 pt-5 pb-0.5">
                        <span className="text-[9px] font-bold uppercase tracking-[1.6px] font-inter text-stone/60 select-none">
                            Quick note
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

                    {/* Content textarea — Ivory bg, Peony focus ring (standard input spec) */}
                    <textarea
                        ref={textareaRef}
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Capture a thought, decision, or risk."
                        rows={4}
                        className={cn(
                            "mx-3.5 mt-2 resize-none rounded-sm px-2 py-1.5",
                            "text-[13px] leading-relaxed text-foreground font-inter",
                            "bg-transparent border-none outline-none",
                            "placeholder:text-stone/40",
                            // Peony focus ring — this is the accessibility focus affordance,
                            // not a decorative use; it applies to all inputs per design spec
                            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50",
                        )}
                    />

                    {/* Ruled lines — decorative, reinforces the paper metaphor */}
                    <div className="mx-3.5 mt-1 mb-3 flex flex-col gap-[9px] pointer-events-none" aria-hidden>
                        {[0, 1, 2].map((i) => (
                            <div key={i} className="h-px bg-stone/15" />
                        ))}
                    </div>

                    {/* Type selector */}
                    <div className="px-3.5 pb-3">
                        <p className="text-[8.5px] font-bold uppercase tracking-widest font-inter text-stone/50 mb-1.5 select-none">
                            Type
                        </p>
                        <div className="flex flex-wrap gap-1">
                            {TYPES.map((t) => (
                                <button
                                    key={t.value}
                                    type="button"
                                    onClick={() => setType(t.value)}
                                    className={cn(
                                        "px-2 py-[3px] rounded-full text-[10px] font-medium font-inter",
                                        "border transition-colors duration-150",
                                        type === t.value
                                            ? t.activeClass
                                            : "border-stone/25 text-stone/70 hover:border-stone/45 hover:text-foreground",
                                    )}
                                >
                                    {t.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Footer — hint + save */}
                    <div className="flex items-center justify-between px-3.5 pb-3.5 pt-2 border-t border-stone/15">
                        <span className="text-[10px] font-inter text-stone/45 select-none">⌘↵ to save</span>
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
                            Pin it
                        </button>
                    </div>
                </div>
            )}

            {/* ── FAB trigger ───────────────────────────────────────────────── */}
            {/* h-12 w-12 = 48px — design system minimum touch target */}
            {/* Ghost/secondary styling — Peony is reserved for the chat FAB   */}
            <button
                type="button"
                aria-label={isOpen ? "Close note" : "Capture a quick note"}
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
                        : "bg-card text-muted-foreground border-border hover:text-foreground hover:bg-muted/60",
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
