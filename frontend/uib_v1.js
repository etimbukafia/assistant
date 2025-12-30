import React, { useState, useEffect } from 'react';
import {
    Mail,
    RefreshCw,
    AlertCircle,
    CheckCircle2,
    Clock,
    ChevronLeft,
    Copy,
    Send,
    Filter,
    User,
    Calendar,
    List,
    Sparkles,
    MoreVertical,
    LogOut
} from 'lucide-react';

/**
 * CONFIGURATION & MOCK DATA
 */
const API_BASE_URL = 'http://localhost:8000';

const MOCK_MESSAGES = [
    {
        id: 1,
        subject: "Q4 Budget Review",
        sender: "john@company.com",
        recipient: "you@gmail.com",
        summary: "John needs Q4 budget breakdown by Wednesday. Wants to review marketing spend details.",
        body: "Hi,\n\nCould you please send over the Q4 budget breakdown by Wednesday? I specifically want to review the marketing spend details we discussed last week.\n\nThanks,\nJohn",
        needs_reply: true,
        extracted_tasks: ["Send budget breakdown", "Review marketing spend"],
        extracted_dates: ["Wednesday, Dec 22"],
        extracted_people: ["John Doe"],
        extracted_decisions: [],
        received_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
        processed: true
    },
    {
        id: 2,
        subject: "Weekly Newsletter",
        sender: "newsletter@tech-news.com",
        recipient: "you@gmail.com",
        summary: "Product updates and team announcements. New features launching next week.",
        body: "Here are the latest updates from the product team...",
        needs_reply: false,
        extracted_tasks: [],
        extracted_dates: [],
        extracted_people: [],
        extracted_decisions: [],
        received_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
        processed: true
    },
    {
        id: 3,
        subject: "Meeting Reschedule?",
        sender: "sarah@client.com",
        recipient: "you@gmail.com",
        summary: "Sarah asks if we can move the Tuesday call to Thursday at 2pm.",
        body: "Hey, something came up. Can we move our Tuesday call to Thursday at 2pm instead?",
        needs_reply: true,
        extracted_tasks: ["Reschedule meeting"],
        extracted_dates: ["Thursday 2pm"],
        extracted_people: ["Sarah Smith"],
        extracted_decisions: [],
        received_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 mins ago
        processed: true
    }
];

const MOCK_STATS = {
    total_messages: 45,
    needs_reply_count: 12,
    fyi_only: 33,
    unprocessed: 0,
    has_tasks_count: 8
};

/**
 * UTILITIES
 */
const timeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return 'Just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
};

/**
 * COMPONENTS
 */

// 1. Landing Page
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

