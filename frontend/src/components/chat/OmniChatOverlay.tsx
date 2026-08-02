"use client"

import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { usePathname } from "next/navigation"
import { ArrowUp, MessageSquare, Plus, X } from "lucide-react"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { useChatContext } from "@/context/ChatContext"
import { useChat, useChatMessages } from "@/hooks/useChat"
import { trackUIEvent } from "@/services/telemetry"
import { MessageBubble } from "./MessageBubble"
import { ApprovalGateComposer } from "./ApprovalGateComposer"
import { toast } from "sonner"
import { useMentionComposer } from "@/hooks/useMentionComposer"
import { cn } from "@/lib/utils"

function mentionToneClass(kind: "contact" | "thread" | "event" | "task" | "memory"): string {
    if (kind === "memory") return "border-amber-300/70 bg-amber-50 text-amber-900"
    if (kind === "contact") return "border-sky-300/70 bg-sky-50 text-sky-900"
    if (kind === "event") return "border-emerald-300/70 bg-emerald-50 text-emerald-900"
    if (kind === "thread") return "border-violet-300/70 bg-violet-50 text-violet-900"
    if (kind === "task") return "border-rose-300/70 bg-rose-50 text-rose-900"
    return "border-primary/30 bg-primary/[0.06] text-primary"
}

