"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { MessageSquare, X, Send, Sparkles } from "lucide-react"

import { cn } from "@/lib/utils"
import { Dialog, DialogContent, DialogTrigger, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { DonnaButton } from "@/components/ui/DonnaButton"
import { DonnaText } from "@/components/ui/DonnaText"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"

export function OmniChatOverlay() {
    const [isOpen, setIsOpen] = React.useState(false)
    const pathname = usePathname()

    // Don't show overlay if already on the dedicated /chat page
    if (pathname === "/chat") return null

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
                <DonnaButton
                    variant="default" // Auburn
                    size="icon"
                    className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-card-hover hover:scale-105 transition-transform z-50"
                >
                    <MessageSquare className="h-6 w-6 text-linen" />
                </DonnaButton>
            </DialogTrigger>

            {/* Vellum Overlay Content */}
            <DialogContent
                className="sm:max-w-[500px] h-[80vh] flex flex-col p-0 gap-0 border-border/40 shadow-2xl bg-white/95 backdrop-blur-sm"
                // Override default dialog overlay to be lighter/vellum
                overlayClassName="bg-white/60 backdrop-blur-[2px]"
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
                                Ready to assist
                            </DonnaText>
                        </div>
                    </div>
                    <DonnaButton variant="ghost" size="icon" onClick={() => setIsOpen(false)} className="h-8 w-8 text-muted-foreground hover:text-auburn">
                        <X size={18} />
                    </DonnaButton>
                </div>

                {/* Chat Area (Placeholder) */}
                <ScrollArea className="flex-1 p-4 bg-linen/20">
                    <div className="flex flex-col gap-4">
                        {/* Empty State */}
                        <div className="flex flex-col items-center justify-center h-full mt-20 opacity-60">
                            <Sparkles size={32} className="text-copper mb-3" />
                            <DonnaText variant="h4" className="text-muted-foreground text-base">How can I help you clear your desk?</DonnaText>
                        </div>
                    </div>
                </ScrollArea>

                {/* Input Area */}
                <div className="p-4 bg-white border-t border-border/40">
                    <form className="flex gap-2" onSubmit={(e) => e.preventDefault()}>
                        <Input
                            placeholder="Ask Teeks to draft specific..."
                            className="flex-1 bg-linen border-border focus-visible:ring-auburn/20 font-inter"
                        />
                        <DonnaButton type="submit" size="icon" variant="secondary" className="shrink-0">
                            <Send size={18} />
                        </DonnaButton>
                    </form>
                </div>
            </DialogContent>
        </Dialog>
    )
}
