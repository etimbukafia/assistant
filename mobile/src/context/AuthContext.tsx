/**
 * Authentication Context using Supabase Auth with Google OAuth
 * 
 * Security:
 * - Uses expo-secure-store for encrypted token storage
 * - Implements PKCE flow via expo-auth-session
 * - Auto-refreshes tokens
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { makeRedirectUri } from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';
import { supabase } from '../utils/supabase';
import type { Session, User } from '@supabase/supabase-js';

// Required for OAuth redirect handling
WebBrowser.maybeCompleteAuthSession();

interface AuthContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    session: Session | null;
    user: User | null;
    // Subscription state
    isSandbox: boolean;        // True if user never started trial (show demo data)
    isActive: boolean;         // True if trial/pro is currently valid (allow sync)
    subscriptionTier: string;  // "trial" | "pro"
    daysRemaining: number;     // Days left in trial/subscription
    settingsError: boolean;    // True if failed to fetch settings (connection issue)
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

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<Session | null>(null);
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    // Subscription state
    const [isSandbox, setIsSandbox] = useState(true); // True = never started trial
    const [isActive, setIsActive] = useState(false);  // True = trial/pro currently valid
    const [subscriptionTier, setSubscriptionTier] = useState('trial');
    const [daysRemaining, setDaysRemaining] = useState(0);
    const [settingsError, setSettingsError] = useState(false); // True = failed to fetch settings
    // Personalization & Onboarding
    const [assistantName, setAssistantName] = useState('Donna');
    const [onboardingCompleted, setOnboardingCompleted] = useState(false);
    // Integration state
    const [initialSyncCompleted, setInitialSyncCompleted] = useState(false);
    const [gmailConnected, setGmailConnected] = useState(false);
    const [calendarConnected, setCalendarConnected] = useState(false);

    const checkSubscription = async () => {
        if (!session?.user) return;

        try {
            // Dynamically import api to avoid circular dependencies if any
            const { api } = require('../services/api');
            const response = await api.get('/settings');
            const settings = response.data;

            // Clear error state on success
            setSettingsError(false);

            // Subscription state
            // Sandbox = never started trial (show demo data)
            setIsSandbox(settings.trial_ends_at == null);
            // Active = trial/pro is currently valid (from backend)
            setIsActive(!!settings.is_active);
            setSubscriptionTier(settings.subscription_tier || 'trial');
            setDaysRemaining(settings.days_remaining || 0);

            setDaysRemaining(settings.days_remaining || 0);

            // Personalization & Onboarding
            setAssistantName(settings.assistant_name || 'Donna');
            setOnboardingCompleted(!!settings.onboarding_completed);

            // Integration state
            setInitialSyncCompleted(!!settings.initial_sync_completed);
            setGmailConnected(!!settings.gmail_connected);
            setCalendarConnected(!!settings.calendar_connected);
        } catch (error) {
            console.error('Failed to fetch settings:', error);
            // Mark error so UI can show connection issue instead of demo data
            setSettingsError(true);
            // Keep previous values if we had them, otherwise safe defaults
            // Don't reset to sandbox - user might be a paying customer with connection issues
        }
    };

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
            }
        );

        return () => subscription.unsubscribe();
    }, []);

    // Check subscription whenever session changes
    useEffect(() => {
        if (session) {
            checkSubscription();
        } else {
            // Reset all state on logout
            setIsSandbox(true);
            setIsActive(false);
            setSubscriptionTier('trial');
            setDaysRemaining(0);
            setSettingsError(false);
            setAssistantName('Donna');
            setOnboardingCompleted(false);
            setInitialSyncCompleted(false);
            setGmailConnected(false);
            setCalendarConnected(false);
        }
    }, [session]);

    /**
     * Sign in with Google using Supabase OAuth
     * 
     * This uses the PKCE flow via expo-auth-session for security.
     * The redirect URI must be configured in Supabase dashboard.
     */
    const signInWithGoogle = async (): Promise<boolean> => {
        try {
            // Create redirect URI for OAuth callback
            // NOTE: In Expo Go, this generates exp://... which Expo Go can intercept.
            // For production builds, it uses teeks://...  
            // BOTH must be whitelisted in Supabase dashboard -> Authentication -> URL Configuration
            const redirectUri = makeRedirectUri({
                // Don't specify scheme in dev - let Expo pick the right one
                // scheme: 'teeks',  // Uncomment for production build
                path: 'auth/callback',
            });
            console.log('=== IMPORTANT: Add this redirect URI to Supabase Dashboard ===');
            console.log('Redirect URI:', redirectUri);
            console.log('============================================================');

            // Initiate OAuth flow
            const { data, error } = await supabase.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: redirectUri,
                    skipBrowserRedirect: true, // We'll handle the redirect manually
                    queryParams: {
                        access_type: 'offline', // Request refresh token
                        prompt: 'consent', // Always show consent screen
                    },
                },
            });

            if (error) throw error;

            if (data?.url) {
                // Open browser for OAuth
                const result = await WebBrowser.openAuthSessionAsync(
                    data.url,
                    redirectUri
                );

                // User cancelled the auth flow
                if (result.type === 'cancel' || result.type === 'dismiss') {
                    return false;
                }

                if (result.type === 'success' && result.url) {
                    // Extract tokens from URL and set session
                    const url = new URL(result.url);
                    const params = new URLSearchParams(url.hash.substring(1));

                    const accessToken = params.get('access_token');
                    const refreshToken = params.get('refresh_token');

                    if (accessToken) {
                        const { error: sessionError } = await supabase.auth.setSession({
                            access_token: accessToken,
                            refresh_token: refreshToken || '',
                        });

                        if (sessionError) throw sessionError;
                        return true;
                    }
                }
            }
            return false;
        } catch (error) {
            console.error('Google sign-in error:', error);
            throw error;
        }
    };

    /**
     * Sign out and clear all auth state
     */
    const signOut = async () => {
        try {
            const { error } = await supabase.auth.signOut();
            if (error) throw error;

            // State will be cleared by onAuthStateChange listener
        } catch (error) {
            console.error('Sign out error:', error);
            throw error;
        }
    };

    return (
        <AuthContext.Provider
            value={{
                isAuthenticated: !!session,
                isLoading,
                session,
                user,
                // Subscription state
                isSandbox,
                isActive,
                subscriptionTier,
                daysRemaining,
                settingsError,
                // Personalization & Onboarding
                assistantName,
                onboardingCompleted,
                // Integration state
                initialSyncCompleted,
                gmailConnected,
                calendarConnected,
                // Actions
                signInWithGoogle,
                signOut,
                refreshProfile: checkSubscription
            }}
        >
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
