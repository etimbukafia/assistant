import React from 'react';
import CalendarPreferencesPanel from '../components/CalendarPreferencesPanel';
import PreferencesPanel from '../components/PreferencesPanel';

const SettingsView = ({ demoMode = false }) => (
    <div className="min-h-screen bg-gray-50 pb-24">
        <div className="bg-white border-b border-gray-200 sticky top-0 z-10 px-4 py-3 shadow-sm">
            <h1 className="text-lg font-bold text-gray-800">Settings</h1>
        </div>

        <div className="p-4 space-y-6">
            {/* Principal Memory - Preferences */}
            <PreferencesPanel demoMode={demoMode} />

            <div className="bg-white p-4 rounded-xl border border-gray-200">
                <h3 className="font-semibold text-gray-900 mb-4">Automation</h3>
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <div className="text-sm font-medium text-gray-800">Auto-Approve Tasks</div>
                        <div className="text-xs text-gray-500">Skip manual review for high confidence tasks</div>
                    </div>
                    <div className="w-11 h-6 bg-gray-200 rounded-full relative">
                        <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm" />
                    </div>
                </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-gray-200">
                <h3 className="font-semibold text-gray-900 mb-4">Quiet Hours</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-xs text-gray-500 mb-1 block">Start</label>
                        <input type="time" defaultValue="22:00" className="w-full border rounded-lg p-2 text-sm" />
                    </div>
                    <div>
                        <label className="text-xs text-gray-500 mb-1 block">End</label>
                        <input type="time" defaultValue="08:00" className="w-full border rounded-lg p-2 text-sm" />
                    </div>
                </div>
            </div>

            {/* Calendar Preferences */}
            <CalendarPreferencesPanel demoMode={demoMode} />

            <div className="bg-white p-4 rounded-xl border border-gray-200">
                <h3 className="font-semibold text-gray-900 mb-4">AI Instructions</h3>
                <p className="text-xs text-gray-500 mb-2">Teach the AI how to prioritize your specific emails.</p>
                <textarea
                    className="w-full border border-gray-200 rounded-lg p-3 text-sm h-32 focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="e.g., Always mark emails from @investors.com as urgent..."
                ></textarea>
            </div>
        </div>
    </div>
);

export default SettingsView;
