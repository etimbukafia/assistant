import React, { useState, useEffect } from 'react';
import CalendarPreferencesPanel from '../components/CalendarPreferencesPanel';
import PreferencesPanel from '../components/PreferencesPanel';
import { useSubscription } from '../contexts/SubscriptionContext';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../utils/api';
import { TIER_NAMES, formatDaysRemaining } from '../utils/subscription';

const SettingsView = ({ demoMode = false, onNavigate }) => {
    const { tier, daysRemaining, isTrialUser, isProUser, isCanceled } = useSubscription();
    const { user, signOut } = useAuth();

    // Settings state
    const [settings, setSettings] = useState({
        auto_approve_tasks: false,
        task_detection_instructions: '',
        reminder_preferences: {},
        enable_quick_reply_from_task: true
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState(null);

    // Gmail connection state
    const [gmailStatus, setGmailStatus] = useState({ is_authenticated: false, email: null });

    // Load settings from backend
    useEffect(() => {
        if (demoMode) {
            setLoading(false);
            return;
        }

        const loadSettings = async () => {
            try {
                const res = await api.get('/settings');
                if (res.ok) {
                    const data = await res.json();
                    setSettings({
                        auto_approve_tasks: data.auto_approve_tasks || false,
                        task_detection_instructions: data.task_detection_instructions || '',
                        reminder_preferences: data.reminder_preferences || {},
                        enable_quick_reply_from_task: data.enable_quick_reply_from_task ?? true
                    });
                }
            } catch (err) {
                console.error('Failed to load settings:', err);
            } finally {
                setLoading(false);
            }
        };

        const loadGmailStatus = async () => {
            try {
                const res = await api.get('/auth/status');
                if (res.ok) {
                    const data = await res.json();
                    setGmailStatus(data);
                }
            } catch (err) {
                console.error('Failed to load Gmail status:', err);
            }
        };

        loadSettings();
        loadGmailStatus();
    }, [demoMode]);

    // Save settings to backend
    const saveSettings = async (updates) => {
        if (demoMode) return;

        setSaving(true);
        setSaveMessage(null);

        try {
            const res = await api.put('/settings', updates);
            if (res.ok) {
                const data = await res.json();
                setSettings({
                    auto_approve_tasks: data.auto_approve_tasks || false,
                    task_detection_instructions: data.task_detection_instructions || '',
                    reminder_preferences: data.reminder_preferences || {},
                    enable_quick_reply_from_task: data.enable_quick_reply_from_task ?? true
                });
                setSaveMessage({ type: 'success', text: 'Settings saved' });
                setTimeout(() => setSaveMessage(null), 2000);
            } else {
                throw new Error('Failed to save');
            }
        } catch (err) {
            console.error('Failed to save settings:', err);
            setSaveMessage({ type: 'error', text: 'Failed to save settings' });
        } finally {
            setSaving(false);
        }
    };

    const handleToggle = (key) => {
        const newValue = !settings[key];
        setSettings(prev => ({ ...prev, [key]: newValue }));
        saveSettings({ [key]: newValue });
    };

    const handleInstructionsChange = (value) => {
        setSettings(prev => ({ ...prev, task_detection_instructions: value }));
    };

    const handleInstructionsBlur = () => {
        saveSettings({ task_detection_instructions: settings.task_detection_instructions });
    };

    const handleSignOut = async () => {
        try {
            await signOut();
            onNavigate && onNavigate('landing');
        } catch (err) {
            console.error('Sign out failed:', err);
        }
    };

    const handleConnectGmail = async () => {
        try {
            const res = await api.get('/auth/gmail');
            const { auth_url } = await res.json();
            window.location.href = auth_url;
        } catch (err) {
            console.error('Failed to start Gmail auth:', err);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 pb-24">
            <div className="bg-white border-b border-gray-200 sticky top-0 z-10 px-4 py-3 shadow-sm">
                <div className="flex items-center justify-between">
                    <h1 className="text-lg font-bold text-gray-800">Settings</h1>
                    {saveMessage && (
                        <span className={`text-sm ${saveMessage.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                            {saveMessage.text}
                        </span>
                    )}
                </div>
            </div>

            <div className="p-4 space-y-6">
                {/* Account Section */}
                {!demoMode && user && (
                    <div className="bg-white p-4 rounded-xl border border-gray-200">
                        <h3 className="font-semibold text-gray-900 mb-4">Account</h3>
                        <div className="flex items-center gap-4 mb-4">
                            {user.user_metadata?.avatar_url && (
                                <img
                                    src={user.user_metadata.avatar_url}
                                    alt="Profile"
                                    className="w-12 h-12 rounded-full"
                                />
                            )}
                            <div>
                                <div className="text-sm font-medium text-gray-800">
                                    {user.user_metadata?.full_name || user.email}
                                </div>
                                <div className="text-xs text-gray-500">{user.email}</div>
                            </div>
                        </div>
                        <button
                            onClick={handleSignOut}
                            className="text-sm text-red-600 hover:text-red-700 font-medium"
                        >
                            Sign Out
                        </button>
                    </div>
                )}

                {/* Gmail Connection */}
                {!demoMode && (
                    <div className="bg-white p-4 rounded-xl border border-gray-200">
                        <h3 className="font-semibold text-gray-900 mb-4">Gmail Connection</h3>
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-sm font-medium text-gray-800">
                                    {gmailStatus.is_authenticated ? 'Connected' : 'Not Connected'}
                                </div>
                                {gmailStatus.email && (
                                    <div className="text-xs text-gray-500">{gmailStatus.email}</div>
                                )}
                            </div>
                            {gmailStatus.is_authenticated ? (
                                <span className="px-3 py-1 text-xs font-medium text-green-700 bg-green-100 rounded-full">
                                    Active
                                </span>
                            ) : (
                                <button
                                    onClick={handleConnectGmail}
                                    className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-lg font-medium"
                                >
                                    Connect Gmail
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* Principal Memory - Preferences */}
                <PreferencesPanel demoMode={demoMode} />

                {/* Automation */}
                <div className="bg-white p-4 rounded-xl border border-gray-200">
                    <h3 className="font-semibold text-gray-900 mb-4">Automation</h3>

                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <div className="text-sm font-medium text-gray-800">Auto-Approve Tasks</div>
                            <div className="text-xs text-gray-500">Skip manual review for high confidence tasks</div>
                        </div>
                        <button
                            onClick={() => handleToggle('auto_approve_tasks')}
                            disabled={saving}
                            className={`w-11 h-6 rounded-full relative transition-colors ${settings.auto_approve_tasks ? 'bg-blue-600' : 'bg-gray-200'
                                }`}
                        >
                            <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${settings.auto_approve_tasks ? 'translate-x-6' : 'translate-x-1'
                                }`} />
                        </button>
                    </div>

                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-sm font-medium text-gray-800">Quick Reply from Task</div>
                            <div className="text-xs text-gray-500">Enable reply drafting from task cards</div>
                        </div>
                        <button
                            onClick={() => handleToggle('enable_quick_reply_from_task')}
                            disabled={saving}
                            className={`w-11 h-6 rounded-full relative transition-colors ${settings.enable_quick_reply_from_task ? 'bg-blue-600' : 'bg-gray-200'
                                }`}
                        >
                            <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${settings.enable_quick_reply_from_task ? 'translate-x-6' : 'translate-x-1'
                                }`} />
                        </button>
                    </div>
                </div>

                {/* Calendar Preferences */}
                <CalendarPreferencesPanel demoMode={demoMode} />

                {/* AI Instructions */}
                <div className="bg-white p-4 rounded-xl border border-gray-200">
                    <h3 className="font-semibold text-gray-900 mb-4">AI Instructions</h3>
                    <p className="text-xs text-gray-500 mb-2">Teach the AI how to prioritize your specific emails.</p>
                    <textarea
                        className="w-full border border-gray-200 rounded-lg p-3 text-sm h-32 focus:ring-2 focus:ring-blue-500 outline-none"
                        placeholder="e.g., Always mark emails from @investors.com as urgent..."
                        value={settings.task_detection_instructions}
                        onChange={(e) => handleInstructionsChange(e.target.value)}
                        onBlur={handleInstructionsBlur}
                    />
                </div>

                {/* Subscription Section */}
                {!demoMode && (
                    <div className="bg-white p-4 rounded-xl border border-gray-200">
                        <h3 className="font-semibold text-gray-900 mb-4">Subscription</h3>
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-sm font-medium text-gray-800">
                                    {TIER_NAMES[tier] || tier}
                                </div>
                                {isTrialUser && daysRemaining !== null && (
                                    <div className="text-xs text-gray-500">
                                        {formatDaysRemaining(daysRemaining)}
                                    </div>
                                )}
                                {isProUser && isCanceled && (
                                    <div className="text-xs text-yellow-600">
                                        Subscription canceled
                                    </div>
                                )}
                            </div>
                            <button
                                onClick={() => onNavigate && onNavigate('billing')}
                                className="px-4 py-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
                            >
                                Manage
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SettingsView;
