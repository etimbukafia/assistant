"use client";

import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { createClient } from '@/utils/supabase/client';
import { connectGmail } from '@/services/gmail';
import { connectMicrosoft } from '@/services/microsoft';
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
    microsoftConnectError: string | null;
    microsoftConnectInFlight: boolean;
    microsoftConnected: boolean;
    signInWithGoogle: () => Promise<void>;
    signInWithMicrosoft: () => Promise<void>;
    signOut: () => Promise<void>;
    refreshProfile: () => Promise<void>;
    retryGmailConnect: () => Promise<void>;
    retryMicrosoftConnect: () => Promise<void>;
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
    const [microsoftConnectError, setMicrosoftConnectError] = useState<string | null>(null);
    const [microsoftConnectInFlight, setMicrosoftConnectInFlight] = useState(false);
    const [microsoftConnected, setMicrosoftConnected] = useState(false);
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
    const lastMicrosoftConnectRef = useRef<{
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
            if (data?.outlook_connected) {
                setMicrosoftConnected(true);
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

    const microsoftConnectProcessedRef = useRef(false);
    const microsoftConnectInFlightRef = useRef(false);

    const startMicrosoftConnect = useCallback(async (pending: {
        providerToken: string;
        providerRefreshToken?: string;
        email: string;
        accessToken: string;
    }) => {
        if (microsoftConnectProcessedRef.current || microsoftConnectInFlightRef.current) return;

        microsoftConnectInFlightRef.current = true;
        setMicrosoftConnectInFlight(true);
        setMicrosoftConnectError(null);

        console.log('[Auth] Connecting Microsoft for:', pending.email);
        try {
            await connectMicrosoft({
                provider_token: pending.providerToken,
                provider_refresh_token: pending.providerRefreshToken,
                email: pending.email,
            }, pending.accessToken);
            console.log('[Auth] Microsoft connected successfully');
            microsoftConnectProcessedRef.current = true;
            setMicrosoftConnected(true);
            setMicrosoftConnectError(null);
            try {
                await triggerInitialSync('microsoft');
            } catch {
                // Non-fatal
            }
            await refreshProfile();
            router.refresh();
        } catch (error: any) {
            const detail = error.response?.data?.detail;
            const message = typeof detail === 'string'
                ? detail
                : 'Failed to connect Microsoft. Please try again.';
            console.error('[Auth] Failed to connect Microsoft:', message);
            microsoftConnectProcessedRef.current = false;
            setMicrosoftConnectError(message);
        } finally {
            microsoftConnectInFlightRef.current = false;
            setMicrosoftConnectInFlight(false);
        }
    }, [refreshProfile, router]);

    useEffect(() => {
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (_event, session) => {
                setSession(session);
                setUser(session?.user ?? null);
                setLoading(false);

                const provider = session?.user?.app_metadata?.provider;
                if (session?.provider_token && session?.user?.email) {
                    if (provider === 'azure') {
                        lastMicrosoftConnectRef.current = {
                            providerToken: session.provider_token,
                            providerRefreshToken: session.provider_refresh_token || undefined,
                            email: session.user.email,
                            accessToken: session.access_token,
                        };
                        if (!microsoftConnectProcessedRef.current && !microsoftConnectInFlightRef.current) {
                            startMicrosoftConnect(lastMicrosoftConnectRef.current);
                        }
                    } else {
                        lastGmailConnectRef.current = {
                            providerToken: session.provider_token,
                            providerRefreshToken: session.provider_refresh_token || undefined,
                            email: session.user.email,
                            accessToken: session.access_token,
                        };
                        if (!gmailConnectProcessedRef.current && !gmailConnectInFlightRef.current) {
                            startGmailConnect(lastGmailConnectRef.current);
                        }
                    }
                } else if (_event === 'SIGNED_OUT') {
                    gmailConnectProcessedRef.current = false;
                    gmailConnectInFlightRef.current = false;
                    lastGmailConnectRef.current = null;
                    microsoftConnectProcessedRef.current = false;
                    microsoftConnectInFlightRef.current = false;
                    lastMicrosoftConnectRef.current = null;
                    setSettings(null);
                    setGmailConnectError(null);
                    setGmailConnected(false);
                    setMicrosoftConnectError(null);
                    setMicrosoftConnected(false);
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

    useEffect(() => {
        if (settings?.outlook_connected) {
            setMicrosoftConnected(true);
        }
    }, [settings?.outlook_connected]);

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

    const signInWithMicrosoft = async () => {
        await supabase.auth.signInWithOAuth({
            provider: 'azure',
            options: {
                redirectTo: `${window.location.origin}/auth/callback`,
                scopes: 'openid email profile offline_access https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/Calendars.ReadWrite',
                queryParams: {
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
        setMicrosoftConnectError(null);
        setMicrosoftConnected(false);
        router.push('/login');
        router.refresh();
    };

    const retryGmailConnect = async () => {
        if (gmailConnectInFlightRef.current) return;
        if (!lastGmailConnectRef.current) return;
        await startGmailConnect(lastGmailConnectRef.current);
    };

    const retryMicrosoftConnect = async () => {
        if (microsoftConnectInFlightRef.current) return;
        if (!lastMicrosoftConnectRef.current) return;
        await startMicrosoftConnect(lastMicrosoftConnectRef.current);
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
            microsoftConnectError,
            microsoftConnectInFlight,
            microsoftConnected,
            signInWithGoogle,
            signInWithMicrosoft,
            signOut,
            refreshProfile,
            retryGmailConnect,
            retryMicrosoftConnect,
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
