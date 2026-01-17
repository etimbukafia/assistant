import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Save, X, Sparkles } from 'lucide-react';
import { api } from '../utils/api';

const CONTEXT_TYPES = [
    { value: 'drafting', label: 'Email Drafting', description: 'Tone, length, sign-off preferences' },
    { value: 'scheduling', label: 'Scheduling', description: 'Meeting time preferences' },
    { value: 'task_review', label: 'Task Review', description: 'How tasks are handled' }
];

const PRESET_KEYS = {
    drafting: [
        { key: 'tone', label: 'Tone', examples: 'formal, casual, friendly' },
        { key: 'reply_length', label: 'Reply Length', examples: 'concise, detailed' },
        { key: 'sign_off', label: 'Sign-off', examples: 'Best regards, Cheers' },
        { key: 'greeting', label: 'Greeting Style', examples: 'Hi [Name], Dear [Name]' }
    ],
    scheduling: [
        { key: 'no_meeting_days', label: 'No Meeting Days', examples: 'Fridays, Mondays' },
        { key: 'preferred_meeting_times', label: 'Preferred Times', examples: 'morning, afternoon' }
    ],
    task_review: [
        { key: 'priority_keywords', label: 'High Priority Keywords', examples: 'urgent, ASAP, deadline' }
    ]
};

