import React, { useState, useEffect } from 'react';
import { RefreshCw, Copy } from 'lucide-react';
import { API_BASE_URL } from '../utils/constants';

const DraftReply = ({ message, onBack, demoMode }) => {
    const [draft, setDraft] = useState('');
    const [loading, setLoading] = useState(true);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        generateDraft();
    }, [message.id]);

    const generateDraft = async () => {
        setLoading(true);
        setDraft('');

        try {
            if (demoMode) {
                await new Promise(r => setTimeout(r, 1500));
                setDraft(`Hi ${message.sender.split('@')[0]},\n\nI'll send over the ${message.subject} details you requested shortly.\n\nBest,\n[Your Name]`);
            } else {
                const res = await fetch(`${API_BASE_URL}/messages/${message.id}/draft-reply`, {
                    method: 'POST'
                });
                const data = await res.json();
                setDraft(data.draft);
            }
        } catch (err) {
            console.error("Failed to generate draft", err);
            setDraft("Error generating draft. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(draft);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col pb-24">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shadow-sm">
                <button onClick={onBack} className="text-gray-600 font-medium text-sm hover:text-gray-900">
                    Cancel
                </button>
                <h2 className="font-semibold text-gray-900">Draft Reply</h2>
                <button
                    onClick={handleCopy}
                    disabled={loading || !draft}
                    className="text-blue-600 font-medium text-sm hover:text-blue-700 disabled:opacity-50"
                >
                    {copied ? 'Copied!' : 'Copy'}
                </button>
            </div>

            <div className="flex-1 p-4 max-w-md mx-auto w-full flex flex-col">
                <div className="text-sm text-gray-500 mb-2">
                    Replying to: <span className="font-medium text-gray-700">{message.subject}</span>
                </div>

                {/* Draft Area */}
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative">
                    {loading ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 rounded-xl z-10">
                            <div className="w-8 h-8 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin mb-4" />
                            <p className="text-gray-500 text-sm animate-pulse">Thinking...</p>
                        </div>
                    ) : (
                        <textarea
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            className="w-full h-full resize-none outline-none text-gray-800 leading-relaxed font-sans placeholder-gray-300"
                            placeholder="Draft will appear here..."
                        />
                    )}
                </div>

                {/* Bottom Actions */}
                <div className="mt-4 flex gap-3">
                    <button
                        onClick={generateDraft}
                        disabled={loading}
                        className="flex-1 bg-white border border-gray-300 text-gray-700 font-medium py-3 rounded-xl hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        Regenerate
                    </button>
                    <button
                        onClick={handleCopy}
                        disabled={loading}
                        className="flex-1 bg-blue-600 text-white font-medium py-3 rounded-xl hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                    >
                        <Copy className="w-4 h-4" />
                        Copy Text
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DraftReply;
