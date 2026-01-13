import { useState } from 'react';
import { useSubscription } from '../contexts/SubscriptionContext';
import { PRO_FEATURES } from '../utils/subscription';

export default function TrialExpiredPrompt() {
    const { createCheckout } = useSubscription();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleUpgrade = async () => {
        setLoading(true);
        setError(null);

        try {
            const successUrl = `${window.location.origin}/checkout-success`;
            const cancelUrl = `${window.location.origin}/`;
            const checkoutUrl = await createCheckout(successUrl, cancelUrl);
            window.location.href = checkoutUrl;
        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-8">
                {/* Header */}
                <div className="text-center mb-6">
                    <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg
                            className="w-8 h-8 text-blue-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-gray-900">
                        Your Free Trial Has Ended
                    </h2>
                    <p className="text-gray-600 mt-2">
                        Upgrade to Pro to continue using all features
                    </p>
                </div>

                {/* Error message */}
                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                        {error}
                    </div>
                )}

                {/* Features list */}
                <div className="mb-6">
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
                        What you'll get
                    </h3>
                    <ul className="space-y-2">
                        {PRO_FEATURES.slice(0, 4).map((feature) => (
                            <li key={feature.name} className="flex items-center text-sm">
                                <svg
                                    className="w-4 h-4 text-green-500 mr-2 flex-shrink-0"
                                    fill="currentColor"
                                    viewBox="0 0 20 20"
                                >
                                    <path
                                        fillRule="evenodd"
                                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                                {feature.name}
                            </li>
                        ))}
                    </ul>
                </div>

                {/* CTA Button */}
                <button
                    onClick={handleUpgrade}
                    disabled={loading}
                    className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    {loading ? (
                        <span className="flex items-center justify-center">
                            <svg
                                className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                                fill="none"
                                viewBox="0 0 24 24"
                            >
                                <circle
                                    className="opacity-25"
                                    cx="12"
                                    cy="12"
                                    r="10"
                                    stroke="currentColor"
                                    strokeWidth="4"
                                />
                                <path
                                    className="opacity-75"
                                    fill="currentColor"
                                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                />
                            </svg>
                            Loading...
                        </span>
                    ) : (
                        'Upgrade to Pro'
                    )}
                </button>

                <p className="text-xs text-gray-500 text-center mt-4">
                    Secure checkout powered by Polar
                </p>
            </div>
        </div>
    );
}
