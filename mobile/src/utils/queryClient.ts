import { QueryClient } from '@tanstack/react-query';

// Configure QueryClient with sensible defaults for mobile
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: 1, // Don't retry endlessly if offline
            staleTime: 1000 * 60, // 1 minute stale time
            refetchOnWindowFocus: false, // Not needed for mobile usually
        },
    },
});