const PreferenceItem = ({ preference, onEdit, onDelete }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(preference.value);

    const handleSave = () => {
        onEdit(preference.id, editValue);
        setIsEditing(false);
    };

    return (
        <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
            <div className="flex-1">
                <div className="text-sm font-medium text-gray-700 capitalize">
                    {preference.key.replace(/_/g, ' ')}
                </div>
                {isEditing ? (
                    <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="mt-1 w-full text-sm border rounded px-2 py-1 focus:ring-2 focus:ring-blue-500 outline-none"
                        autoFocus
                    />
                ) : (
                    <div className="text-sm text-gray-600">{preference.value}</div>
                )}
            </div>
            <div className="flex items-center gap-1 ml-2">
                {isEditing ? (
                    <>
                        <button onClick={handleSave} className="p-1.5 text-green-600 hover:bg-green-100 rounded">
                            <Save className="w-4 h-4" />
                        </button>
                        <button onClick={() => setIsEditing(false)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded">
                            <X className="w-4 h-4" />
                        </button>
                    </>
                ) : (
                    <>
                        <button onClick={() => setIsEditing(true)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded">
                            <Edit2 className="w-4 h-4" />
                        </button>
                        <button onClick={() => onDelete(preference.id)} className="p-1.5 text-red-500 hover:bg-red-100 rounded">
                            <Trash2 className="w-4 h-4" />
                        </button>
                    </>
                )}
            </div>
            {preference.source === 'approved_suggestion' && (
                <Sparkles className="w-3 h-3 text-purple-500 ml-2" title="Learned from your behavior" />
            )}
        </div>
    );
};

const AddPreferenceForm = ({ contextType, onAdd, onCancel }) => {
    const [key, setKey] = useState('');
    const [customKey, setCustomKey] = useState('');
    const [value, setValue] = useState('');

    const presets = PRESET_KEYS[contextType] || [];

    const handleSubmit = (e) => {
        e.preventDefault();
        const finalKey = key === 'custom' ? customKey : key;
        if (finalKey && value) {
            onAdd(finalKey, value, contextType);
            setKey('');
            setCustomKey('');
            setValue('');
        }
    };

    return (
        <form onSubmit={handleSubmit} className="p-3 bg-blue-50 rounded-lg border border-blue-100 space-y-3">
            <div>
                <label className="text-xs text-gray-600 mb-1 block">Preference Type</label>
                <select
                    value={key}
                    onChange={(e) => setKey(e.target.value)}
                    className="w-full text-sm border rounded px-2 py-1.5 focus:ring-2 focus:ring-blue-500 outline-none"
                >
                    <option value="">Select a preference...</option>
                    {presets.map(p => (
                        <option key={p.key} value={p.key}>{p.label} ({p.examples})</option>
                    ))}
                    <option value="custom">Custom...</option>
                </select>
            </div>

            {key === 'custom' && (
                <div>
                    <label className="text-xs text-gray-600 mb-1 block">Custom Key</label>
                    <input
                        type="text"
                        value={customKey}
                        onChange={(e) => setCustomKey(e.target.value)}
                        placeholder="e.g., email_signature"
                        className="w-full text-sm border rounded px-2 py-1.5 focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                </div>
            )}

            <div>
                <label className="text-xs text-gray-600 mb-1 block">Value</label>
                <input
                    type="text"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder="Enter preference value..."
                    className="w-full text-sm border rounded px-2 py-1.5 focus:ring-2 focus:ring-blue-500 outline-none"
                />
            </div>

            <div className="flex gap-2">
                <button
                    type="submit"
                    disabled={!((key && key !== 'custom') || customKey) || !value}
                    className="flex-1 bg-blue-600 text-white py-1.5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Add Preference
                </button>
                <button
                    type="button"
                    onClick={onCancel}
                    className="px-3 bg-gray-200 text-gray-700 py-1.5 rounded text-sm font-medium"
                >
                    Cancel
                </button>
            </div>
        </form>
    );
};

const PreferencesPanel = ({ demoMode = false }) => {
    const [preferences, setPreferences] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [expandedContext, setExpandedContext] = useState('drafting');
    const [showAddForm, setShowAddForm] = useState(null);

    useEffect(() => {
        fetchPreferences();
    }, []);

    const fetchPreferences = async () => {
        if (demoMode) {
            setPreferences([
                { id: 1, key: 'tone', value: 'professional but friendly', context_type: 'drafting', source: 'manual' },
                { id: 2, key: 'sign_off', value: 'Best regards', context_type: 'drafting', source: 'manual' }
            ]);
            setLoading(false);
            return;
        }

        try {
            const res = await api.get('/memory/preferences');
            if (!res.ok) throw new Error('Failed to fetch preferences');
            const data = await res.json();
            setPreferences(data.preferences || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const addPreference = async (key, value, contextType) => {
        if (demoMode) {
            const newPref = {
                id: Date.now(),
                key,
                value,
                context_type: contextType,
                source: 'manual'
            };
            setPreferences(prev => [...prev, newPref]);
            setShowAddForm(null);
            return;
        }

        try {
            const res = await api.post('/memory/preferences', { key, value, context_type: contextType, source: 'manual' });
            if (!res.ok) throw new Error('Failed to add preference');
            const newPref = await res.json();
            setPreferences(prev => [...prev, newPref]);
            setShowAddForm(null);
        } catch (err) {
            setError(err.message);
        }
    };

    const updatePreference = async (id, value) => {
        if (demoMode) {
            setPreferences(prev => prev.map(p => p.id === id ? { ...p, value } : p));
            return;
        }

        try {
            const res = await api.put(`/memory/preferences/${id}`, { value });
            if (!res.ok) throw new Error('Failed to update preference');
            const updated = await res.json();
            setPreferences(prev => prev.map(p => p.id === id ? updated : p));
        } catch (err) {
            setError(err.message);
        }
    };

    const deletePreference = async (id) => {
        if (demoMode) {
            setPreferences(prev => prev.filter(p => p.id !== id));
            return;
        }

        try {
            const res = await api.delete(`/memory/preferences/${id}`);
            if (!res.ok) throw new Error('Failed to delete preference');
            setPreferences(prev => prev.filter(p => p.id !== id));
        } catch (err) {
            setError(err.message);
        }
    };

    if (loading) {
        return (
            <div className="bg-white p-4 rounded-xl border border-gray-200">
                <div className="animate-pulse">
                    <div className="h-5 bg-gray-200 rounded w-1/3 mb-4"></div>
                    <div className="h-10 bg-gray-100 rounded mb-2"></div>
                    <div className="h-10 bg-gray-100 rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white p-4 rounded-xl border border-gray-200">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900">Your Preferences</h3>
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                    {preferences.length} saved
                </span>
            </div>

            {error && (
                <div className="mb-4 p-2 bg-red-50 text-red-700 text-sm rounded">
                    {error}
                </div>
            )}

            <p className="text-xs text-gray-500 mb-4">
                Preferences personalize AI-generated drafts and scheduling suggestions.
            </p>

            {/* Context Type Tabs */}
            <div className="flex gap-2 mb-4 overflow-x-auto">
                {CONTEXT_TYPES.map(ct => (
                    <button
                        key={ct.value}
                        onClick={() => setExpandedContext(ct.value)}
                        className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${expandedContext === ct.value
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                    >
                        {ct.label}
                    </button>
                ))}
            </div>

            {/* Preferences for selected context */}
            <div className="space-y-2">
                {preferences
                    .filter(p => p.context_type === expandedContext)
                    .map(pref => (
                        <PreferenceItem
                            key={pref.id}
                            preference={pref}
                            onEdit={updatePreference}
                            onDelete={deletePreference}
                        />
                    ))
                }

                {preferences.filter(p => p.context_type === expandedContext).length === 0 && !showAddForm && (
                    <div className="text-center py-6 text-gray-400 text-sm">
                        No preferences set for {CONTEXT_TYPES.find(c => c.value === expandedContext)?.label}
                    </div>
                )}

                {showAddForm === expandedContext ? (
                    <AddPreferenceForm
                        contextType={expandedContext}
                        onAdd={addPreference}
                        onCancel={() => setShowAddForm(null)}
                    />
                ) : (
                    <button
                        onClick={() => setShowAddForm(expandedContext)}
                        className="w-full flex items-center justify-center gap-2 py-2 border-2 border-dashed border-gray-200 rounded-lg text-gray-500 hover:border-blue-300 hover:text-blue-600 transition-colors"
                    >
                        <Plus className="w-4 h-4" />
                        Add Preference
                    </button>
                )}
            </div>
        </div>
    );
};

export default PreferencesPanel;
