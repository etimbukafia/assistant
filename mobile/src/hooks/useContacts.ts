/**
 * Contacts Hook
 *
 * TanStack Query hook for contact intelligence operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    fetchContacts,
    updateContact,
    deleteContact,
    ContactContext,
    UpdateContactRequest,
} from '@/src/services/memory';

export const contactsKeys = {
    all: ['contacts'] as const,
    list: (category?: string) => [...contactsKeys.all, 'list', category] as const,
};

/**
 * Hook for fetching contacts
 */
export function useContacts(category?: string) {
    return useQuery({
        queryKey: contactsKeys.list(category),
        queryFn: () => fetchContacts(category),
    });
}

/**
 * Hook for contact mutations (update/delete)
 */
export function useContactMutations() {
    const queryClient = useQueryClient();

    const updateMutation = useMutation({
        mutationFn: ({ email, data }: { email: string; data: UpdateContactRequest }) =>
            updateContact(email, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: contactsKeys.all });
        },
        onError: () => {
            Alert.alert('Error', 'Failed to update contact');
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (email: string) => deleteContact(email),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: contactsKeys.all });
        },
        onError: () => {
            Alert.alert('Error', 'Failed to delete contact');
        },
    });

    return {
        updateContact: updateMutation.mutate,
        isUpdating: updateMutation.isPending,
        deleteContact: deleteMutation.mutate,
        isDeleting: deleteMutation.isPending,
    };
}
