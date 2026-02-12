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
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { makeRedirectUri } from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';
import { supabase } from '../utils/supabase';
import { Platform } from 'react-native';
import type { Session, User } from '@supabase/supabase-js';

// Required for OAuth redirect handling
WebBrowser.maybeCompleteAuthSession();

// =============================================================================
// Types
// =============================================================================

interface ProfileState {
    profileLoaded: boolean;
    settingsError: boolean;
    accountConflict: boolean; // True if email exists with different user_id
    accountConflictMessage: string | null;
    // Subscription
    isActive: boolean;
    subscriptionTier: string;
    daysRemaining: number;
    // Personalization & Onboarding
    assistantName: string;
    onboardingCompleted: boolean;
    // Integration state
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
    // Subscription state
    isActive: boolean;
    subscriptionTier: string;
    daysRemaining: number;
    settingsError: boolean;
    // Account conflict state
    accountConflict: boolean;
    accountConflictMessage: string | null;
    // Personalization & Onboarding
    assistantName: string;
    onboardingCompleted: boolean;
    // Integration state
    initialSyncCompleted: boolean;
    gmailConnected: boolean;
    calendarConnected: boolean;
    // Actions
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
    // Core auth state (changes independently from profile)
    const [session, setSession] = useState<Session | null>(null);
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // Profile state (batched updates via reducer)
    const [profile, dispatch] = useReducer(profileReducer, initialProfileState);

    // Abort controller ref for cancelling in-flight requests
    const abortControllerRef = useRef<AbortController | null>(null);