// 2. Dashboard (Feed)
const Dashboard = ({
    messages,
    stats,
    onNavigate,
    onSync,
    isSyncing,
    filter,
    setFilter,
    demoMode
}) => {
    const [showDebug, setShowDebug] = useState(false);
    const [debugLog, setDebugLog] = useState('');

    const testAPI = async (endpoint, method = 'GET') => {
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`, { method });
            const data = await res.json();
            setDebugLog(`✅ ${method} ${endpoint}\n${JSON.stringify(data, null, 2)}`);
        } catch (err) {
            setDebugLog(`❌ ${method} ${endpoint}\n${err.message}`);
        }
    };

    // Filter logic
    const filteredMessages = messages.filter(m => {
        if (filter === 'urgent') return m.needs_reply;
        if (filter === 'today') {
            const received = new Date(m.received_at);
            const now = new Date();
            return (now.getTime() - received.getTime()) < 24 * 60 * 60 * 1000;
        }
        return true; // 'all'
    });

    // Sort: Urgent first, then new
    const sortedMessages = [...filteredMessages].sort((a, b) => {
        if (a.needs_reply && !b.needs_reply) return -1;
        if (!a.needs_reply && b.needs_reply) return 1;
        return new Date(b.received_at).getTime() - new Date(a.received_at).getTime();
    });

    return (
        <div className="min-h-screen bg-gray-50 pb-20">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 sticky top-0 z-10 px-4 py-3 flex justify-between items-center shadow-sm">
                <h1 className="text-lg font-bold text-gray-800">Inbox</h1>
                <div className="flex gap-2">
                    {!demoMode && (
                        <button
                            onClick={() => setShowDebug(!showDebug)}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-purple-50 text-purple-600 hover:bg-purple-100"
                        >
                            🧪 API Test
                        </button>
                    )}
                    <button
                        onClick={onSync}
                        disabled={isSyncing}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${isSyncing
                            ? 'bg-blue-50 text-blue-600'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                    >
                        <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
                        {isSyncing ? 'Syncing...' : 'Sync'}
                    </button>
                </div>
            </div>

            {/* Debug Panel */}
            {showDebug && (
                <div className="bg-gray-900 text-white p-4 border-b border-gray-700">
                    <div className="max-w-4xl mx-auto">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="font-bold text-sm">🧪 API Test Panel</h3>
                            <button
                                onClick={() => setShowDebug(false)}
                                className="text-gray-400 hover:text-white text-xs"
                            >
                                Close
                            </button>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
                            <button
                                onClick={() => testAPI('/auth/gmail/status')}
                                className="bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-xs font-medium"
                            >
                                Auth Status
                            </button>
                            <button
                                onClick={() => testAPI('/sync', 'POST')}
                                className="bg-green-600 hover:bg-green-700 px-3 py-2 rounded text-xs font-medium"
                            >
                                Sync Messages
                            </button>
                            <button
                                onClick={() => testAPI('/messages')}
                                className="bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded text-xs font-medium"
                            >
                                Get Messages
                            </button>
                            <button
                                onClick={() => testAPI('/stats')}
                                className="bg-orange-600 hover:bg-orange-700 px-3 py-2 rounded text-xs font-medium"
                            >
                                Get Stats
                            </button>
                            <button
                                onClick={() => testAPI('/queue/stats')}
                                className="bg-pink-600 hover:bg-pink-700 px-3 py-2 rounded text-xs font-medium"
                            >
                                Queue Status
                            </button>
                            <button
                                onClick={() => testAPI('/debug/handlers')}
                                className="bg-indigo-600 hover:bg-indigo-700 px-3 py-2 rounded text-xs font-medium"
                            >
                                Event Handlers
                            </button>
                            <button
                                onClick={() => messages[0] && testAPI(`/messages/${messages[0].id}`)}
                                className="bg-cyan-600 hover:bg-cyan-700 px-3 py-2 rounded text-xs font-medium"
                                disabled={!messages[0]}
                            >
                                Get Message #1
                            </button>
                            <button
                                onClick={() => messages[0] && testAPI(`/messages/${messages[0].id}/draft-reply`, 'POST')}
                                className="bg-teal-600 hover:bg-teal-700 px-3 py-2 rounded text-xs font-medium"
                                disabled={!messages[0]}
                            >
                                Draft Reply #1
                            </button>
                        </div>

                        {debugLog && (
                            <div className="bg-black rounded p-3 font-mono text-xs overflow-auto max-h-64">
                                <pre className="whitespace-pre-wrap">{debugLog}</pre>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="px-4 py-3 flex gap-2 overflow-x-auto no-scrollbar">
                <FilterButton
                    active={filter === 'all'}
                    onClick={() => setFilter('all')}
                    label="All"
                    count={stats?.total_messages}
                />
                <FilterButton
                    active={filter === 'urgent'}
                    onClick={() => setFilter('urgent')}
                    label="Urgent"
                    count={stats?.needs_reply_count}
                    urgent
                />
                <FilterButton
                    active={filter === 'today'}
                    onClick={() => setFilter('today')}
                    label="Today"
                />
            </div>

            {/* Feed */}
            <div className="px-4 space-y-3">
                {sortedMessages.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                        <p>No messages found.</p>
                    </div>
                ) : (
                    sortedMessages.map(msg => (
                        <MessageCard
                            key={msg.id}
                            message={msg}
                            onClick={() => onNavigate('detail', { id: msg.id })}
                        />
                    ))
                )}
            </div>
        </div>
    );
};

const FilterButton = ({ active, onClick, label, count, urgent }) => (
    <button
        onClick={onClick}
        className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors border ${active
            ? urgent
                ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-blue-50 border-blue-200 text-blue-700'
            : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
    >
        {label}
        {count !== undefined && <span className="ml-1.5 opacity-60">({count})</span>}
    </button>
);

const MessageCard = ({ message, onClick }) => {
    return (
        <div
            onClick={onClick}
            className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm active:scale-[0.99] transition-transform cursor-pointer"
        >
            {/* Card Header */}
            <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                    {message.needs_reply && (
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
                    )}
                    <span className={`font-semibold ${message.needs_reply ? 'text-gray-900' : 'text-gray-600'}`}>
                        {message.sender.split('@')[0]}
                    </span>
                    <span className="text-xs text-gray-400">• {timeAgo(message.received_at)}</span>
                </div>
                <Mail className="w-4 h-4 text-gray-400" />
            </div>

            {/* Summary */}
            <h3 className="font-medium text-gray-800 mb-1 line-clamp-1">{message.subject}</h3>
            <p className="text-sm text-gray-600 leading-relaxed line-clamp-3 mb-3">
                {message.summary}
            </p>

            {/* Actions / Tasks */}
            {message.extracted_tasks.length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3 mb-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        ACTIONS
                    </div>
                    <ul className="space-y-1.5">
                        {message.extracted_tasks.slice(0, 2).map((task, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                                <span className="mt-1.5 w-1 h-1 bg-gray-400 rounded-full flex-shrink-0" />
                                {task}
                            </li>
                        ))}
                        {message.extracted_tasks.length > 2 && (
                            <li className="text-xs text-gray-400 pl-3">
                                +{message.extracted_tasks.length - 2} more...
                            </li>
                        )}
                    </ul>
                </div>
            )}

            {/* Footer Buttons */}
            <div className="flex gap-2 mt-2">
                {message.needs_reply ? (
                    <button
                        onClick={(e) => { e.stopPropagation(); onClick(); }} // In real app, might go straight to reply
                        className="flex-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-sm font-medium py-2 rounded-lg transition-colors"
                    >
                        Reply
                    </button>
                ) : (
                    <button className="flex-1 bg-gray-50 hover:bg-gray-100 text-gray-600 text-sm font-medium py-2 rounded-lg transition-colors">
                        Mark Done
                    </button>
                )}
            </div>
        </div>
    );
};

// 3. Message Detail View
const MessageDetail = ({ message, onBack, onDraftReply }) => {
    if (!message) return null;

    return (
        <div className="min-h-screen bg-white">
            {/* Header */}
            <div className="sticky top-0 bg-white/90 backdrop-blur-md border-b border-gray-100 px-4 py-3 flex items-center gap-3 z-10">
                <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full">
                    <ChevronLeft className="w-6 h-6 text-gray-600" />
                </button>
                <div className="flex-1 min-w-0">
                    <h2 className="font-semibold text-gray-900 truncate">{message.subject}</h2>
                </div>
            </div>

            <div className="p-4 space-y-6 pb-24">
                {/* Meta */}
                <div className="flex justify-between items-start">
                    <div>
                        <div className="font-bold text-lg text-gray-900">{message.sender}</div>
                        <div className="text-sm text-gray-500">To: You</div>
                    </div>
                    <div className="text-sm text-gray-400">{timeAgo(message.received_at)}</div>
                </div>

                {/* AI Summary Section */}
                <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                    <div className="flex items-center gap-2 mb-2 text-blue-800 font-semibold text-sm">
                        <Sparkles className="w-4 h-4" />
                        ASSISTANT SUMMARY
                    </div>
                    <p className="text-blue-900 leading-relaxed text-sm md:text-base">
                        {message.summary}
                    </p>
                </div>

                {/* Extracted Data Grid */}
                <div className="grid gap-4">
                    {message.extracted_tasks.length > 0 && (
                        <div className="border border-gray-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3 text-gray-700 font-semibold text-sm">
                                <CheckCircle2 className="w-4 h-4 text-green-600" />
                                TASKS
                            </div>
                            <ul className="space-y-2">
                                {message.extracted_tasks.map((task, i) => (
                                    <li key={i} className="flex gap-3 text-gray-800 text-sm">
                                        <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-gray-300 flex-shrink-0" />
                                        {task}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {message.extracted_dates.length > 0 && (
                        <div className="border border-gray-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3 text-gray-700 font-semibold text-sm">
                                <Calendar className="w-4 h-4 text-orange-500" />
                                DATES
                            </div>
                            <ul className="space-y-2">
                                {message.extracted_dates.map((date, i) => (
                                    <li key={i} className="text-gray-800 text-sm bg-orange-50 inline-block px-2 py-1 rounded-md">
                                        {date}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {message.extracted_people.length > 0 && (
                        <div className="border border-gray-200 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-3 text-gray-700 font-semibold text-sm">
                                <User className="w-4 h-4 text-purple-500" />
                                PEOPLE
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {message.extracted_people.map((person, i) => (
                                    <span key={i} className="text-gray-800 text-sm bg-purple-50 px-2 py-1 rounded-md">
                                        {person}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Full Email Collapsible */}
                <details className="group border border-gray-200 rounded-xl overflow-hidden">
                    <summary className="flex items-center justify-between p-4 bg-gray-50 cursor-pointer list-none font-medium text-gray-700 group-open:border-b border-gray-200">
                        <span>Show Full Email</span>
                        <MoreVertical className="w-4 h-4 text-gray-400 group-open:rotate-90 transition-transform" />
                    </summary>
                    <div className="p-4 bg-white text-sm text-gray-600 whitespace-pre-wrap leading-relaxed">
                        {message.body || "No body content available."}
                    </div>
                </details>
            </div>

            {/* Floating Action Button */}
            {message.needs_reply && (
                <div className="fixed bottom-6 left-4 right-4 max-w-md mx-auto">
                    <button
                        onClick={() => onDraftReply(message.id)}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-xl shadow-lg flex items-center justify-center gap-2 transition-transform active:scale-95"
                    >
                        <Sparkles className="w-5 h-5" />
                        Generate AI Reply
                    </button>
                </div>
            )}
        </div>
    );
};

// 4. Draft Reply View
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
                // Mock delay
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
        <div className="min-h-screen bg-gray-50 flex flex-col">
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

/**
 * MAIN APP CONTAINER
 */
const App = () => {
    // Navigation State
    const [currentView, setCurrentView] = useState('landing'); // landing, dashboard, detail, draft
    const [viewParams, setViewParams] = useState({});

    // Data State
    const [demoMode, setDemoMode] = useState(true);
    const [messages, setMessages] = useState([]);
    const [stats, setStats] = useState(null);
    const [isSyncing, setIsSyncing] = useState(false);
    const [filter, setFilter] = useState('all');
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    // Check authentication on mount (handle OAuth redirect)
    useEffect(() => {
        const checkAuth = async () => {
            // Check URL path to handle OAuth redirect
            const path = window.location.pathname;

            if (path === '/dashboard') {
                // Backend redirected us here after OAuth
                // Check if authenticated
                try {
                    const res = await fetch(`${API_BASE_URL}/auth/gmail/status`);
                    const data = await res.json();

                    if (data.authenticated) {
                        setIsAuthenticated(true);
                        setDemoMode(false); // Switch to real mode
                        setCurrentView('dashboard');
                        // Clean URL
                        window.history.replaceState({}, '', '/dashboard');
                    } else {
                        // Not authenticated, go to landing
                        setCurrentView('landing');
                        window.history.replaceState({}, '', '/');
                    }
                } catch (err) {
                    console.error("Auth check failed", err);
                    setCurrentView('landing');
                    window.history.replaceState({}, '', '/');
                }
            }
        };

        checkAuth();
    }, []);

    // Load initial data if authenticated (mocked here by checking if not on landing)
    useEffect(() => {
        if (currentView === 'dashboard') {
            fetchData();
        }
    }, [currentView, demoMode]);

    const fetchData = async () => {
        if (demoMode) {
            setMessages(MOCK_MESSAGES);
            setStats(MOCK_STATS);
            return;
        }

        try {
            const msgRes = await fetch(`${API_BASE_URL}/messages`);
            const msgData = await msgRes.json();
            setMessages(msgData.messages);

            const statsRes = await fetch(`${API_BASE_URL}/stats`);
            const statsData = await statsRes.json();
            setStats(statsData);
        } catch (err) {
            console.error("Failed to fetch data, falling back to empty state", err);
            // Optional: Show toast error
        }
    };

    const handleSync = async () => {
        setIsSyncing(true);
        if (demoMode) {
            await new Promise(r => setTimeout(r, 2000)); // Mock delay
            setMessages(prev => [
                {
                    id: Date.now(),
                    subject: "New Urgent Request",
                    sender: "boss@company.com",
                    recipient: "you@gmail.com",
                    summary: "Need the slide deck ASAP.",
                    body: "Please send the deck.",
                    needs_reply: true,
                    extracted_tasks: ["Send deck"],
                    extracted_dates: [],
                    extracted_people: [],
                    extracted_decisions: [],
                    received_at: new Date().toISOString(),
                    processed: true
                },
                ...prev
            ]);
            setStats(prev => ({ ...prev, total_messages: prev.total_messages + 1, needs_reply_count: prev.needs_reply_count + 1 }));
        } else {
            try {
                await fetch(`${API_BASE_URL}/sync`, { method: 'POST' });
                // Poll for completion or just wait a bit
                await new Promise(r => setTimeout(r, 3000));
                await fetchData();
            } catch (err) {
                console.error("Sync failed", err);
            }
        }
        setIsSyncing(false);
    };

    const handleConnectGmail = async () => {
        if (demoMode) {
            setCurrentView('dashboard');
        } else {
            try {
                const res = await fetch(`${API_BASE_URL}/auth/gmail`);
                const { auth_url } = await res.json();
                window.location.href = auth_url;
            } catch (err) {
                console.error("Auth failed", err);
                alert("Failed to connect to backend. Try checking 'Demo Mode' to preview the UI.");
            }
        }
    };

    const navigate = (view, params = {}) => {
        setCurrentView(view);
        setViewParams(params);
        window.scrollTo(0, 0);
    };

    // Router Switch
    switch (currentView) {
        case 'landing':
            return (
                <LandingPage
                    onConnect={handleConnectGmail}
                    demoMode={demoMode}
                    setDemoMode={setDemoMode}
                />
            );

        case 'dashboard':
            return (
                <Dashboard
                    messages={messages}
                    stats={stats}
                    onSync={handleSync}
                    isSyncing={isSyncing}
                    onNavigate={navigate}
                    filter={filter}
                    setFilter={setFilter}
                    demoMode={demoMode}
                />
            );

        case 'detail':
            const msg = messages.find(m => m.id === viewParams.id);
            return (
                <MessageDetail
                    message={msg}
                    onBack={() => navigate('dashboard')}
                    onDraftReply={(id) => navigate('draft', { id })}
                />
            );

        case 'draft':
            const draftMsg = messages.find(m => m.id === viewParams.id);
            return (
                <DraftReply
                    message={draftMsg}
                    onBack={() => navigate('detail', { id: viewParams.id })}
                    demoMode={demoMode}
                />
            );

        default:
            return <div>Page not found</div>;
    }
};

export default App;