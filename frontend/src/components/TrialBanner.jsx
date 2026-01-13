import { useState } from 'react';
import { useSubscription } from '../contexts/SubscriptionContext';
import { formatDaysRemaining, getTrialUrgency } from '../utils/subscription';

export default function TrialBanner() {
    const {
        isTrialUser,
        isActive,
        daysRemaining,
        createCheckout,
    } = useSubscription();

    const [loading, setLoading] = useState(false);
    const [dismissed, setDismissed] = useState(false);

    // Don't show if not a trial user, trial expired, or dismissed
    if (!isTrialUser || !isActive || dismissed) {
        return null;
    }

    const urgency = getTrialUrgency(daysRemaining);

    const handleUpgrade = async () => {
        setLoading(true);
        try {
            const successUrl = `${window.location.origin}/checkout-success`;
            const cancelUrl = `${window.location.origin}/dashboard`;
            const checkoutUrl = await createCheckout(successUrl, cancelUrl);
            window.location.href = checkoutUrl;
        } catch (err) {
            console.error('Failed to create checkout:', err);
            setLoading(false);
        }
    };

    const getBannerStyle = () => {
        switch (urgency) {
            case 'high':
                return 'bg-red-50 border-red-200 text-red-800';
            case 'medium':
                return 'bg-yellow-50 border-yellow-200 text-yellow-800';
            default:
                return 'bg-blue-50 border-blue-200 text-blue-800';
        }
    };

    const getButtonStyle = () => {
        switch (urgency) {
            case 'high':
                return 'bg-red-600 hover:bg-red-700';
            case 'medium':
                return 'bg-yellow-600 hover:bg-yellow-700';
            default:
                return 'bg-blue-600 hover:bg-blue-700';
        }
    };

    return (
        <div className={`border-b px-4 py-2 flex items-center justify-between ${getBannerStyle()}`}>
            <div className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                        clipRule="evenodd"
                    />
                </svg>
                <span className="text-sm font-medium">
                    {formatDaysRemaining(daysRemaining)} in your free trial
                </span>
            </div>

            <div className="flex items-center gap-2">
                <button
                    onClick={handleUpgrade}
                    disabled={loading}
                    className={`px-3 py-1 text-sm text-white rounded-md disabled:opacity-50 ${getButtonStyle()}`}
                >
                    {loading ? 'Loading...' : 'Upgrade to Pro'}
                </button>
                <button
                    onClick={() => setDismissed(true)}
                    className="p-1 hover:opacity-70"
                    aria-label="Dismiss"
                >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path
                            fillRule="evenodd"
                            d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                            clipRule="evenodd"
                        />
                    </svg>
                </button>
            </div>
        </div>
    );
}
