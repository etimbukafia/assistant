"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { DonnaButton } from "@/components/ui/DonnaButton";
import { DonnaText } from "@/components/ui/DonnaText";
import { DonnaCard, DonnaCardContent } from "@/components/ui/DonnaCard";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
    const { signInWithGoogle, loading } = useAuth();
    const [isSigningIn, setIsSigningIn] = useState(false);

    const handleSignIn = async () => {
        setIsSigningIn(true);
        try {
            await signInWithGoogle();
        } catch (error) {
            console.error("Sign in failed", error);
            setIsSigningIn(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-linen">
                <Loader2 className="h-8 w-8 animate-spin text-auburn" />
            </div>
        );
    }

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-linen">
            <div className="w-full max-w-md space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">

                {/* Brand Header */}
                <div className="text-center space-y-2">
                    <div className="mx-auto h-16 w-16 bg-auburn rounded-2xl flex items-center justify-center shadow-lg mb-6 rotate-3 hover:rotate-0 transition-transform duration-500">
                        <span className="text-linen font-playfair font-bold text-4xl">T</span>
                    </div>
                    <DonnaText variant="h1" className="text-4xl md:text-5xl text-auburn tracking-tight">
                        Teeks
                    </DonnaText>
                    <DonnaText variant="h3" className="text-xl md:text-2xl text-muted-foreground font-light italic">
                        Chaos Out. Clarity In.
                    </DonnaText>
                </div>

                {/* Auth Card */}
                <DonnaCard variant="interactive" className="bg-white/80 backdrop-blur-sm border-white/50 shadow-xl p-6 md:p-10">
                    <DonnaCardContent className="flex flex-col gap-6 pt-6">
                        <div className="space-y-2 text-center">
                            <DonnaText variant="h4" className="text-obsidian">
                                Welcome to your Desk
                            </DonnaText>
                            <DonnaText variant="body" className="text-sm">
                                Sign in to access your executive command center.
                            </DonnaText>
                        </div>

                        <DonnaButton
                            size="lg"
                            onClick={handleSignIn}
                            disabled={isSigningIn}
                            className="w-full bg-surface text-obsidian border border-border hover:bg-white hover:border-copper/50 shadow-sm transition-all relative overflow-hidden group"
                        >
                            {/* Google 'G' SVG */}
                            <div className="absolute left-4">
                                <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                    <path d="M5.84 14.13c-.22-.66-.35-1.36-.35-2.13s.13-1.47.35-2.13V7.03H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.97l3.66-2.84z" fill="#FBBC05" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.03l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                                </svg>
                            </div>
                            {isSigningIn ? (
                                <span className="flex items-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin text-copper" />
                                    Connecting...
                                </span>
                            ) : (
                                <span className="font-semibold text-obsidian group-hover:text-copper transition-colors">Sign in with Google</span>
                            )}
                        </DonnaButton>

                        <div className="text-center">
                            <DonnaText variant="label" className="text-[10px] text-muted-foreground/60 uppercase tracking-widest">
                                Enterprise Grade Security
                            </DonnaText>
                        </div>
                    </DonnaCardContent>
                </DonnaCard>
            </div>
        </div>
    );
}
