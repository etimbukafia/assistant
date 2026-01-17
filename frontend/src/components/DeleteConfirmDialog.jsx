import React, { useState, useEffect } from 'react';
import { AlertTriangle, Archive, Trash2, X } from 'lucide-react';
import { api } from '../utils/api';

const PREF_KEY = 'skip_delete_confirmation';

const DeleteConfirmDialog = ({
    isOpen,
    onClose,
    onConfirm,
    onArchive,
    messageSubject = "this message",
    tasksCount = 0,
    suggestionsCount = 0,
    demoMode = false
}) => {
    const [dontShowAgain, setDontShowAgain] = useState(false);
    const [skipDialog, setSkipDialog] = useState(false);
    const [checkingPref, setCheckingPref] = useState(true);

    // Check if user has "skip" preference saved
    useEffect(() => {
        const checkPreference = async () => {
            if (demoMode) {
                setCheckingPref(false);
                return;
            }

            try {
                const res = await api.get('/memory/preferences?context_type=task_review');
                if (res.ok) {
                    const data = await res.json();
                    const skipPref = (data.preferences || []).find(p => p.key === PREF_KEY);
                    if (skipPref?.value === 'true') {
                        setSkipDialog(true);
                    }
                }
            } catch (err) {
                console.error('Failed to check delete preference:', err);
            } finally {
                setCheckingPref(false);
            }
        };

        if (isOpen) {
            checkPreference();
        }
    }, [isOpen, demoMode]);

    // Auto-confirm if user chose to skip
    useEffect(() => {
        if (isOpen && !checkingPref && skipDialog) {
            onConfirm();
        }
    }, [isOpen, checkingPref, skipDialog]);

    if (!isOpen || checkingPref) return null;
    if (skipDialog) return null;

    const handleConfirm = async () => {
        if (dontShowAgain && !demoMode) {
            // Save preference to backend
            try {
                await api.post('/memory/preferences', {
                    key: PREF_KEY,
                    value: 'true',
                    context_type: 'task_review',
                    source: 'manual'
                });
            } catch (err) {
                console.error('Failed to save preference:', err);
            }
        }
        onConfirm();
    };

    const hasRelatedData = tasksCount > 0 || suggestionsCount > 0;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
                {/* Header */}
                <div className="flex items-start gap-3 mb-4">
                    <div className="p-2 bg-red-100 rounded-full">
                        <AlertTriangle className="w-5 h-5 text-red-600" />
                    </div>
                    <div className="flex-1">
                        <h3 className="font-semibold text-gray-900">Delete Message?</h3>
                        <p className="text-sm text-gray-600 mt-1">
                            This will permanently delete "{messageSubject.slice(0, 50)}{messageSubject.length > 50 ? '...' : ''}"
                        </p>
                    </div>
                    <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
                        <X className="w-5 h-5 text-gray-400" />
                    </button>
                </div>

                {/* Related data warning */}
                {hasRelatedData && (
                    <div className="mb-4 p-3 bg-amber-50 border border-amber-100 rounded-lg">
                        <p className="text-sm text-amber-800 font-medium mb-1">
                            This will also delete:
                        </p>
                        <ul className="text-sm text-amber-700 list-disc list-inside">
                            {tasksCount > 0 && (
                                <li>{tasksCount} related task{tasksCount > 1 ? 's' : ''}</li>
                            )}
                            {suggestionsCount > 0 && (
                                <li>{suggestionsCount} scheduling suggestion{suggestionsCount > 1 ? 's' : ''}</li>
                            )}
                        </ul>
                    </div>
                )}

                {/* Archive recommendation */}
                <div className="mb-4 p-3 bg-blue-50 border border-blue-100 rounded-lg">
                    <p className="text-sm text-blue-800">
                        <strong>Tip:</strong> If you just want to hide this message, consider archiving instead.
                        Archived messages can be restored later.
                    </p>
                </div>

                {/* Don't show again checkbox */}
                <label className="flex items-center gap-2 mb-4 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={dontShowAgain}
                        onChange={(e) => setDontShowAgain(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-600">Don't show this message again</span>
                </label>

                {/* Actions */}
                <div className="flex gap-2">
                    <button
                        onClick={onArchive}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 rounded-lg font-medium hover:bg-blue-100 transition-colors"
                    >
                        <Archive className="w-4 h-4" />
                        Archive Instead
                    </button>
                    <button
                        onClick={handleConfirm}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 transition-colors"
                    >
                        <Trash2 className="w-4 h-4" />
                        Delete
                    </button>
                </div>

                {/* Cancel link */}
                <button
                    onClick={onClose}
                    className="w-full mt-3 text-sm text-gray-500 hover:text-gray-700"
                >
                    Cancel
                </button>
            </div>
        </div>
    );
};

export default DeleteConfirmDialog;
