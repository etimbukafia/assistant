"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function QueryProvider({ children }: { children: React.ReactNode }) {
    const [queryClient] = useState(() => new QueryClient({
        defaultOptions: {
            queries: {
                staleTime: 5 * 60 * 1000,        // 5 min — data stays fresh across tab switches
                gcTime: 10 * 60 * 1000,           // 10 min — keep cache alive after unmount
                refetchOnWindowFocus: false,       // don't refetch when user alt-tabs back
                refetchOnMount: false,             // don't refetch when navigating between tabs
                retry: 1,                          // fail fast
            },
        },
    }));

    return (
        <QueryClientProvider client={queryClient}>
            {children}
        </QueryClientProvider>
    );
}
