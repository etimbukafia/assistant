import { useEffect } from 'react';
import { useSubscription } from '../contexts/SubscriptionContext';

export default function CheckoutSuccess({ onNavigate }) {
    const { refresh } = useSubscription();

    useEffect(() => {
        // Refresh subscription state after successful checkout
        refresh();
    }, [refresh]);

    return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-blue-50 to-indigo-100">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-8 text-center">
                {/* Success icon */}
                <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                    <svg
                        className="w-10 h-10 text-green-500"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                        />
                    </svg>
                </div>

                <h1 className="text-2xl font-bold text-gray-900 mb-2">
                    Welcome to Pro!
                </h1>
                <p className="text-gray-600 mb-6">
                    Your subscription is now active. You have full access to all features.
                </p>

                <div className="space-y-3">
                    <button
                        onClick={() => onNavigate('dashboard')}
                        className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
                    >
                        Go to Dashboard
                    </button>
                    <button
                        onClick={() => onNavigate('billing')}
                        className="w-full py-2 px-4 text-gray-600 hover:text-gray-800 transition-colors"
                    >
                        View Subscription Details
                    </button>
                </div>
            </div>
        </div>
    );
}
