export default function CheckoutCancel({ onNavigate }) {
    return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-gray-50">
            <div className="bg-white rounded-xl shadow-lg max-w-md w-full p-8 text-center">
                {/* Info icon */}
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
                    <svg
                        className="w-8 h-8 text-gray-500"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M6 18L18 6M6 6l12 12"
                        />
                    </svg>
                </div>

                <h1 className="text-xl font-bold text-gray-900 mb-2">
                    Checkout Canceled
                </h1>
                <p className="text-gray-600 mb-6">
                    No worries! You can upgrade to Pro anytime from your settings.
                </p>

                <div className="space-y-3">
                    <button
                        onClick={() => onNavigate('dashboard')}
                        className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
                    >
                        Return to Dashboard
                    </button>
                    <button
                        onClick={() => onNavigate('billing')}
                        className="w-full py-2 px-4 text-gray-600 hover:text-gray-800 transition-colors"
                    >
                        View Subscription Options
                    </button>
                </div>
            </div>
        </div>
    );
}
