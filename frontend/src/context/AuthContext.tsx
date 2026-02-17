"use client";

import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { createClient } from '@/utils/supabase/client';
import { connectGmail } from '@/services/gmail';
import { fetchSettings, type UserSettings } from '@/services/settings';
import { triggerInitialSync } from '@/services/billing';
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
    gmailConnectError: string | null;
    gmailConnectInFlight: boolean;
    gmailConnected: boolean;
    signInWithGoogle: () => Promise<void>;
    signOut: () => Promise<void>;
    refreshProfile: () => Promise<void>;
    retryGmailConnect: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [session, setSession] = useState<Session | null>(null);
    const [loading, setLoading] = useState(true);
    const [settings, setSettings] = useState<UserSettings | null>(null);
    const [settingsLoading, setSettingsLoading] = useState(false);
    const [gmailConnectError, setGmailConnectError] = useState<string | null>(null);
    const [gmailConnectInFlight, setGmailConnectInFlight] = useState(false);
    const [gmailConnected, setGmailConnected] = useState(false);
    const router = useRouter();
    const supabase = createClient();

    // Refs to prevent double-processing in Strict Mode and track last known tokens
    const gmailConnectProcessedRef = useRef(false);
    const gmailConnectInFlightRef = useRef(false);
    const lastGmailConnectRef = useRef<{
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
            if (data?.gmail_connected) {
                setGmailConnected(true);
            }
        } catch (error: any) {
            console.error('[Auth] Failed to fetch settings:', error);
            // Only clear on 404 (new user). Keep existing settings on transient errors.
            if (error?.response?.status === 404) {
                setSettings(null);
            }
        } finally {
            setSettingsLoading(false);
        }
    }, []);

    const startGmailConnect = useCallback(async (pending: {
        providerToken: string;
        providerRefreshToken?: string;
        email: string;
        accessToken: string;
    }) => {
        if (gmailConnectProcessedRef.current || gmailConnectInFlightRef.current) return;

        gmailConnectInFlightRef.current = true;
        setGmailConnectInFlight(true);
        setGmailConnectError(null);

        console.log('[Auth] Connecting Gmail for:', pending.email);
        try {
            await connectGmail({
                provider_token: pending.providerToken,
                provider_refresh_token: pending.providerRefreshToken,
                email: pending.email,
            }, pending.accessToken);
            console.log('[Auth] Gmail connected successfully');
            gmailConnectProcessedRef.current = true;
            setGmailConnected(true);
            setGmailConnectError(null);
            try {
                await triggerInitialSync();
            } catch {
                // Non-fatal: may already be completed or user not active yet
            }
            await refreshProfile();
            router.refresh();
        } catch (error: any) {
            const detail = error.response?.data?.detail;
            const message = typeof detail === 'string'
                ? detail
                : 'Failed to connect Gmail. Please try again.';
            console.error('[Auth] Failed to connect Gmail:', message);
            gmailConnectProcessedRef.current = false;
            setGmailConnectError(message);
        } finally {
            gmailConnectInFlightRef.current = false;
            setGmailConnectInFlight(false);
        }
    }, [refreshProfile, router]);

    useEffect(() => {
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (_event, session) => {
                setSession(session);
                setUser(session?.user ?? null);
                setLoading(false);

                if (session?.provider_token && session?.user?.email) {
                    lastGmailConnectRef.current = {
                        providerToken: session.provider_token,
                        providerRefreshToken: session.provider_refresh_token || undefined,
                        email: session.user.email,
                        accessToken: session.access_token,
                    };
                    if (!gmailConnectProcessedRef.current && !gmailConnectInFlightRef.current) {
                        startGmailConnect(lastGmailConnectRef.current);
                    }
                } else if (_event === 'SIGNED_OUT') {
                    gmailConnectProcessedRef.current = false;
                    gmailConnectInFlightRef.current = false;
                    lastGmailConnectRef.current = null;
                    setSettings(null);
                    setGmailConnectError(null);
                    setGmailConnected(false);
                }

                // Fetch settings for authenticated users
                if (_event === 'SIGNED_IN' || _event === 'TOKEN_REFRESHED') {
                    if (session?.access_token) {
                        try {
                            setSettingsLoading(true);
                            const data = await fetchSettings(session.access_token);
                            setSettings(data);
                        } catch (err: any) {
                            // Only clear settings for 404 (truly new user).
                            // For transient errors (401, network), keep existing settings
                            // to avoid false redirect to /auth/subscription.
                            const status = err?.response?.status;
                            if (status === 404) {
                                setSettings(null);
                            }
                        } finally {
                            setSettingsLoading(false);
                        }
                    }
                }
            }
        );

        return () => subscription.unsubscribe();
    }, [supabase, startGmailConnect]);

    useEffect(() => {
        if (settings?.gmail_connected) {
            setGmailConnected(true);
        }
    }, [settings?.gmail_connected]);

    const signInWithGoogle = async () => {
        await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: `${window.location.origin}/auth/callback`,
                scopes: 'email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.events.freebusy',
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
        setGmailConnectError(null);
        setGmailConnected(false);
        router.push('/login');
        router.refresh();
    };

    const retryGmailConnect = async () => {
        if (gmailConnectInFlightRef.current) return;
        if (!lastGmailConnectRef.current) return;
        await startGmailConnect(lastGmailConnectRef.current);
    };

    const isActive = settings?.is_active ?? false;
    const onboardingCompleted = settings?.onboarding_completed ?? false;
    const assistantName = settings?.assistant_name ?? 'Teeks';

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
            gmailConnectError,
            gmailConnectInFlight,
            gmailConnected,
            signInWithGoogle,
            signOut,
            refreshProfile,
            retryGmailConnect,
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
