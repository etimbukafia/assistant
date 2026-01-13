import { useState } from 'react';
import { useSubscription } from '../contexts/SubscriptionContext';
import {
    TIER_NAMES,
    STATUS_LABELS,
    PRO_FEATURES,
    formatDaysRemaining,
    formatExpiryDate,
    getStatusColor,
} from '../utils/subscription';

export default function BillingView() {
    const {
        tier,
        status,
        isActive,
        trialEndsAt,
        expiresAt,
        daysRemaining,
        isProUser,
        isTrialUser,
        isCanceled,
        loading,
        createCheckout,
        cancelSubscription,
        getPortalUrl,
    } = useSubscription();

    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showCancelConfirm, setShowCancelConfirm] = useState(false);

    const handleUpgrade = async () => {
        setActionLoading(true);
        setError(null);

        try {
            const successUrl = `${window.location.origin}/checkout-success`;
            const cancelUrl = `${window.location.origin}/billing`;
            const checkoutUrl = await createCheckout(successUrl, cancelUrl);
            window.location.href = checkoutUrl;
        } catch (err) {
            setError(err.message);
            setActionLoading(false);
        }
    };

    const handleManageBilling = async () => {
        setActionLoading(true);
        setError(null);

        try {
            const portalUrl = await getPortalUrl();
            window.open(portalUrl, '_blank');
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(false);
        }
    };

    const handleCancel = async () => {
        setActionLoading(true);
        setError(null);

        try {
            await cancelSubscription();
            setShowCancelConfirm(false);
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="max-w-2xl mx-auto p-6">
                <div className="animate-pulse">
                    <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
                    <div className="h-40 bg-gray-200 rounded mb-6"></div>
                    <div className="h-60 bg-gray-200 rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto p-6">
            <h1 className="text-2xl font-bold mb-6">Billing & Subscription</h1>

            {error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                    {error}
                </div>
            )}

            {/* Current Plan Card */}
            <div className="bg-white rounded-lg shadow p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h2 className="text-lg font-semibold">Current Plan</h2>
                        <p className="text-2xl font-bold text-blue-600">
                            {TIER_NAMES[tier] || tier}
                        </p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(status)}`}>
                        {STATUS_LABELS[status] || status}
                    </span>
                </div>

                {/* Trial info */}
                {isTrialUser && trialEndsAt && (
                    <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                        <p className="text-sm text-blue-800">
                            <span className="font-medium">Trial ends:</span>{' '}
                            {formatExpiryDate(trialEndsAt)}
                            {daysRemaining !== null && (
                                <span className="ml-2">({formatDaysRemaining(daysRemaining)})</span>
                            )}
                        </p>
                    </div>
                )}

                {/* Pro subscription info */}
                {isProUser && (
                    <div className="mt-4">
                        {isCanceled && expiresAt ? (
                            <p className="text-sm text-yellow-700 bg-yellow-50 p-3 rounded-lg">
                                Your subscription is canceled. You'll have access until{' '}
                                <span className="font-medium">{formatExpiryDate(expiresAt)}</span>.
                            </p>
                        ) : expiresAt ? (
                            <p className="text-sm text-gray-600">
                                Next billing date: {formatExpiryDate(expiresAt)}
                            </p>
                        ) : null}
                    </div>
                )}

                {/* Action buttons */}
                <div className="mt-6 flex flex-wrap gap-3">
                    {isTrialUser && (
                        <button
                            onClick={handleUpgrade}
                            disabled={actionLoading}
                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {actionLoading ? 'Loading...' : 'Upgrade to Pro'}
                        </button>
                    )}

                    {isProUser && !isCanceled && (
                        <>
                            <button
                                onClick={handleManageBilling}
                                disabled={actionLoading}
                                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
                            >
                                Manage Billing
                            </button>
                            <button
                                onClick={() => setShowCancelConfirm(true)}
                                disabled={actionLoading}
                                className="px-4 py-2 text-red-600 hover:text-red-700"
                            >
                                Cancel Subscription
                            </button>
                        </>
                    )}

                    {isProUser && isCanceled && (
                        <button
                            onClick={handleUpgrade}
                            disabled={actionLoading}
                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                        >
                            {actionLoading ? 'Loading...' : 'Resubscribe'}
                        </button>
                    )}
                </div>
            </div>

            {/* Features List */}
            <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold mb-4">Included Features</h2>
                <ul className="space-y-3">
                    {PRO_FEATURES.map((feature) => (
                        <li key={feature.name} className="flex items-start">
                            <svg
                                className="w-5 h-5 text-green-500 mt-0.5 mr-3 flex-shrink-0"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                            >
                                <path
                                    fillRule="evenodd"
                                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                    clipRule="evenodd"
                                />
                            </svg>
                            <div>
                                <p className="font-medium">{feature.name}</p>
                                <p className="text-sm text-gray-500">{feature.description}</p>
                            </div>
                        </li>
                    ))}
                </ul>
            </div>

            {/* Cancel Confirmation Modal */}
            {showCancelConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg p-6 max-w-md mx-4">
                        <h3 className="text-lg font-semibold mb-2">Cancel Subscription?</h3>
                        <p className="text-gray-600 mb-4">
                            You'll keep access until the end of your current billing period.
                            You can resubscribe at any time.
                        </p>
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setShowCancelConfirm(false)}
                                disabled={actionLoading}
                                className="px-4 py-2 text-gray-600 hover:text-gray-800"
                            >
                                Keep Subscription
                            </button>
                            <button
                                onClick={handleCancel}
                                disabled={actionLoading}
                                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                            >
                                {actionLoading ? 'Canceling...' : 'Yes, Cancel'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
