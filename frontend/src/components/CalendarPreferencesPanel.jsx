import React, { useState, useEffect } from 'react';
import { Calendar, Clock, Globe, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { API_BASE_URL } from '../utils/constants';

/**
 * CalendarPreferencesPanel
 *
 * Settings panel for calendar-related preferences.
 * Allows users to configure:
 * - Default meeting duration
 * - Preferred meeting times (morning/afternoon/any)
 * - Buffer time between meetings
 * - Working hours
 * - Timezone
 * - Which calendars to check for availability
 */
const CalendarPreferencesPanel = () => {
    const [settings, setSettings] = useState(null);
    const [calendars, setCalendars] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    // Common timezones for quick selection
    const commonTimezones = [
        { value: 'UTC', label: 'UTC' },
        { value: 'Africa/Johannesburg', label: 'South Africa (SAST)' },
        { value: 'Europe/London', label: 'London (GMT/BST)' },
        { value: 'America/New_York', label: 'New York (EST/EDT)' },
        { value: 'America/Los_Angeles', label: 'Los Angeles (PST/PDT)' },
        { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
        { value: 'Australia/Sydney', label: 'Sydney (AEST/AEDT)' },
    ];

    useEffect(() => {
        fetchSettings();
        fetchCalendars();
    }, []);

    const fetchSettings = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/calendar/settings`);
            if (!res.ok) throw new Error('Failed to fetch settings');
            const data = await res.json();
            setSettings(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchCalendars = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/calendar/calendars`);
            if (!res.ok) throw new Error('Failed to fetch calendars');
            const data = await res.json();
            setCalendars(data.calendars || []);
        } catch (err) {
            console.log('Could not fetch calendars:', err.message);
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        setSuccess(false);

        try {
            const res = await fetch(`${API_BASE_URL}/calendar/settings`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (!res.ok) throw new Error('Failed to save settings');

            setSuccess(true);
            setTimeout(() => setSuccess(false), 3000);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsSaving(false);
        }
    };

    const handleChange = (field, value) => {
        setSettings(prev => ({ ...prev, [field]: value }));
    };

    const toggleCalendar = (calendarId) => {
        const current = settings?.calendar_ids || [];
        const updated = current.includes(calendarId)
            ? current.filter(id => id !== calendarId)
            : [...current, calendarId];
        handleChange('calendar_ids', updated);
    };

    if (isLoading) {
        return (
            <div className="bg-white p-4 rounded-xl border border-gray-200">
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white p-4 rounded-xl border border-gray-200">
            <div className="flex items-center gap-2 mb-4">
                <Calendar className="w-5 h-5 text-blue-600" />
                <h3 className="font-semibold text-gray-900">Calendar Settings</h3>
            </div>

            {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                </div>
            )}

            {success && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700 text-sm">
                    <CheckCircle className="w-4 h-4" />
                    Settings saved successfully
                </div>
            )}

            <div className="space-y-4">
                {/* Default Meeting Duration */}
                <div>
                    <label className="text-sm font-medium text-gray-700 mb-1 block">
                        Default Meeting Duration
                    </label>
                    <select
                        value={settings?.default_meeting_duration || 30}
                        onChange={(e) => handleChange('default_meeting_duration', parseInt(e.target.value))}
                        className="w-full border border-gray-200 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                        <option value={15}>15 minutes</option>
                        <option value={30}>30 minutes</option>
                        <option value={45}>45 minutes</option>
                        <option value={60}>1 hour</option>
                        <option value={90}>1.5 hours</option>
                    </select>
                </div>

                {/* Preferred Meeting Times */}
                <div>
                    <label className="text-sm font-medium text-gray-700 mb-1 block">
                        Preferred Meeting Times
                    </label>
                    <div className="flex gap-2">
                        {['morning', 'afternoon', 'any'].map((time) => (
                            <button
                                key={time}
                                onClick={() => handleChange('preferred_meeting_times', time)}
                                className={`
                                    flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors
                                    ${settings?.preferred_meeting_times === time
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                    }
                                `}
                            >
                                {time.charAt(0).toUpperCase() + time.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Buffer Time */}
                <div>
                    <label className="text-sm font-medium text-gray-700 mb-1 block">
                        Buffer Between Meetings
                    </label>
                    <select
                        value={settings?.buffer_minutes || 15}
                        onChange={(e) => handleChange('buffer_minutes', parseInt(e.target.value))}
                        className="w-full border border-gray-200 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                        <option value={0}>No buffer</option>
                        <option value={5}>5 minutes</option>
                        <option value={10}>10 minutes</option>
                        <option value={15}>15 minutes</option>
                        <option value={30}>30 minutes</option>
                    </select>
                </div>

                {/* Working Hours */}
                <div>
                    <label className="text-sm font-medium text-gray-700 mb-1 block">
                        Working Hours
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">Start</label>
                            <input
                                type="time"
                                value={settings?.working_hours_start || '09:00'}
                                onChange={(e) => handleChange('working_hours_start', e.target.value)}
                                className="w-full border border-gray-200 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            />
                        </div>
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">End</label>
                            <input
                                type="time"
                                value={settings?.working_hours_end || '17:00'}
                                onChange={(e) => handleChange('working_hours_end', e.target.value)}
                                className="w-full border border-gray-200 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            />
                        </div>
                    </div>
                </div>

                {/* Timezone */}
                <div>
                    <label className="text-sm font-medium text-gray-700 mb-1 block flex items-center gap-1">
                        <Globe className="w-4 h-4" />
                        Timezone
                    </label>
                    <select
                        value={settings?.default_timezone || 'UTC'}
                        onChange={(e) => handleChange('default_timezone', e.target.value)}
                        className="w-full border border-gray-200 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                        {commonTimezones.map((tz) => (
                            <option key={tz.value} value={tz.value}>
                                {tz.label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Calendar Selection */}
                {calendars.length > 0 && (
                    <div>
                        <label className="text-sm font-medium text-gray-700 mb-2 block">
                            Calendars to Check
                        </label>
                        <div className="space-y-2">
                            {calendars.map((cal) => (
                                <label
                                    key={cal.id}
                                    className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                                >
                                    <input
                                        type="checkbox"
                                        checked={(settings?.calendar_ids || []).includes(cal.id)}
                                        onChange={() => toggleCalendar(cal.id)}
                                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                                    />
                                    <span className="text-sm text-gray-700">{cal.summary}</span>
                                    {cal.primary && (
                                        <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                                            Primary
                                        </span>
                                    )}
                                </label>
                            ))}
                        </div>
                    </div>
                )}

                {/* Save Button */}
                <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {isSaving ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Saving...
                        </>
                    ) : (
                        'Save Calendar Settings'
                    )}
                </button>
            </div>
        </div>
    );
};

export default CalendarPreferencesPanel;
