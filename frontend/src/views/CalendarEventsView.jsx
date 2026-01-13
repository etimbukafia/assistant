import React, { useState, useEffect } from 'react';
import { Calendar, Clock, MapPin, ChevronRight, RefreshCw, X, Sparkles } from 'lucide-react';
import { API_BASE_URL } from '../utils/constants';
import MeetingBriefingCard from '../components/MeetingBriefingCard';
import FollowUpGenerator from '../components/FollowUpGenerator';

const CalendarEventsView = ({ onNavigateToDetail, demoMode }) => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isSyncing, setIsSyncing] = useState(false);
    const [selectedEvent, setSelectedEvent] = useState(null);

    useEffect(() => {
        fetchEvents();
    }, []);

    const fetchEvents = async () => {
        if (demoMode) {
            setEvents([
                {
                    id: 1,
                    title: "Architecture Review",
                    start_time: new Date(Date.now() + 3600000).toISOString(),
                    end_time: new Date(Date.now() + 7200000).toISOString(),
                    location: "Zoom",
                    participants: ["dev@example.com", "architect@example.com"],
                    status: "upcoming",
                    briefing: {
                        agenda: "Review the new agentic architecture for the assistant.",
                        prep_complete: false,
                        prep_warnings: [
                            { message: "No agenda document shared yet", severity: "medium", suggestion: "Share the architecture doc" }
                        ],
                        attendees: [{ name: "Dev", email: "dev@example.com" }, { name: "Architect", email: "architect@example.com" }],
                        related_emails: [],
                        open_tasks: []
                    }
                },
                {
                    id: 2,
                    title: "Product Sync",
                    start_time: new Date(Date.now() - 3600000).toISOString(),
                    end_time: new Date(Date.now()).toISOString(),
                    location: "Microsoft Teams",
                    participants: ["pm@example.com"],
                    status: "completed"
                }
            ]);
            setLoading(false);
            return;
        }

        try {
            const res = await fetch(`${API_BASE_URL}/calendar/events`);
            const data = await res.json();
            setEvents(data.events || []);
        } catch (err) {
            console.error("Failed to fetch calendar events", err);
        } finally {
            setLoading(false);
        }
    };

    const handleSync = async () => {
        setIsSyncing(true);
        if (demoMode) {
            await new Promise(r => setTimeout(r, 2000));
        } else {
            try {
                await fetch(`${API_BASE_URL}/calendar/sync`, { method: 'POST' });
                await fetchEvents();
            } catch (err) {
                console.error("Sync failed", err);
            }
        }
        setIsSyncing(false);
    };

    const formatTime = (isoString) => {
        const date = new Date(isoString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    const formatDate = (isoString) => {
        const date = new Date(isoString);
        const now = new Date();
        if (date.toDateString() === now.toDateString()) return 'Today';
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-12 space-y-4">
                <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-gray-500 font-medium">Loading your schedule...</p>
            </div>
        );
    }

    return (
        <div className="pb-24 animate-in fade-in duration-500">
            {/* Header */}
            <div className="bg-white border-b border-gray-100 p-6 sticky top-0 z-10">
                <div className="flex items-center justify-between mb-2">
                    <h1 className="text-2xl font-bold text-gray-900">Meetings</h1>
                    <button
                        onClick={handleSync}
                        disabled={isSyncing}
                        className={`p-2 rounded-full transition-all ${isSyncing ? 'bg-gray-100 text-gray-400' : 'bg-blue-50 text-blue-600 hover:bg-blue-100'}`}
                    >
                        <RefreshCw className={`w-5 h-5 ${isSyncing ? 'animate-spin' : ''}`} />
                    </button>
                </div>
                <p className="text-sm text-gray-500">Upcoming briefings and follow-ups</p>
            </div>

            <div className="p-4 space-y-4">
                {events.length === 0 ? (
                    <div className="bg-white rounded-3xl p-12 text-center border-2 border-dashed border-gray-100">
                        <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Calendar className="w-8 h-8 text-gray-300" />
                        </div>
                        <h3 className="text-lg font-bold text-gray-900">No meetings found</h3>
                        <p className="text-gray-500 text-sm mt-2 mb-6">Your calendar looks clear for the next few days.</p>
                        <button
                            onClick={handleSync}
                            className="bg-blue-600 text-white font-semibold px-6 py-2.5 rounded-full hover:bg-blue-700 transition-colors shadow-lg shadow-blue-100"
                        >
                            Sync Calendar
                        </button>
                    </div>
                ) : (
                    events.map((event) => (
                        <div key={event.id} className="space-y-4">
                            <div
                                onClick={() => setSelectedEvent(selectedEvent?.id === event.id ? null : event)}
                                className={`bg-white rounded-2xl border transition-all cursor-pointer p-5 ${selectedEvent?.id === event.id ? 'border-blue-200 shadow-lg ring-1 ring-blue-50' : 'border-gray-100 shadow-sm hover:border-gray-200 hover:shadow-md'}`}
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1.5">
                                            <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${event.status === 'completed' ? 'bg-gray-100 text-gray-600' : 'bg-green-100 text-green-700'}`}>
                                                {event.status === 'completed' ? 'Past' : formatDate(event.start_time)}
                                            </span>
                                            {event.briefing && !event.briefing.prep_complete && (
                                                <span className="flex items-center gap-1 text-[10px] font-bold uppercase text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-100">
                                                    <Sparkles className="w-2.5 h-2.5" /> Prep Needed
                                                </span>
                                            )}
                                        </div>
                                        <h3 className="text-base font-bold text-gray-900 truncate">{event.title}</h3>
                                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2">
                                            <div className="flex items-center gap-1.5 text-xs text-gray-500">
                                                <Clock className="w-3.5 h-3.5" />
                                                {formatTime(event.start_time)} – {formatTime(event.end_time)}
                                            </div>
                                            {event.location && (
                                                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                                                    <MapPin className="w-3.5 h-3.5" />
                                                    {event.location}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <div className={`mt-2 translate-y-1 transition-transform ${selectedEvent?.id === event.id ? 'rotate-90 text-blue-500' : 'text-gray-300'}`}>
                                        <ChevronRight className="w-5 h-5" />
                                    </div>
                                </div>
                            </div>

                            {/* Expanded Details */}
                            {selectedEvent?.id === event.id && (
                                <div className="animate-in slide-in-from-top-4 fade-in duration-300">
                                    {event.status === 'completed' ? (
                                        <FollowUpGenerator
                                            eventId={event.id}
                                            eventTitle={event.title}
                                            relatedMessageIds={event.related_message_ids || []}
                                            onFollowUpsCreated={() => fetchEvents()}
                                        />
                                    ) : (
                                        <MeetingBriefingCard
                                            briefing={event.briefing}
                                            onNavigateToDetail={onNavigateToDetail}
                                        />
                                    )}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default CalendarEventsView;
