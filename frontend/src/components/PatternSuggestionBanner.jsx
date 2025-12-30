import React, { useState, useEffect } from 'react';
import { Sparkles, Check, X, Ban } from 'lucide-react';
import { API_BASE_URL } from '../utils/constants';

/**
 * Pattern Suggestion Banner
 *
 * Displays inline suggestions based on observed user behavior patterns.
 * Phase 1: Suggest only, never auto-act.
 *
 * Example: "You often dismiss emails from newsletters. Save as preference?"
 * Actions: Save | Not now | Never suggest again
 */

const formatPatternMessage = (pattern) => {
    const { pattern_type, action, conditions, confidence } = pattern;
    const confidencePct = Math.round(confidence * 100);

    const messages = {
        dismiss_email: () => {
            const domain = conditions?.sender_domain || 'this sender';
            return `You often dismiss emails from ${domain}`;
        },
        approve_task_type: () => {
            const taskType = conditions?.task_type || 'this type';
            return `You usually approve "${taskType}" tasks quickly`;
        },
        prefer_morning: () => 'You prefer scheduling meetings in the morning',
        prefer_afternoon: () => 'You prefer scheduling meetings in the afternoon',
        shorten_draft: () => 'You tend to shorten AI-generated drafts',
        lengthen_draft: () => 'You tend to expand AI-generated drafts'
    };

    const getMessage = messages[pattern_type] || (() => `Observed pattern: ${action}`);
    return `${getMessage()} (${confidencePct}% confidence)`;
};

const formatSavedPreference = (pattern) => {
    const { pattern_type, action, conditions } = pattern;

    const descriptions = {
        dismiss_email: () => {
            const domain = conditions?.sender_domain;
            return domain ? `Auto-dismiss emails from ${domain}` : 'Auto-dismiss similar emails';
        },
        approve_task_type: () => {
            const taskType = conditions?.task_type;
            return taskType ? `Quick-approve "${taskType}" tasks` : 'Quick-approve similar tasks';
        },
        prefer_morning: () => 'Prefer morning meetings',
        prefer_afternoon: () => 'Prefer afternoon meetings',
        shorten_draft: () => 'Prefer concise replies',
        lengthen_draft: () => 'Prefer detailed replies'
    };

    const getDesc = descriptions[pattern_type] || (() => action);
    return getDesc();
};

const PatternSuggestionBanner = ({ demoMode = false, onDismissAll }) => {
    const [patterns, setPatterns] = useState([]);
    const [loading, setLoading] = useState(true);
    const [actionInProgress, setActionInProgress] = useState(null);

    useEffect(() => {
        fetchPatterns();
    }, []);

    const fetchPatterns = async () => {
        if (demoMode) {
            // Demo patterns
            setPatterns([
                {
                    id: 1,
                    pattern_key: 'dismiss_from_newsletter.com',
                    pattern_type: 'dismiss_email',
                    action: 'dismiss_from:newsletter.com',
                    conditions: { sender_domain: 'newsletter.com' },
                    occurrences: 5,
                    confidence: 0.71,
                    context_type: 'task_review'
                }
            ]);
            setLoading(false);
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/memory/patterns/suggestions`);
            if (!res.ok) throw new Error('Failed to fetch patterns');
            const data = await res.json();
            setPatterns(data.patterns || []);
        } catch (err) {
            console.error('Error fetching pattern suggestions:', err);
            setPatterns([]);
        } finally {
            setLoading(false);
        }
    };

    const handleAction = async (patternId, action) => {
        setActionInProgress(patternId);

        if (demoMode) {
            // Simulate action
            await new Promise(r => setTimeout(r, 500));
            setPatterns(prev => prev.filter(p => p.id !== patternId));
            setActionInProgress(null);
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/memory/patterns/${patternId}/action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action })
            });

            if (!res.ok) throw new Error('Failed to process action');

            // Remove from list
            setPatterns(prev => prev.filter(p => p.id !== patternId));
        } catch (err) {
            console.error('Error processing pattern action:', err);
        } finally {
            setActionInProgress(null);
        }
    };

    if (loading) {
        return null; // Don't show loading state for this
    }

    if (patterns.length === 0) {
        return null; // Nothing to suggest
    }

    return (
        <div className="space-y-2 mb-4">
            {patterns.map(pattern => (
                <div
                    key={pattern.id}
                    className="bg-purple-50 border border-purple-100 rounded-xl p-3"
                >
                    <div className="flex items-start gap-3">
                        <div className="p-1.5 bg-purple-100 rounded-lg">
                            <Sparkles className="w-4 h-4 text-purple-600" />
                        </div>

                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-purple-900 mb-1">
                                {formatPatternMessage(pattern)}
                            </div>
                            <div className="text-xs text-purple-700 mb-2">
                                Save as preference: "{formatSavedPreference(pattern)}"?
                            </div>

                            <div className="flex gap-2">
                                <button
                                    onClick={() => handleAction(pattern.id, 'approve')}
                                    disabled={actionInProgress === pattern.id}
                                    className="flex items-center gap-1 px-3 py-1 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50"
                                >
                                    <Check className="w-3 h-3" />
                                    Save
                                </button>
                                <button
                                    onClick={() => handleAction(pattern.id, 'not_now')}
                                    disabled={actionInProgress === pattern.id}
                                    className="flex items-center gap-1 px-3 py-1 bg-purple-100 text-purple-700 text-xs font-medium rounded-lg hover:bg-purple-200 disabled:opacity-50"
                                >
                                    <X className="w-3 h-3" />
                                    Not now
                                </button>
                                <button
                                    onClick={() => handleAction(pattern.id, 'reject')}
                                    disabled={actionInProgress === pattern.id}
                                    className="flex items-center gap-1 px-3 py-1 text-purple-500 text-xs font-medium hover:text-purple-700 disabled:opacity-50"
                                >
                                    <Ban className="w-3 h-3" />
                                    Never
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default PatternSuggestionBanner;
