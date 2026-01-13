import React, { useState, useEffect } from 'react';
import { API_BASE_URL, MOCK_MESSAGES, MOCK_STATS } from './utils/constants';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { SubscriptionProvider, useSubscription } from './contexts/SubscriptionContext';
import { api } from './utils/api';
import BottomNav from './components/BottomNav';
import TrialBanner from './components/TrialBanner';
import TrialExpiredPrompt from './components/TrialExpiredPrompt';
import LandingPage from './views/LandingPage';
import AuthPage from './views/AuthPage';
import Dashboard from './views/Dashboard';
import TaskHub from './views/TaskHub';
import SettingsView from './views/SettingsView';
import MessageDetail from './views/MessageDetail';
import DraftReply from './views/DraftReply';
import CalendarEventsView from './views/CalendarEventsView';
import BillingView from './views/BillingView';
import CheckoutSuccess from './views/CheckoutSuccess';
import CheckoutCancel from './views/CheckoutCancel';
import ChatView from './views/ChatView';
import DeleteConfirmDialog from './components/DeleteConfirmDialog';

const AppContent = () => {
    const { isAuthenticated, loading: authLoading, user } = useAuth();
    const { isTrialUser, isTrialExpired, isActive, loading: subscriptionLoading } = useSubscription();

    // Navigation State
    const [currentView, setCurrentView] = useState('landing');
    const [viewParams, setViewParams] = useState({});

    // Data State
    const [demoMode, setDemoMode] = useState(false);
    const [messages, setMessages] = useState([]);
    const [stats, setStats] = useState(null);
    const [isSyncing, setIsSyncing] = useState(false);
    const [filter, setFilter] = useState('all');

    // Scheduling State
    const [schedulingSuggestions, setSchedulingSuggestions] = useState({});

    // Delete Confirmation Dialog State
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [messageToDelete, setMessageToDelete] = useState(null);

    // Polling State (Phase 1 Notification Strategy)
    const [lastFetchTime, setLastFetchTime] = useState(null);
    const [newItemsCount, setNewItemsCount] = useState(0);
    const [pendingMessages, setPendingMessages] = useState([]);
    const [focusMode, setFocusMode] = useState(false);

    // Handle auth state changes and URL-based routing
    useEffect(() => {
        if (authLoading) return;

        const path = window.location.pathname;

        if (isAuthenticated) {
            // Handle URL-based routing for authenticated users
            if (path === '/checkout-success') {
                setCurrentView('checkout-success');
            } else if (path === '/checkout-cancel') {
                setCurrentView('checkout-cancel');
            } else if (path === '/billing') {
                setCurrentView('billing');
            } else if (currentView === 'landing' || currentView === 'auth' || path === '/dashboard') {
                setCurrentView('dashboard');
                window.history.replaceState({}, '', '/dashboard');
            }
        } else if (!demoMode) {
            // Not authenticated and not in demo mode - go to landing
            if (currentView !== 'landing' && currentView !== 'auth') {
                setCurrentView('landing');
                window.history.replaceState({}, '', '/');
            }
        }
    }, [isAuthenticated, authLoading, demoMode]);

    // Load initial data - only on first load or when demoMode changes, NOT on view change
    useEffect(() => {
        if (currentView !== 'landing' && messages.length === 0) {
            fetchData();
        }
    }, [demoMode]);

    // Initial load when navigating away from landing
    useEffect(() => {
        if (currentView !== 'landing' && messages.length === 0) {
            fetchData();
        }
    }, [currentView]);

    const fetchData = async () => {
        if (demoMode) {
            setMessages(MOCK_MESSAGES);
            setStats(MOCK_STATS);
            setLastFetchTime(new Date().toISOString());
            return;
        }

        try {
            const msgRes = await fetch(`${API_BASE_URL}/messages`);
            const msgData = await msgRes.json();
            setMessages(msgData.messages);
            setLastFetchTime(new Date().toISOString());

            const statsRes = await fetch(`${API_BASE_URL}/stats`);
            const statsData = await statsRes.json();
            setStats(statsData);
        } catch (err) {
            console.error("Failed to fetch data", err);
        }
    };

    // Polling for new items (Phase 1 Notification Strategy)
    // Only polls when not in focus mode and on dashboard
    useEffect(() => {
        if (demoMode || focusMode || currentView !== 'dashboard' || !lastFetchTime) return;

        const fetchNewItems = async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/messages/new?since=${encodeURIComponent(lastFetchTime)}`);
                const data = await res.json();

                if (data.messages && data.messages.length > 0) {
                    setPendingMessages(prev => [...data.messages, ...prev]);
                    setNewItemsCount(prev => prev + data.messages.length);
                    // Update lastFetchTime to avoid fetching same messages
                    setLastFetchTime(new Date().toISOString());
                }
            } catch (err) {
                console.error("Polling failed", err);
            }
        };

        const interval = setInterval(fetchNewItems, 30000); // 30 second poll
        return () => clearInterval(interval);
    }, [demoMode, focusMode, currentView, lastFetchTime]);

    // Helper: Load pending messages into main feed
    const loadPendingMessages = () => {
        setMessages(prev => [...pendingMessages, ...prev]);
        setPendingMessages([]);
        setNewItemsCount(0);
    };

    const handleSync = async () => {
        setIsSyncing(true);
        if (demoMode) {
            await new Promise(r => setTimeout(r, 2000));
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
                    processed: true,
                    tasks: [{
                        id: Date.now(),
                        title: "Send deck ASAP",
                        type: "explicit",
                        priority: "urgent",
                        status: "pending_approval",
                        confidence: 0.98,
                        source_snippet: "Need the slide deck ASAP"
                    }]
                },
                ...prev
            ]);
            setStats(prev => ({ ...prev, total_messages: prev.total_messages + 1, needs_reply_count: prev.needs_reply_count + 1 }));
        } else {
            try {
                await fetch(`${API_BASE_URL}/sync`, { method: 'POST' });
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

    /**
     * Toggle task completion status
     * Calls POST /tasks/{task_id}/complete in live mode
     */
    const handleToggleTask = async (taskId) => {
        // Find current task status
        let currentStatus = null;
        for (const msg of messages) {
            const task = (msg.tasks || []).find(t => t.id === taskId);
            if (task) {
                currentStatus = task.status;
                break;
            }
        }

        const newStatus = currentStatus === 'completed' ? 'approved' : 'completed';

        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (!msg.tasks) return msg;
            return {
                ...msg,
                tasks: msg.tasks.map(t =>
                    t.id === taskId ? { ...t, status: newStatus } : t
                )
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const endpoint = newStatus === 'completed'
                    ? `${API_BASE_URL}/tasks/${taskId}/complete`
                    : `${API_BASE_URL}/tasks/${taskId}/approve`;

                const res = await fetch(endpoint, { method: 'POST' });

                if (!res.ok) {
                    throw new Error('Failed to update task');
                }
            } catch (err) {
                console.error("Toggle task failed", err);
                // Rollback on error
                setMessages(prev => prev.map(msg => {
                    if (!msg.tasks) return msg;
                    return {
                        ...msg,
                        tasks: msg.tasks.map(t =>
                            t.id === taskId ? { ...t, status: currentStatus } : t
                        )
                    };
                }));
            }
        }
    };

    /**
     * Approve a pending_approval task
     * Calls POST /tasks/{task_id}/approve in live mode
     */
    const handleApproveTask = async (taskId) => {
        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (!msg.tasks) return msg;
            return {
                ...msg,
                tasks: msg.tasks.map(t =>
                    t.id === taskId && t.status === 'pending_approval'
                        ? { ...t, status: 'approved' }
                        : t
                )
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks/${taskId}/approve`, {
                    method: 'POST'
                });

                if (!res.ok) {
                    throw new Error('Failed to approve task');
                }
            } catch (err) {
                console.error("Approve task failed", err);
                // Rollback on error
                setMessages(prev => prev.map(msg => {
                    if (!msg.tasks) return msg;
                    return {
                        ...msg,
                        tasks: msg.tasks.map(t =>
                            t.id === taskId ? { ...t, status: 'pending_approval' } : t
                        )
                    };
                }));
            }
        }
    };

    /**
     * Dismiss a task (hide everywhere)
     * Calls POST /tasks/{task_id}/dismiss in live mode
     */
    const handleDismissTask = async (taskId) => {
        // Store original status for rollback
        let originalStatus = null;
        for (const msg of messages) {
            const task = (msg.tasks || []).find(t => t.id === taskId);
            if (task) {
                originalStatus = task.status;
                break;
            }
        }

        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (!msg.tasks) return msg;
            return {
                ...msg,
                tasks: msg.tasks.map(t =>
                    t.id === taskId ? { ...t, status: 'dismissed' } : t
                )
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks/${taskId}/dismiss`, {
                    method: 'POST'
                });

                if (!res.ok) {
                    throw new Error('Failed to dismiss task');
                }
            } catch (err) {
                console.error("Dismiss task failed", err);
                // Rollback on error
                setMessages(prev => prev.map(msg => {
                    if (!msg.tasks) return msg;
                    return {
                        ...msg,
                        tasks: msg.tasks.map(t =>
                            t.id === taskId ? { ...t, status: originalStatus } : t
                        )
                    };
                }));
            }
        }
    };

    /**
     * Update a task (Smart Todo List - inline edit)
     * Calls PUT /tasks/{task_id} in live mode
     */
    const handleUpdateTask = async (taskId, updates) => {
        // Store original task for rollback
        let originalTask = null;
        for (const msg of messages) {
            const task = (msg.tasks || []).find(t => t.id === taskId);
            if (task) {
                originalTask = { ...task };
                break;
            }
        }

        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (!msg.tasks) return msg;
            return {
                ...msg,
                tasks: msg.tasks.map(t =>
                    t.id === taskId ? { ...t, ...updates } : t
                )
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates)
                });

                if (!res.ok) {
                    throw new Error('Failed to update task');
                }
            } catch (err) {
                console.error("Update task failed", err);
                // Rollback on error
                if (originalTask) {
                    setMessages(prev => prev.map(msg => {
                        if (!msg.tasks) return msg;
                        return {
                            ...msg,
                            tasks: msg.tasks.map(t =>
                                t.id === taskId ? originalTask : t
                            )
                        };
                    }));
                }
            }
        }
    };

    /**
     * Confirm AI-suggested deadline
     * Calls PUT /tasks/{task_id} with deadline_confirmed: true
     */
    const handleConfirmDeadline = async (taskId) => {
        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (!msg.tasks) return msg;
            return {
                ...msg,
                tasks: msg.tasks.map(t =>
                    t.id === taskId ? { ...t, deadline_user_confirmed: true } : t
                )
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ deadline_confirmed: true })
                });

                if (!res.ok) {
                    throw new Error('Failed to confirm deadline');
                }
            } catch (err) {
                console.error("Confirm deadline failed", err);
                // Rollback
                setMessages(prev => prev.map(msg => {
                    if (!msg.tasks) return msg;
                    return {
                        ...msg,
                        tasks: msg.tasks.map(t =>
                            t.id === taskId ? { ...t, deadline_user_confirmed: false } : t
                        )
                    };
                }));
            }
        }
    };

    /**
     * Confirm AI-suggested urgency
     * Calls PUT /tasks/{task_id} with mark_urgent: true
     */
    const handleConfirmUrgency = async (taskId) => {
        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (!msg.tasks) return msg;
            return {
                ...msg,
                tasks: msg.tasks.map(t =>
                    t.id === taskId ? { ...t, urgency_suggested_by_ai: false } : t
                )
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mark_urgent: true })
                });

                if (!res.ok) {
                    throw new Error('Failed to confirm urgency');
                }
            } catch (err) {
                console.error("Confirm urgency failed", err);
                // Rollback
                setMessages(prev => prev.map(msg => {
                    if (!msg.tasks) return msg;
                    return {
                        ...msg,
                        tasks: msg.tasks.map(t =>
                            t.id === taskId ? { ...t, urgency_suggested_by_ai: true } : t
                        )
                    };
                }));
            }
        }
    };

    /**
     * Create a manual task (not from email)
     * Calls POST /tasks/manual
     */
    const handleCreateTask = async (taskData) => {
        const tempTask = {
            id: Date.now(),
            ...taskData,
            status: 'approved',
            type: 'explicit',
            created_at: new Date().toISOString()
        };

        // For manual tasks, we need to add them to a special "manual" message or create standalone
        // For now, add to first message for display purposes
        setMessages(prev => {
            if (prev.length === 0) return prev;
            const [first, ...rest] = prev;
            return [{ ...first, tasks: [...(first.tasks || []), tempTask] }, ...rest];
        });

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks/manual`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskData)
                });

                if (!res.ok) {
                    throw new Error('Failed to create task');
                }

                const createdTask = await res.json();

                // Update with real task from backend
                setMessages(prev => {
                    if (prev.length === 0) return prev;
                    const [first, ...rest] = prev;
                    return [{
                        ...first,
                        tasks: first.tasks.map(t =>
                            t.id === tempTask.id ? { ...createdTask, type: createdTask.type || createdTask.task_type } : t
                        )
                    }, ...rest];
                });
            } catch (err) {
                console.error("Create task failed", err);
                // Rollback
                setMessages(prev => {
                    if (prev.length === 0) return prev;
                    const [first, ...rest] = prev;
                    return [{
                        ...first,
                        tasks: (first.tasks || []).filter(t => t.id !== tempTask.id)
                    }, ...rest];
                });
            }
        }
    };

    /**
     * Approve an extracted task (raw AI text) as a real task
     * Calls POST /tasks in live mode to create task in database
     */
    const handleApproveExtractedTask = async (messageId, taskText) => {
        // Create temporary task for optimistic update
        const tempTask = {
            id: Date.now(),
            title: taskText,
            type: 'explicit',
            priority: 'normal',
            status: 'approved',
            source_snippet: taskText,
            confidence: 1.0
        };

        // Optimistic update
        setMessages(prev => prev.map(msg => {
            if (msg.id !== messageId) return msg;
            return {
                ...msg,
                tasks: [...(msg.tasks || []), tempTask],
                extracted_tasks: (msg.extracted_tasks || []).filter(t => t !== taskText)
            };
        }));

        // Call backend in live mode
        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/tasks`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message_id: messageId,
                        title: taskText,
                        source_snippet: taskText,
                        task_type: 'explicit',
                        priority: 'normal',
                        status: 'approved'
                    })
                });

                if (!res.ok) {
                    throw new Error('Failed to create task');
                }

                const createdTask = await res.json();

                // Update with real task ID from backend
                setMessages(prev => prev.map(msg => {
                    if (msg.id !== messageId) return msg;
                    return {
                        ...msg,
                        tasks: msg.tasks.map(t =>
                            t.id === tempTask.id ? { ...createdTask, type: createdTask.type || createdTask.task_type } : t
                        )
                    };
                }));
            } catch (err) {
                console.error("Create task failed", err);
                // Rollback on error
                setMessages(prev => prev.map(msg => {
                    if (msg.id !== messageId) return msg;
                    return {
                        ...msg,
                        tasks: (msg.tasks || []).filter(t => t.id !== tempTask.id),
                        extracted_tasks: [...(msg.extracted_tasks || []), taskText]
                    };
                }));
            }
        }
    };

    /**
     * Mark a message as done, or restore to inbox if restore=true
     */
    const handleMarkDone = async (messageId, restore = false) => {
        const newStatus = restore ? 'inbox' : 'done';
        const originalStatus = messages.find(m => m.id === messageId)?.status || 'inbox';

        // Optimistic update
        setMessages(prev => prev.map(msg =>
            msg.id === messageId ? { ...msg, status: newStatus } : msg
        ));

        if (!demoMode) {
            try {
                const endpoint = restore
                    ? `${API_BASE_URL}/messages/${messageId}/restore`
                    : `${API_BASE_URL}/messages/${messageId}/done`;
                const res = await fetch(endpoint, {
                    method: 'POST'
                });
                if (!res.ok) throw new Error(restore ? 'Failed to restore' : 'Failed to mark as done');
            } catch (err) {
                console.error(restore ? "Restore failed" : "Mark done failed", err);
                // Rollback
                setMessages(prev => prev.map(msg =>
                    msg.id === messageId ? { ...msg, status: originalStatus } : msg
                ));
            }
        }
    };

    /**
     * Archive a message
     */
    const handleArchive = async (messageId) => {
        // Optimistic update
        setMessages(prev => prev.map(msg =>
            msg.id === messageId ? { ...msg, status: 'archived' } : msg
        ));

        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/messages/${messageId}/archive`, {
                    method: 'POST'
                });
                if (!res.ok) throw new Error('Failed to archive');
            } catch (err) {
                console.error("Archive failed", err);
                // Rollback
                setMessages(prev => prev.map(msg =>
                    msg.id === messageId ? { ...msg, status: 'inbox' } : msg
                ));
            }
        }
    };

    /**
     * Initiate delete - shows confirmation dialog
     */
    const handleDelete = (messageId) => {
        const message = messages.find(m => m.id === messageId);
        if (message) {
            setMessageToDelete(message);
            setDeleteDialogOpen(true);
        }
    };

    /**
     * Actually delete the message after confirmation
     */
    const confirmDelete = async () => {
        if (!messageToDelete) return;

        const messageId = messageToDelete.id;
        setDeleteDialogOpen(false);

        // Optimistic update - remove from list
        setMessages(prev => prev.filter(msg => msg.id !== messageId));

        if (!demoMode) {
            try {
                const res = await fetch(`${API_BASE_URL}/messages/${messageId}`, {
                    method: 'DELETE'
                });
                if (!res.ok) throw new Error('Failed to delete');
            } catch (err) {
                console.error("Delete failed", err);
                // Rollback - add message back
                setMessages(prev => [...prev, messageToDelete]);
            }
        }

        setMessageToDelete(null);
    };

    /**
     * Archive instead of delete (from dialog)
     */
    const archiveInsteadOfDelete = () => {
        if (messageToDelete) {
            handleArchive(messageToDelete.id);
            setDeleteDialogOpen(false);
            setMessageToDelete(null);
        }
    };

    /**
     * Fetch scheduling suggestion for a message
     */
    const fetchSchedulingSuggestion = async (messageId) => {
        if (demoMode) return null;

        try {
            const res = await fetch(`${API_BASE_URL}/scheduling/suggestions?message_id=${messageId}`);
            const data = await res.json();
            if (data.suggestions && data.suggestions.length > 0) {
                // Get the latest pending suggestion
                const pending = data.suggestions.find(s => s.status === 'pending');
                if (pending) {
                    setSchedulingSuggestions(prev => ({
                        ...prev,
                        [messageId]: pending
                    }));
                    return pending;
                }
            }
        } catch (err) {
            console.error("Failed to fetch scheduling suggestion", err);
        }
        return null;
    };

    /**
     * Send scheduling availability reply
     */
    const handleSendScheduling = async (suggestionId, editedReply = null) => {
        if (demoMode) {
            // Demo mode: just clear the suggestion
            setSchedulingSuggestions(prev => {
                const updated = { ...prev };
                for (const key in updated) {
                    if (updated[key]?.id === suggestionId) {
                        delete updated[key];
                    }
                }
                return updated;
            });
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/scheduling/suggestions/${suggestionId}/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ edited_reply: editedReply })
            });

            if (!res.ok) throw new Error('Failed to send');

            // Clear from local state
            setSchedulingSuggestions(prev => {
                const updated = { ...prev };
                for (const key in updated) {
                    if (updated[key]?.id === suggestionId) {
                        delete updated[key];
                    }
                }
                return updated;
            });
        } catch (err) {
            console.error("Send scheduling failed", err);
        }
    };

    /**
     * Dismiss scheduling suggestion
     */
    const handleDismissScheduling = async (suggestionId) => {
        if (demoMode) {
            setSchedulingSuggestions(prev => {
                const updated = { ...prev };
                for (const key in updated) {
                    if (updated[key]?.id === suggestionId) {
                        delete updated[key];
                    }
                }
                return updated;
            });
            return;
        }

        try {
            await fetch(`${API_BASE_URL}/scheduling/suggestions/${suggestionId}/dismiss`, {
                method: 'POST'
            });

            setSchedulingSuggestions(prev => {
                const updated = { ...prev };
                for (const key in updated) {
                    if (updated[key]?.id === suggestionId) {
                        delete updated[key];
                    }
                }
                return updated;
            });
        } catch (err) {
            console.error("Dismiss scheduling failed", err);
        }
    };

    /**
     * Refresh scheduling suggestion with fresh availability
     */
    const [isRefreshingScheduling, setIsRefreshingScheduling] = useState(false);

    const handleRefreshScheduling = async (messageId) => {
        if (demoMode) {
            alert("Cannot refresh in demo mode");
            return;
        }

        setIsRefreshingScheduling(true);
        try {
            const res = await fetch(`${API_BASE_URL}/scheduling/detect?message_id=${messageId}`, {
                method: 'POST'
            });

            if (res.ok) {
                const result = await res.json();
                if (result.success && result.suggestion_id) {
                    // Fetch the updated suggestion
                    const suggestionRes = await fetch(`${API_BASE_URL}/scheduling/suggestions/${result.suggestion_id}`);
                    if (suggestionRes.ok) {
                        const suggestion = await suggestionRes.json();
                        setSchedulingSuggestions(prev => ({
                            ...prev,
                            [messageId]: suggestion
                        }));
                    }
                }
            }
        } catch (err) {
            console.error("Refresh scheduling failed", err);
        } finally {
            setIsRefreshingScheduling(false);
        }
    };

    /**
     * Create calendar event from suggestion
     */
    const handleCreateCalendarEvent = async (suggestionId, slotIndex) => {
        if (demoMode) {
            alert("Calendar events can't be created in demo mode");
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/calendar/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    suggestion_id: suggestionId,
                    selected_slot_index: slotIndex
                })
            });

            if (!res.ok) throw new Error('Failed to create event');

            // Clear suggestion from state
            setSchedulingSuggestions(prev => {
                const updated = { ...prev };
                for (const key in updated) {
                    if (updated[key]?.id === suggestionId) {
                        delete updated[key];
                    }
                }
                return updated;
            });

            alert("Calendar event created!");
        } catch (err) {
            console.error("Create event failed", err);
            alert("Failed to create calendar event");
        }
    };

    const navigate = (view, params = {}) => {
        setCurrentView(view);
        setViewParams(params);
        window.scrollTo(0, 0);

        // Fetch scheduling suggestion when navigating to message detail
        if (view === 'detail' && params.id && !demoMode) {
            fetchSchedulingSuggestion(params.id);
        }
    };

    // Show loading state while checking auth
    if (authLoading) {
        return (
            <div className="min-h-screen bg-slate-900 flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
            </div>
        );
    }

    // Router Switch
    let content;
    switch (currentView) {
        case 'landing':
            return (
                <LandingPage
                    onConnect={() => navigate('auth')}
                    demoMode={demoMode}
                    setDemoMode={setDemoMode}
                />
            );

        case 'auth':
            return <AuthPage onNavigate={navigate} />;

        case 'dashboard':
            // Filter to only show inbox messages (not done or archived)
            const inboxMessages = messages.filter(m => !m.status || m.status === 'inbox');
            content = (
                <Dashboard
                    messages={inboxMessages}
                    stats={stats}
                    onSync={handleSync}
                    isSyncing={isSyncing}
                    onNavigate={navigate}
                    filter={filter}
                    setFilter={setFilter}
                    demoMode={demoMode}
                    onToggleTask={handleToggleTask}
                    onApproveTask={handleApproveTask}
                    onDismissTask={handleDismissTask}
                    onApproveExtractedTask={handleApproveExtractedTask}
                    onMarkDone={handleMarkDone}
                    onArchive={handleArchive}
                    onDelete={handleDelete}
                    onConfirmDeadline={handleConfirmDeadline}
                    onConfirmUrgency={handleConfirmUrgency}
                    // Polling props (Phase 1 Notification Strategy)
                    newItemsCount={newItemsCount}
                    onLoadNewItems={loadPendingMessages}
                    focusMode={focusMode}
                    setFocusMode={setFocusMode}
                />
            );
            break;

        case 'archive':
            const archivedMessages = messages.filter(m => m.status === 'archived' || m.status === 'done');
            content = (
                <Dashboard
                    messages={archivedMessages}
                    stats={stats}
                    onSync={handleSync}
                    isSyncing={isSyncing}
                    onNavigate={navigate}
                    filter={filter}
                    setFilter={setFilter}
                    demoMode={demoMode}
                    onToggleTask={handleToggleTask}
                    onApproveTask={handleApproveTask}
                    onDismissTask={handleDismissTask}
                    onApproveExtractedTask={handleApproveExtractedTask}
                    onMarkDone={handleMarkDone}
                    onArchive={handleArchive}
                    onDelete={handleDelete}
                    onConfirmDeadline={handleConfirmDeadline}
                    onConfirmUrgency={handleConfirmUrgency}
                    isArchiveView={true}
                />
            );
            break;

        case 'tasks':
            content = (
                <TaskHub
                    messages={messages}
                    onNavigate={navigate}
                    onToggleTask={handleToggleTask}
                    onApproveTask={handleApproveTask}
                    onDismissTask={handleDismissTask}
                    onUpdateTask={handleUpdateTask}
                    onConfirmDeadline={handleConfirmDeadline}
                    onConfirmUrgency={handleConfirmUrgency}
                    onCreateTask={handleCreateTask}
                />
            );
            break;

        case 'calendar':
            content = (
                <CalendarEventsView
                    onNavigateToDetail={(id) => navigate('detail', { id })}
                    demoMode={demoMode}
                />
            );
            break;

        case 'chat':
            content = (
                <ChatView
                    onNavigate={navigate}
                    demoMode={demoMode}
                />
            );
            break;

        case 'settings':
            content = <SettingsView demoMode={demoMode} onNavigate={navigate} />;
            break;

        case 'billing':
            content = <BillingView />;
            break;

        case 'checkout-success':
            return <CheckoutSuccess onNavigate={navigate} />;

        case 'checkout-cancel':
            return <CheckoutCancel onNavigate={navigate} />;

        case 'detail':
            const msg = messages.find(m => m.id === viewParams.id);
            content = (
                <MessageDetail
                    message={msg}
                    onBack={() => navigate('dashboard')}
                    onDraftReply={(id) => navigate('draft', { id })}
                    onToggleTask={handleToggleTask}
                    onApproveTask={handleApproveTask}
                    onDismissTask={handleDismissTask}
                    onApproveExtractedTask={handleApproveExtractedTask}
                    schedulingSuggestion={schedulingSuggestions[viewParams.id]}
                    onSendScheduling={handleSendScheduling}
                    onDismissScheduling={handleDismissScheduling}
                    onCreateCalendarEvent={handleCreateCalendarEvent}
                    onRefreshScheduling={handleRefreshScheduling}
                    isRefreshingScheduling={isRefreshingScheduling}
                />
            );
            break;

        case 'draft':
            const draftMsg = messages.find(m => m.id === viewParams.id);
            content = (
                <DraftReply
                    message={draftMsg}
                    onBack={() => navigate('detail', { id: viewParams.id })}
                    demoMode={demoMode}
                />
            );
            break;

        default:
            content = <div>Page not found</div>;
    }

    return (
        <div className="max-w-md mx-auto min-h-screen bg-gray-50 shadow-2xl overflow-hidden relative flex flex-col">
            {/* Trial Banner - shown for active trial users */}
            {isAuthenticated && isTrialUser && isActive && !demoMode && currentView !== 'landing' && currentView !== 'auth' && (
                <TrialBanner />
            )}

            <div className="flex-1 overflow-auto">
                {content}
            </div>

            {currentView !== 'landing' && currentView !== 'billing' && currentView !== 'checkout-success' && currentView !== 'checkout-cancel' && currentView !== 'chat' && (
                <BottomNav currentView={currentView} onNavigate={navigate} />
            )}

            {/* Delete Confirmation Dialog */}
            <DeleteConfirmDialog
                isOpen={deleteDialogOpen}
                onClose={() => {
                    setDeleteDialogOpen(false);
                    setMessageToDelete(null);
                }}
                onConfirm={confirmDelete}
                onArchive={archiveInsteadOfDelete}
                messageSubject={messageToDelete?.subject || "this message"}
                tasksCount={(messageToDelete?.tasks || []).length}
                suggestionsCount={0}
                demoMode={demoMode}
            />

            {/* Trial Expired Prompt - blocks app when trial expired */}
            {isAuthenticated && isTrialExpired && !demoMode && (
                <TrialExpiredPrompt />
            )}
        </div>
    );
};

// Wrap with AuthProvider and SubscriptionProvider
const App = () => (
    <AuthProvider>
        <SubscriptionProvider>
            <AppContent />
        </SubscriptionProvider>
    </AuthProvider>
);

export default App;
