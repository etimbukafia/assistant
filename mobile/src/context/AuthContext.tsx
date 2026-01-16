import React, { createContext, useContext, useState, useEffect } from 'react';
import { Storage } from '../utils/Storage';
import { api } from '../services/api';

interface UserProfile {
    name: string;
    email: string;
}

interface AuthContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    token: string | null;
    user: UserProfile | null;
    syncStatus: 'demo' | 'processing' | 'real';
    login: (token: string) => Promise<void>;
    logout: () => Promise<void>;
    startSync: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [token, setToken] = useState<string | null>(null);
    const [user, setUser] = useState<UserProfile | null>({
        name: 'Jane Doe',
        email: 'jane@example.com'
    }); // Mock user for now
    const [syncStatus, setSyncStatus] = useState<'demo' | 'processing' | 'real'>('demo');
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        try {
            const storedToken = await Storage.getItem('auth_token');
            const storedSync = await Storage.getItem('sync_status');

            if (storedToken) {
                setToken(storedToken);
            }
            if (storedSync) {
                setSyncStatus(storedSync as any);
            }
        } catch (error) {
            console.error('Auth check failed:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const login = async (newToken: string) => {
        try {
            await Storage.setItem('auth_token', newToken);
            setToken(newToken);
            // In a real app, we'd fetch profile here
            setUser({ name: 'Jane Doe', email: 'jane@example.com' });
        } catch (error) {
            console.error('Login failed:', error);
            throw error;
        }
    };

    const logout = async () => {
        try {
            await Storage.deleteItem('auth_token');
            await Storage.deleteItem('sync_status');
            setToken(null);
            setUser(null);
            setSyncStatus('demo');
        } catch (error) {
            console.error('Logout failed:', error);
        }
    };

    const startSync = async () => {
        setSyncStatus('processing');
        await Storage.setItem('sync_status', 'processing');

        // Mock transition to real after 5 seconds
        setTimeout(async () => {
            setSyncStatus('real');
            await Storage.setItem('sync_status', 'real');
        }, 5000);
    };

    return (
        <AuthContext.Provider
            value={{
                isAuthenticated: !!token,
                isLoading,
                token,
                user,
                syncStatus,
                login,
                logout,
                startSync
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
