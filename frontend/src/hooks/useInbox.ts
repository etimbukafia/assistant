import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMessages, markMessageDone, archiveMessage, restoreMessage, deleteMessage, type Message, type MessagesResponse } from "@/services/messages";
import { tasksKeys } from "./useTasks";
import { toast } from "sonner";

export const messagesKeys = {
    all: ["messages"] as const,
    lists: () => [...messagesKeys.all, "list"] as const,
    list: (filters?: { needs_reply?: boolean }) => [...messagesKeys.lists(), filters] as const,
};

const LIMIT = 20;

export function useInbox(filters?: { needs_reply?: boolean; status?: string }) {
    return useInfiniteQuery({
        queryKey: messagesKeys.list(filters),
        queryFn: ({ pageParam }) => fetchMessages({ ...filters, offset: pageParam, limit: LIMIT }),
        initialPageParam: 0,
        staleTime: 2 * 60_000, // 2 min — tab switches are instant
        getNextPageParam: (lastPage, allPages) => {
            if (lastPage.messages.length < LIMIT) return undefined;
            return allPages.length * LIMIT;
        },
    });
}

// Helper: update a message across all infinite query pages
function updateMessageInPages(
    old: unknown,
    messageId: number,
    updater: ((msg: Message) => Message) | null, // null = remove
): unknown {
    if (!old || typeof old !== "object" || !("pages" in old)) return old;
    const data = old as { pages: Array<MessagesResponse>; pageParams: unknown[] };
    return {
        ...data,
        pages: data.pages.map((page) => {
            if (updater === null) {
                // Remove message
                const filtered = page.messages.filter((m) => m.id !== messageId);
                return { ...page, messages: filtered, total: page.total - (page.messages.length - filtered.length) };
            }
            return {
                ...page,
                messages: page.messages.map((m) => (m.id === messageId ? updater(m) : m)),
            };
        }),
    };
}

export function useMessageMutations() {
    const queryClient = useQueryClient();

    const snapshotMessages = async () => {
        await queryClient.cancelQueries({ queryKey: messagesKeys.lists() });
        return queryClient.getQueriesData({ queryKey: messagesKeys.lists() });
    };

    const restoreAndInvalidate = (previous: [any, unknown][] | undefined) => {
        previous?.forEach(([key, data]) => queryClient.setQueryData(key, data));
        // Cross-cache: restore server truth for related caches
        queryClient.invalidateQueries({ queryKey: tasksKeys.all });
        queryClient.invalidateQueries({ queryKey: ["thread-detail"] });
    };

    const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
        queryClient.invalidateQueries({ queryKey: ["thread-detail"] });
    };

    const markDone = useMutation({
        mutationFn: markMessageDone,
        onMutate: async (messageId) => {
            const previous = await snapshotMessages();
            // Optimistically remove from inbox (done messages aren't shown)
            queryClient.setQueriesData({ queryKey: messagesKeys.lists() }, (old: unknown) =>
                updateMessageInPages(old, messageId, (msg) => ({ ...msg, status: "done" as const }))
            );
            return { previous };
        },
        onError: (_err, _id, ctx) => restoreAndInvalidate(ctx?.previous),
        onSettled: invalidateAll,
    });

    const archive = useMutation({
        mutationFn: archiveMessage,
        onMutate: async (messageId) => {
            const previous = await snapshotMessages();
            queryClient.setQueriesData({ queryKey: messagesKeys.lists() }, (old: unknown) =>
                updateMessageInPages(old, messageId, (msg) => ({ ...msg, status: "archived" as const }))
            );
            return { previous };
        },
        onError: (_err, _id, ctx) => restoreAndInvalidate(ctx?.previous),
        onSettled: invalidateAll,
    });

    const restore = useMutation({
        mutationFn: restoreMessage,
        onMutate: async (messageId) => {
            const previous = await snapshotMessages();
            queryClient.setQueriesData({ queryKey: messagesKeys.lists() }, (old: unknown) =>
                updateMessageInPages(old, messageId, (msg) => ({ ...msg, status: "inbox" as const }))
            );
            return { previous };
        },
        onSuccess: () => {
            toast.success("Message restored to Inbox");
        },
        onError: (_err, _id, ctx) => restoreAndInvalidate(ctx?.previous),
        onSettled: invalidateAll,
    });

    const remove = useMutation({
        mutationFn: deleteMessage,
        onMutate: async (messageId) => {
            const previous = await snapshotMessages();
            // Optimistically remove entirely
            queryClient.setQueriesData({ queryKey: messagesKeys.lists() }, (old: unknown) =>
                updateMessageInPages(old, messageId, null)
            );
            return { previous };
        },
        onError: (_err, _id, ctx) => restoreAndInvalidate(ctx?.previous),
        onSettled: invalidateAll,
    });

    return { markDone, archive, restore, remove };
}
