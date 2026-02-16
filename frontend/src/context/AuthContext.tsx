"use client";

import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { createClient } from '@/utils/supabase/client';
import { connectGmail } from '@/services/gmail';
import { fetchSettings, type UserSettings } from '@/services/settings';
import { useRouter } from 'next/navigation';

interface AuthContextType {
    user: User | null;
    session: Session | null;
    loading: boolean;
    settings: UserSettings | null;
    settingsLoading: boolean;
    isActive: boolean;
    onboardingCompleted: boolean;
    assistantName: string;
    signInWithGoogle: () => Promise<void>;
    signOut: () => Promise<void>;
    refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [session, setSession] = useState<Session | null>(null);
    const [loading, setLoading] = useState(true);
    const [settings, setSettings] = useState<UserSettings | null>(null);
    const [settingsLoading, setSettingsLoading] = useState(false);
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

    const refreshProfile = useCallback(async () => {
        try {
            setSettingsLoading(true);
            const data = await fetchSettings();
            setSettings(data);
        } catch (error) {
            console.error('[Auth] Failed to fetch settings:', error);
        } finally {
            setSettingsLoading(false);
        }
    }, []);

    useEffect(() => {
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (_event, session) => {
                setSession(session);
                setUser(session?.user ?? null);
                setLoading(false);

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
                    setSettings(null);
                }

                // Fetch settings for authenticated users
                if (_event === 'SIGNED_IN' || _event === 'TOKEN_REFRESHED') {
                    if (session?.access_token) {
                        try {
                            const data = await fetchSettings();
                            setSettings(data);
                        } catch {
                            // Settings may not exist yet for brand new users
                        }
                    }
                }
            }
        );

        return () => subscription.unsubscribe();
    }, [supabase]);

    // Effect to process the pending Gmail connection
    useEffect(() => {
        const pending = pendingGmailConnectRef.current;
        if (!pending) return;

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
                // Refresh settings after Gmail connect to get updated state
                await refreshProfile();
                router.refresh();
            } catch (error) {
                console.error('[Auth] Failed to connect Gmail:', error);
            }
        };

        connect();
    }, [session, router, refreshProfile]);

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
        setSettings(null);
        router.push('/login');
        router.refresh();
    };

    const isActive = settings?.is_active ?? false;
    const onboardingCompleted = settings?.onboarding_completed ?? false;
    const assistantName = settings?.assistant_name ?? 'Donna';

    return (
        <AuthContext.Provider value={{
            user,
            session,
            loading,
            settings,
            settingsLoading,
            isActive,
            onboardingCompleted,
            assistantName,
            signInWithGoogle,
            signOut,
            refreshProfile,
        }}>
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
