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
    isSandbox: boolean;
    initialSyncCompleted: boolean;
    signInWithGoogle: () => Promise<void>;
    signOut: () => Promise<void>;
    refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [session, setSession] = useState<Session | null>(null);
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSandbox, setIsSandbox] = useState(false);
    const [initialSyncCompleted, setInitialSyncCompleted] = useState(false);

    const checkSubscription = async () => {
        if (!session?.user) return;

        try {
            // Dynamically import api to avoid circular dependencies if any
            const { api } = require('../services/api');
            const response = await api.get('/settings');
            const settings = response.data;

            // Sandbox = No trial end date set (Deferred Trial)
            // If trial_ends_at is set, they are in Trial or Active
            setIsSandbox(!settings.trial_ends_at);

            // Sync status
            setInitialSyncCompleted(!!settings.initial_sync_completed);
        } catch (error) {
            console.error('Failed to fetch settings:', error);
            // Default to sandbox if check fails to be safe? 
            // Or default to FALSE to avoid showing mock data to real users on error?
            // "Secure by default" => if error, maybe assume REAL data (false) to avoid leaking mock data?
            // But for this specific feature "Deferred Trial", default path is Sandbox.
            // Let's stick to current state if error.
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
            setIsSandbox(false); // Reset
        }
    }, [session]);

    /**
     * Sign in with Google using Supabase OAuth
     * 
     * This uses the PKCE flow via expo-auth-session for security.
     * The redirect URI must be configured in Supabase dashboard.
     */
    const signInWithGoogle = async () => {
        try {
            // Create redirect URI for OAuth callback
            const redirectUri = makeRedirectUri({
                scheme: 'corta',
                path: 'auth/callback',
            });

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
                    }
                }
            }
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
                isSandbox,
                initialSyncCompleted,
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
