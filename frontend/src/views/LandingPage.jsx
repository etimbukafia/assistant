import React from 'react';
import { Mail } from 'lucide-react';

const LandingPage = ({ onConnect, demoMode, setDemoMode }) => (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-6 text-center">
        <div className="bg-white p-8 rounded-2xl shadow-xl max-w-md w-full">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Mail className="w-8 h-8 text-blue-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Inbox Brain</h1>
            <p className="text-gray-500 mb-8">
                AI assistant for executive assistants. Connect your Gmail to get started.
            </p>

            <button
                onClick={onConnect}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-colors"
            >
                <Mail className="w-5 h-5" />
                Connect Gmail
            </button>

            <div className="mt-8 pt-6 border-t border-gray-100">
                <label className="flex items-center justify-center gap-2 cursor-pointer text-sm text-gray-600">
                    <input
                        type="checkbox"
                        checked={demoMode}
                        onChange={(e) => setDemoMode(e.target.checked)}
                        className="rounded text-blue-600 focus:ring-blue-500"
                    />
                    <span>Use Demo Mode (No Backend Required)</span>
                </label>
            </div>
        </div>
    </div>
);

export default LandingPage;
