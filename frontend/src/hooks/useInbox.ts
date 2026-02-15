import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMessages, markMessageDone, archiveMessage, deleteMessage } from "@/services/messages";

export const messagesKeys = {
    all: ["messages"] as const,
    lists: () => [...messagesKeys.all, "list"] as const,
    list: (filters?: { needs_reply?: boolean }) => [...messagesKeys.lists(), filters] as const,
};

const LIMIT = 20;

export function useInbox(filters?: { needs_reply?: boolean }) {
    return useInfiniteQuery({
        queryKey: messagesKeys.list(filters),
        queryFn: ({ pageParam }) => fetchMessages({ ...filters, offset: pageParam, limit: LIMIT }),
        initialPageParam: 0,
        getNextPageParam: (lastPage, allPages) => {
            // If we received fewer items than the limit, we've reached the end
            if (lastPage.messages.length < LIMIT) return undefined;
            // Calculate next offset
            return allPages.length * LIMIT;
        },
    });
}

export function useMessageMutations() {
    const queryClient = useQueryClient();

    const invalidateList = () => {
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
    };

    const markDone = useMutation({
        mutationFn: markMessageDone,
        onSuccess: invalidateList,
    });

    const archive = useMutation({
        mutationFn: archiveMessage,
        onSuccess: invalidateList,
    });

    const remove = useMutation({
        mutationFn: deleteMessage,
        onSuccess: invalidateList,
    });

    return {
        markDone,
        archive,
        remove,
    };
}
