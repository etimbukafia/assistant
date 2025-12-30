import React from 'react';
import { Sparkles, Plus } from 'lucide-react';

/**
 * ExtractedTaskSuggestion - Displays raw AI-extracted tasks as read-only suggestions
 *
 * These are NOT actionable tasks - they are context/transparency only.
 * Users can approve them to convert to real Task objects.
 */
const ExtractedTaskSuggestion = ({ text, onApprove, messageId }) => {
    const handleApprove = (e) => {
        e.stopPropagation();
        if (onApprove) {
            onApprove(messageId, text);
        }
    };

    return (
        <div className="mt-2 bg-gray-50 border border-gray-200 border-dashed rounded-lg p-3">
            <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                    <Sparkles className="w-4 h-4 text-gray-400" />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">
                            Detected by AI
                        </span>
                    </div>
                    <p className="text-sm text-gray-600 italic">
                        "{text}"
                    </p>
                </div>
                <button
                    onClick={handleApprove}
                    className="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 transition-colors"
                    title="Approve as task"
                >
                    <Plus className="w-3 h-3" />
                    Approve
                </button>
            </div>
        </div>
    );
};

export default ExtractedTaskSuggestion;
