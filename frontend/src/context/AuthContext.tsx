"use client";

import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { createClient } from '@/utils/supabase/client';
import { connectGmail } from '@/services/gmail';
import { useRouter } from 'next/navigation';

interface AuthContextType {
    user: User | null;
    session: Session | null;
    loading: boolean;
    signInWithGoogle: () => Promise<void>;
    signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [session, setSession] = useState<Session | null>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();
    const supabase = createClient();

    // Ref to prevent double-processing the same token in Strict Mode
    const gmailConnectProcessedRef = useRef(false);
    const pendingGmailConnectRef = useRef<{
        providerToken: string;
        providerRefreshToken?: string;
        email: string;
        accessToken: string;
    } | null>(null);

    useEffect(() => {
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (_event, session) => {
                setSession(session);
                setUser(session?.user ?? null);
                setLoading(false);

                // Detect provider token on sign-in (Web flow)
                // When redirecting back from Google, Supabase parses the hash and fires SIGNED_IN
                // with the provider_token in the session object.
                if (_event === 'SIGNED_IN' && session?.provider_token && session?.user?.email && !gmailConnectProcessedRef.current) {
                    gmailConnectProcessedRef.current = true;
                    pendingGmailConnectRef.current = {
                        providerToken: session.provider_token,
                        providerRefreshToken: session.provider_refresh_token || undefined,
                        email: session.user.email,
                        accessToken: session.access_token,
                    };
                } else if (_event === 'SIGNED_OUT') {
                    gmailConnectProcessedRef.current = false;
                    pendingGmailConnectRef.current = null;
                }
            }
        );

        return () => subscription.unsubscribe();
    }, [supabase]);

    // Effect to process the pending Gmail connection
    useEffect(() => {
        const pending = pendingGmailConnectRef.current;
        if (!pending) return;

        // Clear immediately to prevent loops
        pendingGmailConnectRef.current = null;

        const connect = async () => {
            console.log('[Auth] Connecting Gmail for:', pending.email);
            try {
                await connectGmail({
                    provider_token: pending.providerToken,
                    provider_refresh_token: pending.providerRefreshToken,
                    email: pending.email,
                }, pending.accessToken);
                console.log('[Auth] Gmail connected successfully');
                router.refresh(); // Refresh server components
            } catch (error) {
                console.error('[Auth] Failed to connect Gmail:', error);
                // In a real app, show a toast or error state here
            }
        };

        connect();
    }, [session, router]);

    const signInWithGoogle = async () => {
        await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: `${window.location.origin}/auth/callback`,
                scopes: 'email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events',
                queryParams: {
                    access_type: 'offline',
                    prompt: 'consent',
                },
            },
        });
    };

    const signOut = async () => {
        await supabase.auth.signOut();
        router.push('/login');
        router.refresh();
    };

    return (
        <AuthContext.Provider value={{ user, session, loading, signInWithGoogle, signOut }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