export function OmniChatOverlay() {
    const { isOpen, setIsOpen, mode } = useChatContext()
    const { currentSessionId, sendMessage, createSession, isSending, isCreating } = useChat()
    const pathname  = usePathname()
    const isChatSurfaceRoute =
        pathname === "/chat" ||
        pathname.startsWith("/dashboard/chat") ||
        pathname === "/login" ||
        pathname.startsWith("/auth")
    const { data: messages, pendingActions } = useChatMessages(isChatSurfaceRoute ? null : currentSessionId)

    const [inputValue, setInputValue] = React.useState("")
    const scrollRef = React.useRef<HTMLDivElement>(null)
    const inputRef  = React.useRef<HTMLTextAreaElement>(null)
    const adjustComposerHeight = React.useCallback(() => {
        const el = inputRef.current
        if (!el) return
        const minPx = 40
        const maxPx = 220
        el.style.height = "auto"
        const next = Math.min(Math.max(el.scrollHeight, minPx), maxPx)
        el.style.height = `${next}px`
        el.style.overflowY = el.scrollHeight > maxPx ? "auto" : "hidden"
    }, [])

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
            trackUIEvent("mention_selected", { mention_type: mention.kind, source: "overlay" })
        },
    })

    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: "smooth" })
        }
    }, [messages, pendingActions, isSending])

    React.useEffect(() => {
        adjustComposerHeight()
    }, [inputValue, adjustComposerHeight])

    // Focus input as soon as the panel is open
    React.useEffect(() => {
        if (isOpen) {
            const t = setTimeout(() => inputRef.current?.focus(), 80)
            return () => clearTimeout(t)
        }
    }, [isOpen])

    const selectedInlineMentions = React.useMemo(() => {
        if (!inputValue.trim()) return []
        return parseMentions(inputValue)
    }, [inputValue, parseMentions])

    const removeInlineMention = React.useCallback((kind: string, label: string) => {
        const token = `${kind === "memory" ? "/" : "@"}${label}`
        setInputValue((prev) => prev.replace(token, "").replace(/\s{2,}/g, " ").trimStart())
    }, [])

    const submitCurrentMessage = React.useCallback(async () => {
        if (!inputValue.trim() || isSending || isCreating) return

        const content = inputValue.trim()
        const mentions = parseMentions(content)
        setInputValue("")
        clearMentionState()

        try {
            if (!currentSessionId) {
                const session = await createSession({ mode })
                await sendMessage({ session_id: session.id, content, mode, mentions })
            } else {
                await sendMessage({ session_id: currentSessionId, content, mode, mentions })
            }
            trackUIEvent("chat_message_sent", {
                has_mentions: mentions.length > 0,
                mention_count: mentions.length,
                source: "overlay",
            })
        } catch {
            toast.error("That didn't send. Try again.")
            setInputValue(content)
        }
    }, [
        clearMentionState,
        createSession,
        currentSessionId,
        inputValue,
        isCreating,
        isSending,
        mode,
        parseMentions,
        sendMessage,
    ])

    const handleSubmit = React.useCallback(async (e: React.FormEvent) => {
        e.preventDefault()
        await submitCurrentMessage()
    }, [submitCurrentMessage])

    const handleComposerKeyDown = React.useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        onInputKeyDown(e)
        if (e.defaultPrevented) return
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            const target = e.currentTarget
            const start = target.selectionStart ?? target.value.length
            const end = target.selectionEnd ?? start
            setInputValue((prev) => `${prev.slice(0, start)}\n${prev.slice(end)}`)
            requestAnimationFrame(() => {
                inputRef.current?.focus()
                inputRef.current?.setSelectionRange(start + 1, start + 1)
                adjustComposerHeight()
            })
            return
        }
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            void submitCurrentMessage()
        }
    }, [onInputKeyDown, submitCurrentMessage, adjustComposerHeight])

    const handleCreateNewSession = React.useCallback(async () => {
        if (isSending || isCreating) return
        try {
            await createSession({ mode })
            setInputValue("")
            clearMentionState()
            inputRef.current?.focus()
        } catch {
            toast.error("Couldn't start a new session right now.")
        }
    }, [clearMentionState, createSession, isCreating, isSending, mode])

    if (isChatSurfaceRoute) return null

    return (
        <DialogPrimitive.Root open={isOpen} onOpenChange={setIsOpen}>

            {/* ── FAB trigger — Peony, bottom-right ── */}
            <DialogPrimitive.Trigger asChild>
                <button
                    aria-label={isOpen ? "Close memory reflection" : "Open Memory Reflection Space"}
                    className={cn(
                        "fixed bottom-6 right-6 z-50",
                        "h-14 w-14 rounded-full",
                        "bg-primary text-white",
                        "flex items-center justify-center",
                        "shadow-[0_4px_20px_rgba(194,24,91,0.30)]",
                        "transition-all duration-150",
                        "hover:bg-primary/90 active:scale-[0.94]",
                    )}
                >
                    {isOpen
                        ? <X size={20} strokeWidth={2} />
                        : <MessageSquare size={20} strokeWidth={1.8} />
                    }
                </button>
            </DialogPrimitive.Trigger>

            <DialogPrimitive.Portal>

                {/* Barely-there backdrop — 10% black, not 80% */}
                <DialogPrimitive.Overlay className={cn(
                    "fixed inset-0 z-50 bg-black/10",
                    "data-[state=open]:animate-in  data-[state=open]:fade-in-0",
                    "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
                    "duration-200",
                )} />

                {/* ── Floating panel — bottom-right, drops in from below ── */}
                <DialogPrimitive.Content
                    style={{
                        boxShadow: "0 12px 40px rgba(0,0,0,0.14), 0 4px 12px rgba(0,0,0,0.08)",
                    }}
                    className={cn(
                        // Position — sits just above the FAB
                        "fixed bottom-24 right-6 z-50",
                        // Size
                        "w-[400px] h-[68vh] max-h-[640px]",
                        // Mobile: stretch edge-to-edge above FAB
                        "max-sm:left-3 max-sm:right-3 max-sm:w-auto max-sm:bottom-20",
                        // Surface — frosted glass per design spec
                        "bg-white/92 backdrop-blur-xl",
                        "border border-white/50",
                        "rounded-[20px]",
                        // Layout
                        "flex flex-col overflow-hidden",
                        // Animation — scale from bottom-right corner (near FAB)
                        "origin-bottom-right",
                        "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-bottom-2",
                        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:slide-out-to-bottom-2",
                        "duration-200",
                    )}
                >
                    <DialogPrimitive.Title className="sr-only">Memory Reflection Space</DialogPrimitive.Title>
                    <DialogPrimitive.Description className="sr-only">Quick memory reflection with Teeks</DialogPrimitive.Description>

                    {/* ── Header ── */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 flex-shrink-0">
                        <div className="flex items-center gap-2.5">
                            {/* Logo mark */}
                            <span className="w-7 h-7 bg-primary rounded-[6px] flex items-center justify-center flex-shrink-0">
                                <span className="font-playfair font-bold text-[13px] text-white leading-none">T</span>
                            </span>
                            <span className="font-playfair font-semibold text-[16px] text-foreground tracking-tight">
                                Memory Reflection
                            </span>
                        </div>
                        <div className="flex items-center gap-1">
                            <button
                                type="button"
                                onClick={() => void handleCreateNewSession()}
                                disabled={isCreating || isSending}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 px-2.5 py-1.5 text-[11px] font-medium font-inter text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors disabled:opacity-40"
                                aria-label="Create new memory reflection session"
                            >
                                <Plus size={13} strokeWidth={2} />
                                New space
                            </button>
                            <button
                                type="button"
                                onClick={() => setIsOpen(false)}
                                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                                aria-label="Close"
                            >
                                <X size={16} strokeWidth={1.8} />
                            </button>
                        </div>
                    </div>

                    {/* Messages */}
                    <ScrollArea className="flex-1 px-4 py-4">
                        <div className="flex flex-col gap-3 min-h-full">

                            {/* Empty state */}
                            {!messages?.length && !isSending && (
                                <div className="pt-6">
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter mb-2">
                                        {new Date().toLocaleDateString("en-US", {
                                            weekday: "long",
                                            month: "short",
                                            day: "numeric",
                                        })}
                                    </p>
                                    <p className="font-playfair text-[20px] font-semibold text-foreground tracking-tight leading-snug">
                                        What do you want to<br />remember or verify?
                                    </p>
                                </div>
                            )}

                            {messages?.map((msg) => {
                                const normalizedRoleRaw = String(msg.role || "").trim().toLowerCase()
                                const normalizedRole =
                                    normalizedRoleRaw === "assistant" || normalizedRoleRaw === "system"
                                        ? normalizedRoleRaw
                                        : "user"
                                return (
                                    <div key={msg.id} className="flex flex-col">
                                        <MessageBubble
                                            role={normalizedRole}
                                            content={msg.content}
                                            timestamp={msg.created_at}
                                        />
                                    </div>
                                )
                            })}

                            {/* Three-dot typing indicator — never a spinner */}
                            {(isSending || isCreating) && (
                                <div className="flex justify-start">
                                    <div className="bg-white border border-border rounded-2xl rounded-bl-[4px] px-4 py-3.5 flex items-center gap-1.5"
                                        style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.07)" }}>
                                        <span className="teeks-dot" style={{ animationDelay: "0ms" }} />
                                        <span className="teeks-dot" style={{ animationDelay: "200ms" }} />
                                        <span className="teeks-dot" style={{ animationDelay: "400ms" }} />
                                    </div>
                                </div>
                            )}

                            <div ref={scrollRef} />
                        </div>
                    </ScrollArea>

                    {/* ── Input area ── */}
                    <div className="px-4 pb-4 pt-2 flex-shrink-0 border-t border-border/50">

                        {currentSessionId && pendingActions?.length > 0 && (
                            <div className="mb-3">
                                <ApprovalGateComposer
                                    pendingActions={pendingActions}
                                    disabled={isSending || isCreating}
                                    onSendDecision={async (command) => {
                                        await sendMessage({
                                            session_id: currentSessionId,
                                            content: command,
                                            mode: "action",
                                            mentions: [],
                                        })
                                        trackUIEvent("chat_approval_sent", {
                                            source: "overlay",
                                            pending_count: pendingActions.length,
                                        })
                                    }}
                                />
                            </div>
                        )}

                        {selectedInlineMentions.length > 0 && (
                            <div className="mb-2 flex flex-wrap gap-1.5">
                                {selectedInlineMentions.map((mention) => (
                                    <span
                                        key={`${mention.kind}:${mention.ref}`}
                                        className={cn(
                                            "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium font-inter",
                                            mentionToneClass(mention.kind)
                                        )}
                                    >
                                        {mention.kind === "memory" ? "/" : "@"}{mention.label}
                                        <button
                                            type="button"
                                            className="opacity-70 hover:opacity-100"
                                            onClick={() => removeInlineMention(mention.kind, mention.label)}
                                            aria-label={`Remove ${mention.label}`}
                                        >
                                            <X size={11} />
                                        </button>
                                    </span>
                                ))}
                            </div>
                        )}

                        <form className="flex gap-2 items-end" onSubmit={handleSubmit}>
                            <div className="relative flex-1">
                                <Textarea
                                    ref={inputRef}
                                    aria-label="Chat message input"
                                    role="combobox"
                                    aria-autocomplete="list"
                                    aria-expanded={Boolean(mentionContext || loadingSuggestions)}
                                    aria-controls={listboxId}
                                    aria-activedescendant={
                                        mentionSuggestions[activeSuggestionIndex]
                                            ? `${listboxId}-option-${activeSuggestionIndex}`
                                            : undefined
                                    }
                                    placeholder="Ask about a person, capture, approval, preference, or prior discussion"
                                    value={inputValue}
                                    rows={1}
                                    onChange={(e) => {
                                        const value = e.target.value
                                        const cursor = e.target.selectionStart ?? value.length
                                        onInputChange(value, cursor)
                                        requestAnimationFrame(adjustComposerHeight)
                                    }}
                                    onKeyDown={handleComposerKeyDown}
                                    disabled={isSending || isCreating}
                                    className="min-h-[40px] text-[13px] leading-5 bg-background/80 border-border focus-visible:bg-white focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-primary/30 font-inter resize-none overflow-y-auto"
                                />

                                {/* Mention suggestions */}
                                {(mentionContext || loadingSuggestions) && (
                                    <div
                                        id={listboxId}
                                        role="listbox"
                                        className="absolute left-0 right-0 bottom-full z-50 mb-1 rounded-[10px] border border-border bg-white shadow-md max-h-48 overflow-y-auto overscroll-contain"
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
                                                        index === activeSuggestionIndex && "bg-muted/40 ring-1 ring-inset ring-primary/20"
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

                            {/* Send — Peony, always */}
                            <button
                                type="submit"
                                aria-label="Send message"
                                disabled={!inputValue.trim() || isSending || isCreating}
                                className="h-10 w-10 rounded-full bg-primary text-white flex items-center justify-center shrink-0 disabled:opacity-30 hover:bg-primary/90 active:scale-[0.94] transition-all shadow-sm"
                            >
                                <ArrowUp size={17} strokeWidth={2.5} />
                            </button>
                        </form>
                    </div>
                </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
    )
}
