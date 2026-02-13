/**
 * Authentication Context using Supabase Auth with Google OAuth
 *
 * Security:
 * - Uses expo-secure-store for encrypted token storage
 * - Implements PKCE flow via expo-auth-session
 * - Auto-refreshes tokens
 *
 * State Management:
 * - Uses useReducer for profile state to batch updates and reduce re-renders
 * - Auth state (session/user) kept separate as it changes independently
 *
 * Gmail Connect Strategy:
 * - provider_token is ephemeral — only available during SIGNED_IN event
 * - onAuthStateChange captures it into a ref (no async work, no race conditions)
 * - A separate useEffect picks it up after session state settles and calls connectGmail
 * - Native flow handles connectGmail inline in signInWithGoogle (no race there)
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { makeRedirectUri } from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';
import { supabase } from '../utils/supabase';
import { Platform, Alert } from 'react-native';
import type { Session, User } from '@supabase/supabase-js';

// Required for OAuth redirect handling
WebBrowser.maybeCompleteAuthSession();

// =============================================================================
// Types
// =============================================================================

interface ProfileState {
    profileLoaded: boolean;
    settingsError: boolean;
    accountConflict: boolean;
    accountConflictMessage: string | null;
    isActive: boolean;
    subscriptionTier: string;
    daysRemaining: number;
    assistantName: string;
    onboardingCompleted: boolean;
    initialSyncCompleted: boolean;
    gmailConnected: boolean;
    calendarConnected: boolean;
}

type ProfileAction =
    | { type: 'LOADING' }
    | { type: 'LOADED'; payload: Partial<ProfileState> }
    | { type: 'ERROR' }
    | { type: 'CONFLICT'; message: string }
    | { type: 'RESET' };

interface AuthContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    profileLoaded: boolean;
    session: Session | null;
    user: User | null;
    isActive: boolean;
    subscriptionTier: string;
    daysRemaining: number;
    settingsError: boolean;
    accountConflict: boolean;
    accountConflictMessage: string | null;
    assistantName: string;
    onboardingCompleted: boolean;
    initialSyncCompleted: boolean;
    gmailConnected: boolean;
    calendarConnected: boolean;
    signInWithGoogle: () => Promise<boolean>;
    signOut: () => Promise<void>;
    refreshProfile: () => Promise<void>;
}

// =============================================================================
// Reducer
// =============================================================================

const initialProfileState: ProfileState = {
    profileLoaded: false,
    settingsError: false,
    accountConflict: false,
    accountConflictMessage: null,
    isActive: false,
    subscriptionTier: 'trial',
    daysRemaining: 0,
    assistantName: 'Donna',
    onboardingCompleted: false,
    initialSyncCompleted: false,
    gmailConnected: false,
    calendarConnected: false,
};

function profileReducer(state: ProfileState, action: ProfileAction): ProfileState {
    switch (action.type) {
        case 'LOADING':
            return { ...state, profileLoaded: false, accountConflict: false, accountConflictMessage: null };
        case 'LOADED':
            return {
                ...state,
                ...action.payload,
                profileLoaded: true,
                settingsError: false,
                accountConflict: false,
                accountConflictMessage: null,
            };
        case 'ERROR':
            return { ...state, profileLoaded: true, settingsError: true };
        case 'CONFLICT':
            return {
                ...state,
                profileLoaded: true,
                settingsError: false,
                accountConflict: true,
                accountConflictMessage: action.message,
            };
        case 'RESET':
            return initialProfileState;
        default:
            return state;
    }
}

// =============================================================================
// Context
// =============================================================================

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<Session | null>(null);
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [profile, dispatch] = useReducer(profileReducer, initialProfileState);

    const abortControllerRef = useRef<AbortController | null>(null);

    // Ref to hold pending Gmail connect data captured from onAuthStateChange.
    // provider_token is ephemeral — only on the session during SIGNED_IN.
    const pendingGmailConnectRef = useRef<{
        providerToken: string;
        providerRefreshToken?: string;
        email: string;
        accessToken: string;
    } | null>(null);

    // Guard: only process Gmail connect once per auth session.
    // Supabase fires multiple SIGNED_IN events on web — without this,
    // connectGmail would be called in a loop.
    const gmailConnectProcessedRef = useRef(false);

    // -----------------------------------------------------------------
    // Check subscription / load profile
    // -----------------------------------------------------------------
    const checkSubscription = useCallback(async () => {
        if (!session?.user) return;

        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        try {
            const { api } = require('../services/api');
            const response = await api.get('/settings/', {
                signal: abortControllerRef.current.signal,
                validateStatus: (status: number) => status < 500
            });

            if (response.status === 409) {
                const message = response.data?.detail?.message ||
                    'An account with this email already exists. Please contact support.';
                dispatch({ type: 'CONFLICT', message });
                return;
            }

            if (response.status !== 200) {
                console.warn('[Auth] Settings fetch returned status:', response.status);
                return;
            }

            const settings = response.data;
            console.log('[Auth] Settings loaded:', {
                is_active: settings.is_active,
                subscription_tier: settings.subscription_tier,
                days_remaining: settings.days_remaining,
                gmail_connected: settings.gmail_connected,
                onboarding_completed: settings.onboarding_completed,
            });
            dispatch({
                type: 'LOADED',
                payload: {
                    isActive: !!settings.is_active,
                    subscriptionTier: settings.subscription_tier || 'trial',
                    daysRemaining: settings.days_remaining || 0,
                    assistantName: settings.assistant_name || 'Donna',
                    onboardingCompleted: !!settings.onboarding_completed,
                    initialSyncCompleted: !!settings.initial_sync_completed,
                    gmailConnected: !!settings.gmail_connected,
                    calendarConnected: !!settings.calendar_connected,
                },
            });
        } catch (error: any) {
            if (error?.name === 'AbortError' || error?.name === 'CanceledError') return;
            console.error('Failed to fetch settings:', error);
            dispatch({ type: 'ERROR' });
        }
    }, [session?.user]);

    // -----------------------------------------------------------------
    // Auth listener — keep it synchronous, no async work
    // -----------------------------------------------------------------
    useEffect(() => {
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session);
            setUser(session?.user ?? null);
            setIsLoading(false);
        });

        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            (_event, session) => {
                console.log('[Auth] onAuthStateChange:', _event, {
                    email: session?.user?.email,
                    provider_token: !!session?.provider_token,
                });

                // Capture provider_token before it disappears.
                // This is synchronous — no awaits, no race conditions.
                // Guard: only capture once per auth session (Supabase fires multiple SIGNED_IN on web).
                if (_event === 'SIGNED_IN' && session?.provider_token && session?.user?.email && !gmailConnectProcessedRef.current) {
                    gmailConnectProcessedRef.current = true;
                    pendingGmailConnectRef.current = {
                        providerToken: session.provider_token,
                        providerRefreshToken: session.provider_refresh_token || undefined,
                        email: session.user.email,
                        accessToken: session.access_token,
                    };
                }

                setSession(session);
                setUser(session?.user ?? null);
                setIsLoading(false);

                // Clean URL hash on web
                if (Platform.OS === 'web' && typeof window !== 'undefined' && window.location.hash) {
                    window.history.replaceState(null, '', window.location.pathname + window.location.search);
                }
            }
        );

        return () => subscription.unsubscribe();
    }, []);

    // -----------------------------------------------------------------
    // Gmail connect effect — runs after session state settles
    // -----------------------------------------------------------------
    useEffect(() => {
        const pending = pendingGmailConnectRef.current;
        if (!pending || !session) return;

        // Clear immediately so this only runs once
        pendingGmailConnectRef.current = null;

        (async () => {
            console.log('[Auth] Connecting Gmail for:', pending.email);
            try {
                const { connectGmail } = require('../services/gmail');
                const result = await connectGmail({
                    provider_token: pending.providerToken,
                    provider_refresh_token: pending.providerRefreshToken,
                    email: pending.email,
                }, pending.accessToken);
                console.log('[Auth] connectGmail success:', result);

                // Trigger initial sync now that GmailAccount exists
                try {
                    const { triggerInitialSync } = require('../services/billing');
                    await triggerInitialSync();
                    console.log('[Auth] Initial sync triggered successfully');
                } catch (syncError: any) {
                    // Non-fatal: sync can be retried later
                    console.warn('[Auth] Initial sync trigger failed:', syncError?.message);
                }
            } catch (error: any) {
                console.error('[Auth] connectGmail failed:', {
                    status: error?.response?.status,
                    data: error?.response?.data,
                    message: error?.message,
                });
                const errorDetail = error?.response?.data?.detail;
                if (errorDetail?.error === 'missing_scopes') {
                    Alert.alert(
                        'Permissions Required',
                        `To use Teeks, please grant all requested permissions:\n\n• ${errorDetail.missing_permissions?.join('\n• ')}`,
                        [{ text: 'OK' }]
                    );
                } else {
                    Alert.alert(
                        'Connection Failed',
                        'Unable to connect your Google account. Please try again.',
                        [{ text: 'OK' }]
                    );
                }
                await supabase.auth.signOut();
            }
        })();
    }, [session]);

    // -----------------------------------------------------------------
    // Profile check — runs when session changes
    // -----------------------------------------------------------------
    useEffect(() => {
        if (session) {
            dispatch({ type: 'LOADING' });
            checkSubscription();
        } else {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            dispatch({ type: 'RESET' });
        }

        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, [session, checkSubscription]);

    // -----------------------------------------------------------------
    // Sign in with Google
    // -----------------------------------------------------------------
    const signInWithGoogle = useCallback(async (): Promise<boolean> => {
        try {
            if (Platform.OS === 'web') {
                // Web: full-page redirect. After OAuth, Supabase detects tokens
                // in the hash, fires onAuthStateChange with SIGNED_IN + provider_token.
                // The ref + useEffect above handles connectGmail.
                const { data, error } = await supabase.auth.signInWithOAuth({
                    provider: 'google',
                    options: {
                        redirectTo: window.location.origin,
                        scopes: 'email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events',
                        queryParams: {
                            access_type: 'offline',
                            prompt: 'consent',
                        },
                    },
                });
                if (error) throw error;
                return true;
            }

            // Native: expo-auth-session popup flow
            const redirectUri = makeRedirectUri({ path: 'auth/callback' });

            const { data, error } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: redirectUri,
                    skipBrowserRedirect: true,
                    scopes: 'email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events',
                    queryParams: {
                        access_type: 'offline',
                        prompt: 'consent',
                    },
                },
            });
            if (error) throw error;

            if (data?.url) {
                const result = await WebBrowser.openAuthSessionAsync(data.url, redirectUri);

                if (result.type === 'cancel' || result.type === 'dismiss') {
                    return false;
                }

                if (result.type === 'success' && result.url) {
                    const params = new URLSearchParams(new URL(result.url).hash.substring(1));

                    const accessToken = params.get('access_token');
                    const refreshToken = params.get('refresh_token');
                    const providerToken = params.get('provider_token');
                    const providerRefreshToken = params.get('provider_refresh_token');

                    if (!accessToken) throw new Error('No access token from Google');

                    const { error: sessionError } = await supabase.auth.setSession({
                        access_token: accessToken,
                        refresh_token: refreshToken || '',
                    });
                    if (sessionError) throw sessionError;

                    if (!providerToken) {
                        await supabase.auth.signOut();
                        throw new Error('Google did not return access to Gmail/Calendar. Please try again and grant all permissions.');
                    }

                    // Native flow is linear — no race condition, connect directly
                    const { connectGmail } = require('../services/gmail');
                    const { data: { session: newSession } } = await supabase.auth.getSession();
                    const email = newSession?.user?.email;

                    if (!email) {
                        throw new Error('No email found in session. Please try again.');
                    }

                    await connectGmail({
                        provider_token: providerToken,
                        provider_refresh_token: providerRefreshToken || undefined,
                        email,
                    }, accessToken);

                    console.log('[Auth] Gmail connected successfully (native)');
                    return true;
                }
            }
            return false;
        } catch (error) {
            console.error('Google sign-in error:', error);
            throw error;
        }
    }, []);

    // -----------------------------------------------------------------
    // Sign out
    // -----------------------------------------------------------------
    const signOut = useCallback(async () => {
        try {
            gmailConnectProcessedRef.current = false;
            const { error } = await supabase.auth.signOut();
            if (error) throw error;
        } catch (error) {
            console.error('Sign out error:', error);
            throw error;
        }
    }, []);

    const value: AuthContextType = {
        isAuthenticated: !!session,
        isLoading,
        session,
        user,
        ...profile,
        signInWithGoogle,
        signOut,
        refreshProfile: checkSubscription,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
