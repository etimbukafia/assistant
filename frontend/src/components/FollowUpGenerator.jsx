import React, { useState } from 'react';
import { Sparkles, RefreshCw, CheckCircle2, Copy, Plus, X } from 'lucide-react';
import { api } from '../utils/api';

const FollowUpGenerator = ({ eventId, eventTitle, relatedMessageIds = [], onFollowUpsCreated }) => {
    const [loading, setLoading] = useState(false);
    const [followUps, setFollowUps] = useState([]);
    const [isComplete, setIsComplete] = useState(false);
    const [creating, setCreating] = useState(null); // Track which item is being created

    const copyToClipboard = async (text) => {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            return false;
        }
    };

    const generateFollowUps = async () => {
        setLoading(true);
        setFollowUps([]);
        try {
            const res = await api.post(`/calendar/events/${eventId}/generate-followups`);
            const data = await res.json();
            setFollowUps(data.follow_ups || []);
        } catch (err) {
            console.error("Failed to generate follow-ups", err);
            alert("Error generating follow-ups");
        } finally {
            setLoading(false);
        }
    };

    const approveItem = async (idx) => {
        const item = followUps[idx];
        setCreating(idx);

        try {
            if (item.type === 'email_draft') {
                // For email drafts, copy to clipboard and mark as approved
                const success = await copyToClipboard(item.draft_content || item.description || '');
                if (success) {
                    setFollowUps(prev => prev.map((f, i) => i === idx ? { ...f, approved: true, copiedToClipboard: true } : f));
                }
            } else {
                // For tasks and reminders, create via API
                const messageId = relatedMessageIds[0];
                if (!messageId) {
                    alert('Cannot create task: No related message found. Please create this task manually.');
                    return;
                }

                const res = await api.post('/tasks', {
                    message_id: messageId,
                    title: item.title,
                    description: item.description || `Follow-up from meeting: ${eventTitle}`,
                    task_type: item.type === 'reminder' ? 'implied_followup' : 'explicit',
                    priority: item.priority || 'normal',
                    status: 'approved'
                });

                if (res.ok) {
                    setFollowUps(prev => prev.map((f, i) => i === idx ? { ...f, approved: true } : f));
                    if (onFollowUpsCreated) onFollowUpsCreated();
                } else {
                    const error = await res.json();
                    alert(`Failed to create task: ${error.detail || 'Unknown error'}`);
                }
            }
        } catch (err) {
            console.error('Failed to approve item:', err);
            alert('Failed to create item. Please try again.');
        } finally {
            setCreating(null);
        }
    };

    const removeItem = (idx) => {
        setFollowUps(prev => prev.filter((_, i) => i !== idx));
    };

    if (isComplete) {
        return (
            <div className="bg-green-50 rounded-2xl p-6 border border-green-100 text-center">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <CheckCircle2 className="w-6 h-6 text-green-600" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Follow-ups Created</h3>
                <p className="text-gray-600 text-sm mb-4">All selected tasks and drafts have been added to your hub.</p>
                <button
                    onClick={() => setIsComplete(false)}
                    className="text-green-700 font-semibold text-sm hover:underline"
                >
                    Draft more?
                </button>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden mb-6">
            <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="font-bold text-gray-900">Post-Meeting Follow-ups</h3>
                        <p className="text-xs text-gray-500 mt-0.5">Generate tasks and drafts from this meeting</p>
                    </div>
                    <Sparkles className="w-5 h-5 text-purple-500" />
                </div>

                {followUps.length === 0 ? (
                    <button
                        onClick={generateFollowUps}
                        disabled={loading}
                        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold py-4 rounded-2xl hover:from-blue-700 hover:to-indigo-700 transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-100 disabled:opacity-50"
                    >
                        {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                        Generate Follow-up Ideas
                    </button>
                ) : (
                    <div className="space-y-3">
                        {followUps.map((item, idx) => (
                            <div key={idx} className={`p-4 rounded-xl border transition-all ${item.approved ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-100'}`}>
                                <div className="flex justify-between items-start gap-3">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${item.type === 'email_draft' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                                                }`}>
                                                {item.type === 'email_draft' ? 'Email Draft' : 'Task'}
                                            </span>
                                            {item.priority === 'high' && <span className="text-[10px] uppercase font-bold text-orange-600 bg-orange-100 px-1.5 py-0.5 rounded">High Priority</span>}
                                        </div>
                                        <p className="text-sm font-semibold text-gray-900 leading-tight">{item.title}</p>
                                        {item.description && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{item.description}</p>}
                                    </div>
                                    {!item.approved && (
                                        <button onClick={() => removeItem(idx)} className="text-gray-400 hover:text-red-500 transition-colors">
                                            <X className="w-4 h-4" />
                                        </button>
                                    )}
                                </div>

                                {!item.approved && (
                                    <div className="mt-3 flex gap-2">
                                        <button
                                            onClick={() => approveItem(idx)}
                                            disabled={creating === idx}
                                            className="flex-1 bg-white border border-gray-200 text-gray-700 font-semibold text-xs py-2 rounded-lg hover:bg-gray-100 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                                        >
                                            {creating === idx ? (
                                                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                            ) : (
                                                <Plus className="w-3.5 h-3.5 text-blue-600" />
                                            )}
                                            {item.type === 'email_draft' ? 'Copy & Approve' : 'Create Task'}
                                        </button>
                                        {item.type === 'email_draft' && item.draft_content && (
                                            <button
                                                onClick={async () => {
                                                    const success = await copyToClipboard(item.draft_content);
                                                    if (success) {
                                                        setFollowUps(prev => prev.map((f, i) => i === idx ? { ...f, copied: true } : f));
                                                        setTimeout(() => {
                                                            setFollowUps(prev => prev.map((f, i) => i === idx ? { ...f, copied: false } : f));
                                                        }, 2000);
                                                    }
                                                }}
                                                className={`flex items-center justify-center px-3 border rounded-lg transition-colors ${item.copied ? 'bg-green-50 border-green-200 text-green-600' : 'bg-white border-gray-200 hover:bg-gray-100 text-gray-500'}`}
                                                title="Copy to clipboard"
                                            >
                                                {item.copied ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                                            </button>
                                        )}
                                    </div>
                                )}

                                {item.approved && (
                                    <div className="mt-2 flex items-center gap-1.5 text-green-700">
                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-wider">
                                            {item.type === 'email_draft' ? 'Copied to Clipboard' : 'Task Created'}
                                        </span>
                                    </div>
                                )}
                            </div>
                        ))}

                        <div className="pt-2 flex gap-3">
                            <button
                                onClick={generateFollowUps}
                                className="flex-1 text-gray-500 font-semibold text-sm py-2 hover:text-gray-800 transition-colors flex items-center justify-center gap-2"
                            >
                                <RefreshCw className="w-4 h-4" />
                                Regenerate
                            </button>
                            <button
                                onClick={() => setIsComplete(true)}
                                className="flex-1 bg-blue-600 text-white font-semibold text-sm py-3 rounded-xl hover:bg-blue-700 transition-colors shadow-md shadow-blue-200"
                            >
                                Done
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FollowUpGenerator;
