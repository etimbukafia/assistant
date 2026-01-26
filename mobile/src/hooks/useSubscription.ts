/**
 * Subscription Hooks
 *
 * TanStack Query hooks for billing actions.
 *
 * Note: Subscription STATUS is available via AuthContext (from /settings).
 * These hooks handle billing ACTIONS (checkout, portal, trial activation).
 */

import { useMutation } from '@tanstack/react-query';
import { Alert } from 'react-native';
import {
    createCheckout,
    getPortalUrl,
    activateTrial,
    triggerInitialSync,
    CheckoutRequest,
} from '@/src/services/billing';
import { useAuth } from '@/src/context/AuthContext';

// ================================
// Billing Mutations
// ================================

/**
 * Hook for billing actions (checkout, portal, trial activation)
 */
export function useBillingActions() {
    const { refreshProfile } = useAuth();

    const checkoutMutation = useMutation({
        mutationFn: (request: CheckoutRequest) => createCheckout(request),
        onError: () => Alert.alert('Error', 'Failed to create checkout session'),
    });

    const portalMutation = useMutation({
        mutationFn: getPortalUrl,
        onError: () => Alert.alert('Error', 'Failed to open billing portal'),
    });

    const activateTrialMutation = useMutation({
        mutationFn: activateTrial,
        onSuccess: () => {
            // Refresh auth context to update subscription state
            refreshProfile();
        },
        onError: () => Alert.alert('Error', 'Failed to activate trial'),
    });

    const initialSyncMutation = useMutation({
        mutationFn: triggerInitialSync,
        onError: () => Alert.alert('Error', 'Failed to start initial sync'),
    });

    return {
        // Checkout
        createCheckout: checkoutMutation.mutate,
        createCheckoutAsync: checkoutMutation.mutateAsync,
        isCreatingCheckout: checkoutMutation.isPending,
        checkoutData: checkoutMutation.data,

        // Portal
        getPortalUrl: portalMutation.mutate,
        getPortalUrlAsync: portalMutation.mutateAsync,
        isGettingPortalUrl: portalMutation.isPending,
        portalData: portalMutation.data,

        // Trial Activation
        activateTrial: activateTrialMutation.mutate,
        activateTrialAsync: activateTrialMutation.mutateAsync,
        isActivatingTrial: activateTrialMutation.isPending,
        trialData: activateTrialMutation.data,

        // Initial Sync
        triggerInitialSync: initialSyncMutation.mutate,
        triggerInitialSyncAsync: initialSyncMutation.mutateAsync,
        isTriggering: initialSyncMutation.isPending,

        // Combined loading state
        isAnyPending:
            checkoutMutation.isPending ||
            portalMutation.isPending ||
            activateTrialMutation.isPending ||
            initialSyncMutation.isPending,
    };
}

// Legacy export for backwards compatibility
export const useSubscriptionMutations = useBillingActions;
