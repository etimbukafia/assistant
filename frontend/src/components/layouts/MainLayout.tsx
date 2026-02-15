"use client"

import React, { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Menu, Home, MessageSquare, Settings, LogOut, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { DonnaButton } from "@/components/ui/DonnaButton"
import { DonnaText } from "@/components/ui/DonnaText"
import { Separator } from "@/components/ui/separator"

interface MainLayoutProps {
    children: React.ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false)
    const pathname = usePathname()

    const NavItem = ({ href, icon: Icon, label }: { href: string; icon: any; label: string }) => {
        const isActive = pathname === href
        return (
            <Link href={href} passHref>
                <DonnaButton
                    variant={isActive ? "secondary" : "ghost"}
                    className={cn(
                        "w-full justify-start gap-3 text-base font-medium transition-all duration-200",
                        isActive ? "bg-copper/10 text-copper font-semibold shadow-sm" : "text-muted-foreground hover:bg-linen hover:text-obsidian"
                    )}
                    onClick={() => setIsSidebarOpen(false)}
                >
                    <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />
                    {label}
                </DonnaButton>
            </Link>
        )
    }

    const SidebarContent = () => (
        <div className="flex flex-col h-full py-6 px-4 bg-surface border-r border-border/40">
            {/* Brand */}
            <div className="mb-8 px-2 flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-auburn flex items-center justify-center shadow-md">
                    <span className="text-linen font-playfair font-bold text-lg">T</span>
                </div>
                <DonnaText variant="h3" className="text-xl tracking-tight text-auburn">Teeks</DonnaText>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1">
                <NavItem href="/dashboard" icon={Home} label="Inbox" />
                <NavItem href="/chat" icon={MessageSquare} label="Assistant" />
                <NavItem href="/settings" icon={Settings} label="Settings" />
            </nav>

            <Separator className="my-4 bg-border/60" />

            {/* User / Footer */}
            <div className="mt-auto px-2">
                <div className="flex items-center justify-between p-3 rounded-lg bg-linen border border-border/50 shadow-sm cursor-pointer hover:bg-white hover:shadow-card transition-all">
                    <div className="flex flex-col">
                        <DonnaText variant="caption" className="text-obsidian font-semibold">User Name</DonnaText>
                        <DonnaText variant="label" className="text-[10px] text-muted-foreground">Pro Plan</DonnaText>
                    </div>
                    <ChevronRight size={14} className="text-muted-foreground" />
                </div>
            </div>
        </div>
    )

    return (
        <div className="min-h-screen bg-linen flex">
            {/* Mobile Trigger */}
            <div className="md:hidden fixed top-4 left-4 z-50">
                <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
                    <SheetTrigger asChild>
                        <DonnaButton variant="linen" size="icon" className="shadow-card hover:shadow-card-hover border-transparent bg-white/80 backdrop-blur-sm">
                            <Menu size={20} className="text-auburn" />
                        </DonnaButton>
                    </SheetTrigger>
                    <SheetContent side="left" className="p-0 w-72 bg-surface text-foreground border-r border-border/40">
                        <SidebarContent />
                    </SheetContent>
                </Sheet>
            </div>

            {/* Desktop Sidebar */}
            <aside className="hidden md:block w-72 h-screen sticky top-0 bg-surface shadow-card z-30">
                <SidebarContent />
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 min-h-screen relative flex flex-col">
                {/* Top padding for mobile trigger spacing */}
                <div className="md:hidden h-16 w-full" />

                <div className="flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full animate-in fade-in duration-500 slide-in-from-bottom-2">
                    {children}
                </div>
            </main>
        </div>
    )
}
