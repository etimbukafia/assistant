/**
 * SyncCTA Context - Global state for CTA banner dismissal
 * 
 * Persists dismissal state to AsyncStorage for global effect across all screens.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@corta/cta_dismissed';

interface SyncCTAContextType {
    ctaDismissed: boolean;
    dismissCTA: () => void;
}

const SyncCTAContext = createContext<SyncCTAContextType | undefined>(undefined);

export function SyncCTAProvider({ children }: { children: React.ReactNode }) {
    const [ctaDismissed, setCtaDismissed] = useState(false);
    const [isLoaded, setIsLoaded] = useState(false);

    // Load persisted state on mount
    useEffect(() => {
        AsyncStorage.getItem(STORAGE_KEY).then((value) => {
            if (value === 'true') {
                setCtaDismissed(true);
            }
            setIsLoaded(true);
        });
    }, []);

    const dismissCTA = async () => {
        setCtaDismissed(true);
        await AsyncStorage.setItem(STORAGE_KEY, 'true');
    };

    // Don't render children until loaded to prevent flash
    if (!isLoaded) {
        return null;
    }

    return (
        <SyncCTAContext.Provider value={{ ctaDismissed, dismissCTA }}>
            {children}
        </SyncCTAContext.Provider>
    );
}

export function useSyncCTA() {
    const context = useContext(SyncCTAContext);
    if (context === undefined) {
        throw new Error('useSyncCTA must be used within a SyncCTAProvider');
    }
    return context;
}
