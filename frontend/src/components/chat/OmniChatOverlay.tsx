"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { MessageSquare, X, Send, Sparkles, Loader2 } from "lucide-react"

import { Dialog, DialogContent, DialogTrigger, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { DonnaButton } from "@/components/ui/DonnaButton"
import { DonnaText } from "@/components/ui/DonnaText"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
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
    return "border-auburn/30 bg-auburn/[0.06] text-auburn"
}

export function OmniChatOverlay() {
    const { isOpen, setIsOpen, mode } = useChatContext()
    const {
        currentSessionId,
        sendMessage,
        createSession,
        isSending,
        isCreating,
    } = useChat()

    // Updated hook utilization to get pendingActions
    const { data: messages, pendingActions } = useChatMessages(currentSessionId)

    const [inputValue, setInputValue] = React.useState("")
    const scrollRef = React.useRef<HTMLDivElement>(null)
    const inputRef = React.useRef<HTMLInputElement>(null)
    const pathname = usePathname()

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

    // Auto-scroll to bottom when messages change
    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [messages, pendingActions, isSending])

    const selectedInlineMentions = React.useMemo(() => {
        if (!inputValue.trim()) return []
        return parseMentions(inputValue)
    }, [inputValue, parseMentions])

    const removeInlineMention = React.useCallback((kind: string, label: string) => {
        const token = `${kind === "memory" ? "/" : "@"}${label}`
        setInputValue((prev) => prev.replace(token, "").replace(/\s{2,}/g, " ").trimStart())
    }, [])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!inputValue.trim() || isSending || isCreating) return

        const content = inputValue.trim()
        const mentions = parseMentions(content)
        setInputValue("") // Optimistic clear
        clearMentionState()

        try {
            if (!currentSessionId) {
                // First create a session, then send the message to it.
                const session = await createSession({ mode })
                await sendMessage({ session_id: session.id, content, mode, mentions })
                trackUIEvent("chat_message_sent", {
                    has_mentions: mentions.length > 0,
                    mention_count: mentions.length,
                    source: "overlay",
                })
            } else {
                await sendMessage({ session_id: currentSessionId, content, mode, mentions })
                trackUIEvent("chat_message_sent", {
                    has_mentions: mentions.length > 0,
                    mention_count: mentions.length,
                    source: "overlay",
                })
            }
        } catch {
            toast.error("Failed to send message")
            setInputValue(content) // Restore on error
        }
    }

    // Don't show overlay if already on a dedicated chat page or auth pages
    if (pathname === "/chat" ||
        pathname.startsWith("/dashboard/chat") ||
        pathname === "/login" ||
        pathname.startsWith("/auth")) return null

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
                <DonnaButton
                    variant="default" // Auburn
                    size="icon"
                    className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-card-hover hover:scale-105 transition-transform z-50"
                    onClick={() => setIsOpen(true)}
                >
                    <MessageSquare className="h-6 w-6 text-linen" />
                </DonnaButton>
            </DialogTrigger>

            {/* Vellum Overlay Content */}
            <DialogContent
                className="sm:max-w-[500px] h-[80vh] flex flex-col p-0 gap-0 border-border/40 shadow-2xl bg-white/95 backdrop-blur-sm"
                // Override default dialog overlay to be lighter/vellum
                overlayClassName="bg-white/60 backdrop-blur-[2px]"
                onInteractOutside={(e) => e.preventDefault()} // Prevent closing when interacting outside heavily
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-border/40 bg-linen/50">
                    <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-full bg-auburn flex items-center justify-center">
                            <Sparkles size={16} className="text-linen" />
                        </div>
                        <div>
                            <DialogTitle className="font-playfair text-lg text-auburn font-semibold">Teeks</DialogTitle>
                            <DialogDescription className="sr-only">Chat with Teeks assistant</DialogDescription>
                            <DonnaText variant="label" className="text-[10px] text-muted-foreground/80">
                                {mode === 'action' ? 'Action Mode' : 'Reflection Mode'}
                            </DonnaText>
                        </div>
                    </div>
                    <DonnaButton variant="ghost" size="icon" onClick={() => setIsOpen(false)} className="h-8 w-8 text-muted-foreground hover:text-auburn">
                        <X size={18} />
                    </DonnaButton>
                </div>

                {/* Chat Area */}
                <ScrollArea className="flex-1 p-4 bg-linen/20">
                    <div className="flex flex-col gap-4 min-h-full">
                        {!currentSessionId && messages?.length === 0 && (
                            <div className="flex flex-col items-center justify-center flex-1 mt-20 opacity-60">
                                <Sparkles size={32} className="text-copper mb-3" />
                                <DonnaText variant="h4" className="text-muted-foreground text-base">How can I help you clear your desk?</DonnaText>
                            </div>
                        )}

                        {messages?.map((msg) => (
                            <div key={msg.id} className="flex flex-col">
                                <MessageBubble
                                    role={msg.role}
                                    content={msg.content}
                                    timestamp={msg.created_at}
                                />
                            </div>
                        ))}

                        {(isSending || isCreating) && (
                            <div className="flex justify-start mb-4">
                                <div className="bg-white border border-border/40 rounded-2xl rounded-tl-sm p-3 shadow-sm flex items-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin text-auburn" />
                                    <span className="text-sm text-muted-foreground">Teeks is thinking...</span>
                                </div>
                            </div>
                        )}
                        <div ref={scrollRef} />
                    </div>
                </ScrollArea>

                {/* Input Area */}
                <div className="p-4 bg-white border-t border-border/40">
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
                                })
                                trackUIEvent("chat_approval_sent", {
                                    source: "overlay",
                                    pending_count: pendingActions.length,
                                })
                            }}
                        />
                    )}

                    {selectedInlineMentions.length > 0 && (
                        <div className="mb-2.5 flex flex-wrap gap-1.5">
                            {selectedInlineMentions.map((mention) => (
                                <span
                                    key={`${mention.kind}:${mention.ref}`}
                                    className={cn(
                                        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium",
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
                                        <X size={12} />
                                    </button>
                                </span>
                            ))}
                        </div>
                    )}
                    <form className="flex gap-2" onSubmit={handleSubmit}>
                        <div className="relative flex-1">
                            <Input
                                ref={inputRef}
                                aria-label="Chat message input"
                                placeholder="Ask Teeks to draft specific..."
                                className="flex-1 bg-linen border-border focus-visible:ring-auburn/20 font-inter"
                                value={inputValue}
                                role="combobox"
                                aria-autocomplete="list"
                                aria-expanded={Boolean(mentionContext || loadingSuggestions)}
                                aria-controls={listboxId}
                                aria-activedescendant={mentionSuggestions[activeSuggestionIndex] ? `${listboxId}-option-${activeSuggestionIndex}` : undefined}
                                onChange={(e) => {
                                    const value = e.target.value
                                    const cursor = e.target.selectionStart ?? value.length
                                    onInputChange(value, cursor)
                                }}
                                onKeyDown={onInputKeyDown}
                                disabled={isSending || isCreating}
                            />
                            {(mentionContext || loadingSuggestions) && (
                                <div
                                    id={listboxId}
                                    role="listbox"
                                    className="absolute left-0 right-0 top-full z-50 mt-1 rounded-md border border-border/60 bg-white shadow-md max-h-72 overflow-y-auto overscroll-contain"
                                >
                                    {loadingSuggestions ? (
                                        <div className="px-3 py-2 text-xs text-muted-foreground" aria-live="polite">Loading mentions...</div>
                                    ) : mentionSuggestions.length > 0 ? (
                                        mentionSuggestions.map((suggestion, index) => (
                                            <button
                                                id={`${listboxId}-option-${index}`}
                                                key={suggestion.key}
                                                type="button"
                                                role="option"
                                                aria-selected={index === activeSuggestionIndex}
                                                className={`w-full px-3 py-2 text-left text-xs hover:bg-linen/80 ${index === activeSuggestionIndex ? "bg-linen outline-none ring-1 ring-auburn/30" : ""
                                                    }`}
                                                onMouseDown={(evt) => {
                                                    evt.preventDefault()
                                                    applySuggestion(suggestion)
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
                        <DonnaButton
                            type="submit"
                            size="icon"
                            variant="secondary"
                            className="shrink-0"
                            disabled={!inputValue.trim() || isSending || isCreating}
                        >
                            {isSending || isCreating ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                        </DonnaButton>
                    </form>
                </div>
            </DialogContent>
        </Dialog>
    )
}
