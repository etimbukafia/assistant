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
import { useAuth } from '@/src/context/AuthContext';

// Demo contacts for sandbox mode
const SANDBOX_CONTACTS: ContactContext[] = [
    {
        id: 1,
        contact_email: 'sarah.chen@acme.com',
        contact_name: 'Sarah Chen',
        category: 'vip',
        preferred_tone: 'formal',
        notes: null,
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:00:00Z',
    },
    {
        id: 2,
        contact_email: 'mike.wilson@partner.io',
        contact_name: 'Mike Wilson',
        category: 'colleague',
        preferred_tone: 'casual',
        notes: null,
        created_at: '2024-01-10T14:30:00Z',
        updated_at: '2024-01-10T14:30:00Z',
    },
];

export const contactsKeys = {
    all: ['contacts'] as const,
    list: (category?: string) => [...contactsKeys.all, 'list', category] as const,
};

/**
 * Hook for fetching contacts
 */
export function useContacts(category?: string) {
    const { isSandbox } = useAuth();

    const query = useQuery({
        queryKey: contactsKeys.list(category),
        queryFn: () => fetchContacts(category),
        enabled: !isSandbox, // Disable API calls in sandbox mode
    });

    // Return sandbox data when in sandbox mode
    if (isSandbox) {
        return {
            ...query,
            data: { contacts: SANDBOX_CONTACTS, total: SANDBOX_CONTACTS.length },
            isLoading: false,
            error: null,
        };
    }

    return query;
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
