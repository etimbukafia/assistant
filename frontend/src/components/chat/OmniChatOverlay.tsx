"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { MessageSquare, X, Send, Sparkles, Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"
import { Dialog, DialogContent, DialogTrigger, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { DonnaButton } from "@/components/ui/DonnaButton"
import { DonnaText } from "@/components/ui/DonnaText"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useChatContext } from "@/context/ChatContext"
import { useChat, useChatMessages } from "@/hooks/useChat"
import { MessageBubble } from "./MessageBubble"
import { ActionBubble } from "./ActionBubble"
import { toast } from "sonner"

export function OmniChatOverlay() {
    const { isOpen, setIsOpen, mode } = useChatContext()
    const {
        currentSessionId,
        sendMessage,
        createSession,
        approveAction,
        rejectAction,
        isSending,
        isCreating,
        isApproving,
        isRejecting
    } = useChat()

    // Updated hook utilization to get pendingActions
    const { data: messages, pendingActions, isLoading: isLoadingMessages } = useChatMessages(currentSessionId)

    const [inputValue, setInputValue] = React.useState("")
    const scrollRef = React.useRef<HTMLDivElement>(null)
    const pathname = usePathname()

    // Auto-scroll to bottom when messages change
    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [messages, pendingActions, isSending])

    // Don't show overlay if already on the dedicated /chat page
    if (pathname === "/chat") return null

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!inputValue.trim() || isSending || isCreating) return

        const content = inputValue.trim()
        setInputValue("") // Optimistic clear

        try {
            if (!currentSessionId) {
                // First message creates the session
                await createSession({ initial_message: content, mode })
            } else {
                await sendMessage({ session_id: currentSessionId, content, mode })
            }
        } catch (error) {
            toast.error("Failed to send message")
            setInputValue(content) // Restore on error
        }
    }

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

                        {messages?.map((msg) => {
                            // Find corresponding action for this message
                            const action = pendingActions?.find(a => a.message_id === Number(msg.id));

                            return (
                                <div key={msg.id} className="flex flex-col">
                                    <MessageBubble
                                        role={msg.role}
                                        content={msg.content}
                                        timestamp={msg.created_at}
                                    />
                                    {action && currentSessionId && (
                                        <ActionBubble
                                            action={action}
                                            onApprove={(id) => approveAction({ sessionId: currentSessionId, actionId: id })}
                                            onReject={(id) => rejectAction({ sessionId: currentSessionId, actionId: id })}
                                            isApproving={isApproving}
                                            isRejecting={isRejecting}
                                        />
                                    )}
                                </div>
                            );
                        })}

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
                    <form className="flex gap-2" onSubmit={handleSubmit}>
                        <Input
                            placeholder="Ask Teeks to draft specific..."
                            className="flex-1 bg-linen border-border focus-visible:ring-auburn/20 font-inter"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            disabled={isSending || isCreating}
                        />
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