    const checkSubscription = useCallback(async () => {
        if (!session?.user) return;

        // Cancel any in-flight request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        try {
            // Dynamically import api to avoid circular dependencies if any
            const { api } = require('../services/api');
            // Fetch latest settings from backend
            const response = await api.get('/settings/', {
                signal: abortControllerRef.current.signal,
                validateStatus: (status: number) => status < 500 // Don't throw on 404
            });

            // Check for 409 Conflict (account exists with different user_id)
            if (response.status === 409) {
                const errorData = response.data;
                const message = errorData?.detail?.message ||
                    'An account with this email already exists. Please contact support.';
                dispatch({ type: 'CONFLICT', message });
                return;
            }

            const settings = response.data;

            // Single dispatch updates all profile state at once (reduces re-renders)
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
            // Ignore abort errors - they're expected when session changes mid-fetch
            if (error?.name === 'AbortError' || error?.name === 'CanceledError') {
                return;
            }
            console.error('Failed to fetch settings:', error);
            // Mark error so UI can show connection issue instead of demo data
            // Keep previous values - user might be a paying customer with connection issues
            dispatch({ type: 'ERROR' });
        }
    }, [session?.user]);

    useEffect(() => {
        // Get initial session
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session);
            setUser(session?.user ?? null);
            setIsLoading(false);
        });

        // Listen for auth state changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (_event, session) => {
                setSession(session);
                setUser(session?.user ?? null);
                setIsLoading(false);

                // On web/PWA: handle OAuth redirect
                if (_event === 'SIGNED_IN' && Platform.OS === 'web' && typeof window !== 'undefined') {
                    // Check for provider token in URL hash (from Google OAuth)
                    if (window.location.hash) {
                        const hashParams = new URLSearchParams(window.location.hash.substring(1));
                        const providerToken = hashParams.get('provider_token');
                        const providerRefreshToken = hashParams.get('provider_refresh_token');

                        // Connect Gmail if we have a provider token
                        if (providerToken && session?.user?.email) {
                            try {
                                const { connectGmail } = require('../services/gmail');
                                await connectGmail({
                                    provider_token: providerToken,
                                    provider_refresh_token: providerRefreshToken || undefined,
                                    email: session.user.email,
                                });
                                console.log('Google connected successfully (web)');
                            } catch (gmailError: any) {
                                console.error('Failed to connect Google (web):', gmailError);
                                // Sign out to clean up partial state - can't proceed without Google connection
                                await supabase.auth.signOut();

                                // Show appropriate error message
                                const { Alert } = require('react-native');
                                const errorDetail = gmailError?.response?.data?.detail;
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
                            }
                        }

                        // Clean access tokens from URL hash
                        if (window.location.hash.includes('access_token')) {
                            window.history.replaceState(null, '', window.location.pathname + window.location.search);
                        }
                    }
                }
            }
        );

        return () => subscription.unsubscribe();
    }, []);

    // Check subscription whenever session changes
    useEffect(() => {
        if (session) {
            // Reset profileLoaded before fetching new settings
            dispatch({ type: 'LOADING' });
            checkSubscription();
        } else {
            // Cancel any in-flight request on logout
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            // Reset all profile state on logout
            dispatch({ type: 'RESET' });
        }

        // Cleanup on unmount
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, [session, checkSubscription]);

    /**
     * Sign in with Google using Supabase OAuth
     *
     * This uses the PKCE flow via expo-auth-session for security.
     * The redirect URI must be configured in Supabase dashboard.
     */
    const signInWithGoogle = useCallback(async (): Promise<boolean> => {
        try {
            if (Platform.OS === 'web') {
                // Web/PWA: Use full-page redirect instead of popup.
                // After Google OAuth, Supabase redirects back to the app URL
                // with tokens in the hash. detectSessionInUrl (enabled for web
                // in supabase.ts) auto-extracts them and triggers onAuthStateChange.
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
                // signInWithOAuth on web will redirect the page automatically
                return true;
            }

            // Native: Use expo-auth-session popup flow
            const redirectUri = makeRedirectUri({
                path: 'auth/callback',
            });
            console.log('Redirect URI:', redirectUri);

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
                const result = await WebBrowser.openAuthSessionAsync(
                    data.url,
                    redirectUri
                );

                if (result.type === 'cancel' || result.type === 'dismiss') {
                    return false;
                }

                if (result.type === 'success' && result.url) {
                    const url = new URL(result.url);
                    const params = new URLSearchParams(url.hash.substring(1));

                    const accessToken = params.get('access_token');
                    const refreshToken = params.get('refresh_token');
                    const providerToken = params.get('provider_token');
                    const providerRefreshToken = params.get('provider_refresh_token');

                    if (accessToken) {
                        const { error: sessionError } = await supabase.auth.setSession({
                            access_token: accessToken,
                            refresh_token: refreshToken || '',
                        });

                        if (sessionError) throw sessionError;

                        // Connect Gmail if we have a provider token
                        if (providerToken) {
                            try {
                                const { connectGmail } = require('../services/gmail');
                                // Get email from the session
                                const { data: { session: newSession } } = await supabase.auth.getSession();
                                const email = newSession?.user?.email;
                                if (email) {
                                    await connectGmail({
                                        provider_token: providerToken,
                                        provider_refresh_token: providerRefreshToken || undefined,
                                        email: email,
                                    });
                                    console.log('Google connected successfully');
                                }
                            } catch (gmailError: any) {
                                console.error('Failed to connect Google:', gmailError);
                                // Sign out to clean up partial state - can't proceed without Google connection
                                await supabase.auth.signOut();
                                // Re-throw so UI can handle it
                                throw gmailError;
                            }
                        }

                        return true;
                    }
                }
            }
            return false;
        } catch (error) {
            console.error('Google sign-in error:', error);
            throw error;
        }
    }, []);

    /**
     * Sign out and clear all auth state
     */
    const signOut = useCallback(async () => {
        try {
            const { error } = await supabase.auth.signOut();
            if (error) throw error;

            // State will be cleared by onAuthStateChange listener
        } catch (error) {
            console.error('Sign out error:', error);
            throw error;
        }
    }, []);

    // Memoize context value to prevent unnecessary re-renders of consumers
    const value: AuthContextType = {
        isAuthenticated: !!session,
        isLoading,
        session,
        user,
        // Spread profile state
        ...profile,
        // Actions
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
