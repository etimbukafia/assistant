import { useMutation, useQueryClient } from "@tanstack/react-query";
import { approveTask, dismissTask } from "@/services/tasks";
import { messagesKeys } from "./useInbox";

export function useTaskMutations() {
    const queryClient = useQueryClient();

    const invalidateLists = () => {
        // Tasks affect the message list (e.g. Needs Reply status might change)
        queryClient.invalidateQueries({ queryKey: messagesKeys.lists() });
    };

    const approve = useMutation({
        mutationFn: approveTask,
        onSuccess: invalidateLists,
    });

    const dismiss = useMutation({
        mutationFn: dismissTask,
        onSuccess: invalidateLists,
    });

    return {
        approve,
        dismiss,
    };
}
