"use client";

import { useMemo, useState, useTransition, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    addDays,
    addMonths,
    addWeeks,
    endOfDay,
    endOfMonth,
    endOfWeek,
    format,
    isSameDay,
    isSameMonth,
    parseISO,
    startOfDay,
    startOfMonth,
    startOfWeek,
} from "date-fns";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Loader2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { setCalendarView } from "./actions";
import {
    CalendarEvent,
    CalendarSettings,
    createEventFromSuggestion,
    createManualEvent,
    deleteEvent,
    fetchCalendarEvents,
    fetchCalendarSettings,
    fetchCalendars,
    generateBriefing,
    syncCalendar,
    updateCalendarSettings,
    updateEvent,
} from "@/services/calendar";
import {
    SchedulingSuggestion,
    dismissSchedulingSuggestion,
    fetchSchedulingSuggestions,
    sendSchedulingSuggestion,
} from "@/services/scheduling";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type CalendarView = "month" | "week" | "day" | "list";

const VIEW_LABELS: Record<CalendarView, string> = {
    month: "Month",
    week: "Week",
    day: "Day",
    list: "List",
};

const WEEK_STARTS_ON = 1; // Monday

export default function CalendarClient({ initialView }: { initialView: string }) {
    const [view, setView] = useState<CalendarView>(
        ["month", "week", "day", "list"].includes(initialView) ? (initialView as CalendarView) : "month"
    );
    const [selectedDate, setSelectedDate] = useState<Date>(new Date());
    const [isPendingViewSave, startViewTransition] = useTransition();
    const [eventDialogOpen, setEventDialogOpen] = useState(false);
    const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);

    const queryClient = useQueryClient();

    const range = useMemo(() => {
        if (view === "month") {
            return {
                start: startOfWeek(startOfMonth(selectedDate), { weekStartsOn: WEEK_STARTS_ON }),
                end: endOfWeek(endOfMonth(selectedDate), { weekStartsOn: WEEK_STARTS_ON }),
            };
        }
        if (view === "week") {
            return {
                start: startOfWeek(selectedDate, { weekStartsOn: WEEK_STARTS_ON }),
                end: endOfWeek(selectedDate, { weekStartsOn: WEEK_STARTS_ON }),
            };
        }
        if (view === "day") {
            return { start: startOfDay(selectedDate), end: endOfDay(selectedDate) };
        }
        return { start: startOfDay(selectedDate), end: addDays(endOfDay(selectedDate), 30) };
    }, [selectedDate, view]);

    const eventsQuery = useQuery({
        queryKey: ["calendar-events", range.start.toISOString(), range.end.toISOString()],
        queryFn: () =>
            fetchCalendarEvents({
                start_time: range.start.toISOString(),
                end_time: range.end.toISOString(),
                limit: 500,
            }),
    });

    const settingsQuery = useQuery({
        queryKey: ["calendar-settings"],
        queryFn: fetchCalendarSettings,
    });

    const calendarsQuery = useQuery({
        queryKey: ["calendar-calendars"],
        queryFn: fetchCalendars,
    });

    const suggestionsQuery = useQuery({
        queryKey: ["scheduling-suggestions"],
        queryFn: () => fetchSchedulingSuggestions({ status: "pending", limit: 20 }),
    });

    const syncMutation = useMutation({
        mutationFn: () => syncCalendar(14),
        onSuccess: async () => {
            await queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
            toast.success("Calendar synced");
        },
        onError: (error: any) => toast.error(error?.message || "Failed to sync calendar"),
    });

    const createEventMutation = useMutation({
        mutationFn: createManualEvent,
        onMutate: () => {
            setEventDialogOpen(false);
            setEditingEvent(null);
        },
        onSuccess: () => {
            toast.success("Event created");
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        },
        onError: (error: any) => toast.error(error?.message || "Failed to create event"),
    });

    const updateEventMutation = useMutation({
        mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof updateEvent>[1] }) =>
            updateEvent(id, payload),
        onMutate: () => {
            setEventDialogOpen(false);
            setEditingEvent(null);
        },
        onSuccess: () => {
            toast.success("Event updated");
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        },
        onError: (error: any) => toast.error(error?.message || "Failed to update event"),
    });

    const deleteEventMutation = useMutation({
        mutationFn: deleteEvent,
        onMutate: () => {
            setEventDialogOpen(false);
            setEditingEvent(null);
        },
        onSuccess: () => {
            toast.success("Event deleted");
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        },
        onError: (error: any) => toast.error(error?.message || "Failed to delete event"),
    });

    const suggestionAcceptMutation = useMutation({
        mutationFn: createEventFromSuggestion,
        onSuccess: async () => {
            await queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
            await queryClient.invalidateQueries({ queryKey: ["scheduling-suggestions"] });
            toast.success("Event created from suggestion");
        },
        onError: (error: any) => toast.error(error?.message || "Failed to create event"),
    });

    const suggestionSendMutation = useMutation({
        mutationFn: ({ id, reply }: { id: number; reply?: string }) => sendSchedulingSuggestion(id, reply),
        onSuccess: async () => {
            await queryClient.invalidateQueries({ queryKey: ["scheduling-suggestions"] });
            toast.success("Availability reply sent");
        },
        onError: (error: any) => toast.error(error?.message || "Failed to send reply"),
    });

    const suggestionDismissMutation = useMutation({
        mutationFn: dismissSchedulingSuggestion,
        onSuccess: async () => {
            await queryClient.invalidateQueries({ queryKey: ["scheduling-suggestions"] });
            toast.success("Suggestion dismissed");
        },
        onError: (error: any) => toast.error(error?.message || "Failed to dismiss suggestion"),
    });

    const generateBriefMutation = useMutation({
        mutationFn: generateBriefing,
        onSuccess: async () => {
            await queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
            toast.success("Meeting brief generated");
        },
        onError: (error: any) => toast.error(error?.message || "Failed to generate briefing"),
    });

    const updateSettingsMutation = useMutation({
        mutationFn: updateCalendarSettings,
        onSuccess: async (data) => {
            queryClient.setQueryData(["calendar-settings"], data);
        },
    });

    const events = eventsQuery.data?.events ?? [];

    const handleViewChange = (next: CalendarView) => {
        setView(next);
        startViewTransition(() => setCalendarView(next));
    };

    const handlePrev = () => {
        if (view === "month") setSelectedDate(addMonths(selectedDate, -1));
        if (view === "week") setSelectedDate(addWeeks(selectedDate, -1));
        if (view === "day") setSelectedDate(addDays(selectedDate, -1));
        if (view === "list") setSelectedDate(addDays(selectedDate, -7));
    };

    const handleNext = () => {
        if (view === "month") setSelectedDate(addMonths(selectedDate, 1));
        if (view === "week") setSelectedDate(addWeeks(selectedDate, 1));
        if (view === "day") setSelectedDate(addDays(selectedDate, 1));
        if (view === "list") setSelectedDate(addDays(selectedDate, 7));
    };

    const openCreateDialog = () => {
        setEditingEvent(null);
        setEventDialogOpen(true);
    };

    const openEditDialog = (event: CalendarEvent) => {
        setEditingEvent(event);
        setEventDialogOpen(true);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
            <section className="space-y-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2">
                            <CalendarIcon className="text-auburn" size={20} />
                            <h1 className="text-2xl font-semibold text-foreground">Calendar</h1>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="ghost" size="icon" onClick={handlePrev}>
                                <ChevronLeft size={18} />
                            </Button>
                            <div className="text-sm font-medium text-muted-foreground min-w-[140px] text-center">
                                {format(selectedDate, view === "day" ? "EEEE, MMM d" : "MMMM yyyy")}
                            </div>
                            <Button variant="ghost" size="icon" onClick={handleNext}>
                                <ChevronRight size={18} />
                            </Button>
                            <Button variant="ghost" onClick={() => setSelectedDate(new Date())}>Today</Button>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 rounded-full border border-auburn/20 bg-white/60 p-1">
                            {(Object.keys(VIEW_LABELS) as CalendarView[]).map((v) => (
                                <Button
                                    key={v}
                                    variant={view === v ? "default" : "ghost"}
                                    size="sm"
                                    onClick={() => handleViewChange(v)}
                                    disabled={isPendingViewSave}
                                    className={cn(view === v && "bg-auburn text-white")}
                                >
                                    {VIEW_LABELS[v]}
                                </Button>
                            ))}
                        </div>
                        <Button onClick={openCreateDialog} className="gap-2">
                            <Plus size={16} />
                            New Event
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => syncMutation.mutate()}
                            disabled={syncMutation.isPending}
                        >
                            {syncMutation.isPending ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                        </Button>
                    </div>
                </div>

                <div className="rounded-2xl border border-auburn/10 bg-white/80 shadow-sm p-4">
                    {eventsQuery.isLoading ? (
                        <div className="flex items-center justify-center py-24">
                            <Loader2 className="h-8 w-8 animate-spin text-auburn" />
                        </div>
                    ) : (
                        <>
                            {view === "month" && (
                                <MonthView
                                    selectedDate={selectedDate}
                                    events={events}
                                    onSelectDate={setSelectedDate}
                                    onSelectEvent={openEditDialog}
                                />
                            )}
                            {view === "week" && (
                                <WeekView
                                    weekStart={startOfWeek(selectedDate, { weekStartsOn: WEEK_STARTS_ON })}
                                    events={events}
                                    onSelectEvent={openEditDialog}
                                />
                            )}
                            {view === "day" && (
                                <DayView
                                    day={selectedDate}
                                    events={events}
                                    onSelectEvent={openEditDialog}
                                />
                            )}
                            {view === "list" && (
                                <ListView
                                    rangeStart={range.start}
                                    rangeEnd={range.end}
                                    events={events}
                                    onSelectEvent={openEditDialog}
                                />
                            )}
                        </>
                    )}
                </div>
            </section>

            <aside className="space-y-6">
                <CalendarSettingsPanel
                    settings={settingsQuery.data}
                    calendars={calendarsQuery.data?.calendars ?? []}
                    onUpdate={(payload) => updateSettingsMutation.mutateAsync(payload)}
                />

                <SuggestionsPanel
                    suggestions={suggestionsQuery.data?.suggestions ?? []}
                    onAccept={(suggestionId, slotIndex) =>
                        suggestionAcceptMutation.mutate({ suggestion_id: suggestionId, selected_slot_index: slotIndex })
                    }
                    onSend={(suggestionId, reply) => suggestionSendMutation.mutate({ id: suggestionId, reply })}
                    onDismiss={(suggestionId) => suggestionDismissMutation.mutate(suggestionId)}
                />
            </aside>

            <EventDialog
                open={eventDialogOpen}
                onOpenChange={setEventDialogOpen}
                event={editingEvent}
                settings={settingsQuery.data}
                onCreate={(payload) => createEventMutation.mutate(payload)}
                onUpdate={(id, payload) => updateEventMutation.mutate({ id, payload })}
                onDelete={(id) => deleteEventMutation.mutate(id)}
                onGenerateBrief={(id) => generateBriefMutation.mutate(id)}
            />
        </div>
    );
}

function MonthView({
    selectedDate,
    events,
    onSelectDate,
    onSelectEvent,
}: {
    selectedDate: Date;
    events: CalendarEvent[];
    onSelectDate: (date: Date) => void;
    onSelectEvent: (event: CalendarEvent) => void;
}) {
    const start = startOfWeek(startOfMonth(selectedDate), { weekStartsOn: WEEK_STARTS_ON });
    const end = endOfWeek(endOfMonth(selectedDate), { weekStartsOn: WEEK_STARTS_ON });
    const days: Date[] = [];
    for (let day = start; day <= end; day = addDays(day, 1)) {
        days.push(day);
    }

    const eventsByDay = useMemo(() => {
        const map = new Map<string, CalendarEvent[]>();
        events.forEach((event) => {
            const key = format(parseISO(event.start_time), "yyyy-MM-dd");
            const list = map.get(key) || [];
            list.push(event);
            map.set(key, list);
        });
        return map;
    }, [events]);

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-7 text-xs uppercase tracking-wide text-muted-foreground">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label) => (
                    <div key={label} className="px-2 py-1 text-center">{label}</div>
                ))}
            </div>
            <div className="grid grid-cols-7 gap-2">
                {days.map((day) => {
                    const key = format(day, "yyyy-MM-dd");
                    const dayEvents = eventsByDay.get(key) || [];
                    return (
                        <button
                            key={key}
                            onClick={() => onSelectDate(day)}
                            className={cn(
                                "rounded-xl border border-auburn/10 bg-white/70 p-2 text-left hover:border-auburn/30 transition",
                                !isSameMonth(day, selectedDate) && "opacity-50",
                                isSameDay(day, new Date()) && "border-auburn/40 bg-auburn/5"
                            )}
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-semibold">{format(day, "d")}</span>
                                {dayEvents.length > 0 && (
                                    <span className="text-xs text-muted-foreground">{dayEvents.length}</span>
                                )}
                            </div>
                            <div className="mt-2 space-y-1">
                                {dayEvents.slice(0, 3).map((event) => (
                                    <div
                                        key={event.id}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onSelectEvent(event);
                                        }}
                                        className="truncate rounded-md bg-auburn/10 px-2 py-1 text-xs text-auburn"
                                    >
                                        {event.title}
                                    </div>
                                ))}
                                {dayEvents.length > 3 && (
                                    <div className="text-xs text-muted-foreground">+{dayEvents.length - 3} more</div>
                                )}
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

function WeekView({
    weekStart,
    events,
    onSelectEvent,
}: {
    weekStart: Date;
    events: CalendarEvent[];
    onSelectEvent: (event: CalendarEvent) => void;
}) {
    const days = Array.from({ length: 7 }, (_, idx) => addDays(weekStart, idx));
    return (
        <div className="space-y-4">
            <div className="grid grid-cols-8 gap-2 text-xs uppercase tracking-wide text-muted-foreground">
                <div />
                {days.map((day) => (
                    <div key={day.toISOString()} className="text-center">
                        <div className="font-medium text-foreground">{format(day, "EEE")}</div>
                        <div>{format(day, "d")}</div>
                    </div>
                ))}
            </div>
            <TimeGrid days={days} events={events} onSelectEvent={onSelectEvent} />
        </div>
    );
}

function DayView({
    day,
    events,
    onSelectEvent,
}: {
    day: Date;
    events: CalendarEvent[];
    onSelectEvent: (event: CalendarEvent) => void;
}) {
    return <TimeGrid days={[day]} events={events} onSelectEvent={onSelectEvent} />;
}

function TimeGrid({
    days,
    events,
    onSelectEvent,
}: {
    days: Date[];
    events: CalendarEvent[];
    onSelectEvent: (event: CalendarEvent) => void;
}) {
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const hourHeight = 48;

    return (
        <div className="grid grid-cols-[60px_1fr] gap-2">
            <div className="flex flex-col text-xs text-muted-foreground">
                {hours.map((hour) => (
                    <div key={hour} className="h-12 flex items-start justify-end pr-2">
                        {format(new Date().setHours(hour, 0), "ha")}
                    </div>
                ))}
            </div>
            <div className="grid" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}>
                {days.map((day) => (
                    <div key={day.toISOString()} className="relative border-l border-auburn/10 px-1">
                        <div className="absolute top-0 left-0 right-0 flex gap-1">
                            {events
                                .filter((event) => event.all_day && isSameDay(parseISO(event.start_time), day))
                                .map((event) => (
                                    <div
                                        key={event.id}
                                        className="rounded-md bg-auburn/10 px-2 py-1 text-xs text-auburn"
                                        onClick={() => onSelectEvent(event)}
                                    >
                                        {event.title}
                                    </div>
                                ))}
                        </div>
                        <div className="relative pt-6" style={{ height: hours.length * hourHeight }}>
                            {events
                                .filter((event) => !event.all_day && isSameDay(parseISO(event.start_time), day))
                                .map((event) => {
                                    const start = parseISO(event.start_time);
                                    const end = parseISO(event.end_time);
                                    const startMinutes = start.getHours() * 60 + start.getMinutes();
                                    const endMinutes = end.getHours() * 60 + end.getMinutes();
                                    const top = (startMinutes / 60) * hourHeight;
                                    const height = Math.max(24, ((endMinutes - startMinutes) / 60) * hourHeight);
                                    return (
                                        <button
                                            key={event.id}
                                            onClick={() => onSelectEvent(event)}
                                            className="absolute left-1 right-1 rounded-lg bg-auburn/10 px-2 py-1 text-left text-xs text-auburn shadow-sm hover:bg-auburn/20"
                                            style={{ top, height }}
                                        >
                                            <div className="font-semibold">{event.title}</div>
                                            <div className="text-[10px] text-auburn/80">
                                                {format(start, "p")} - {format(end, "p")}
                                            </div>
                                        </button>
                                    );
                                })}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function ListView({
    rangeStart,
    rangeEnd,
    events,
    onSelectEvent,
}: {
    rangeStart: Date;
    rangeEnd: Date;
    events: CalendarEvent[];
    onSelectEvent: (event: CalendarEvent) => void;
}) {
    const days: Date[] = [];
    for (let day = rangeStart; day <= rangeEnd; day = addDays(day, 1)) {
        days.push(day);
    }

    return (
        <div className="space-y-6">
            {days.map((day) => {
                const dayEvents = events.filter((event) => isSameDay(parseISO(event.start_time), day));
                if (!dayEvents.length) return null;
                return (
                    <div key={day.toISOString()} className="space-y-2">
                        <div className="text-sm font-semibold text-muted-foreground">
                            {format(day, "EEEE, MMM d")}
                        </div>
                        <div className="space-y-2">
                            {dayEvents.map((event) => (
                                <button
                                    key={event.id}
                                    onClick={() => onSelectEvent(event)}
                                    className="w-full rounded-xl border border-auburn/10 bg-white/70 p-3 text-left hover:border-auburn/30"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="font-semibold text-foreground">{event.title}</div>
                                        <div className="text-xs text-muted-foreground">
                                            {event.all_day ? "All day" : `${format(parseISO(event.start_time), "p")} - ${format(parseISO(event.end_time), "p")}`}
                                        </div>
                                    </div>
                                    {event.location && (
                                        <div className="text-xs text-muted-foreground mt-1">{event.location}</div>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function CalendarSettingsPanel({
    settings,
    calendars,
    onUpdate,
}: {
    settings?: CalendarSettings;
    calendars: { id: string; summary: string; primary?: boolean }[];
    onUpdate: (payload: Parameters<typeof updateCalendarSettings>[0]) => Promise<CalendarSettings>;
}) {
    const [saving, setSaving] = useState(false);

    const handleChange = async (payload: Parameters<typeof updateCalendarSettings>[0]) => {
        try {
            setSaving(true);
            await onUpdate(payload);
            toast.success("Calendar settings updated");
        } catch (error: any) {
            toast.error(error?.message || "Failed to update settings");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="rounded-2xl border border-auburn/10 bg-white/80 shadow-sm p-4 space-y-4">
            <div className="font-semibold text-foreground">Calendar Settings</div>
            <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Default Calendar</label>
                <select
                    className="w-full rounded-lg border border-auburn/10 bg-white px-3 py-2 text-sm"
                    value={settings?.default_calendar_id || "primary"}
                    onChange={(e) => handleChange({ default_calendar_id: e.target.value })}
                    disabled={saving}
                >
                    {(calendars.length ? calendars : [{ id: "primary", summary: "Primary", primary: true }]).map((cal) => (
                        <option key={cal.id} value={cal.id}>
                            {cal.summary}{cal.primary ? " (Primary)" : ""}
                        </option>
                    ))}
                </select>
            </div>
            <div className="flex items-center justify-between gap-3">
                <div>
                    <div className="text-sm font-medium text-foreground">Auto-generate briefs</div>
                    <div className="text-xs text-muted-foreground">Generate 1 hour before meetings by default</div>
                </div>
                <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={settings?.auto_briefing_enabled ?? true}
                    onChange={(e) => handleChange({ auto_briefing_enabled: e.target.checked })}
                />
            </div>
            <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Briefing lead time (hours)</label>
                <Input
                    type="number"
                    min={1}
                    value={settings?.briefing_hours_before ?? 1}
                    onChange={(e) => handleChange({ briefing_hours_before: Number(e.target.value || 1) })}
                    disabled={saving}
                />
            </div>
        </div>
    );
}

function SuggestionsPanel({
    suggestions,
    onAccept,
    onSend,
    onDismiss,
}: {
    suggestions: SchedulingSuggestion[];
    onAccept: (suggestionId: number, slotIndex: number) => void;
    onSend: (suggestionId: number, reply?: string) => void;
    onDismiss: (suggestionId: number) => void;
}) {
    return (
        <div className="rounded-2xl border border-auburn/10 bg-white/80 shadow-sm p-4 space-y-4">
            <div className="font-semibold text-foreground">Scheduling Suggestions</div>
            {suggestions.length === 0 && (
                <div className="text-sm text-muted-foreground">No pending suggestions.</div>
            )}
            {suggestions.map((suggestion) => (
                <div key={suggestion.id} className="rounded-xl border border-auburn/10 bg-white/70 p-3 space-y-3">
                    <div className="text-sm font-semibold text-foreground">
                        {suggestion.meeting_type} with {suggestion.participants.join(", ") || "guest"}
                    </div>
                    <div className="space-y-2">
                        {suggestion.suggested_slots.slice(0, 3).map((slot, idx) => (
                            <button
                                key={`${suggestion.id}-${idx}`}
                                onClick={() => onAccept(suggestion.id, idx)}
                                className="w-full rounded-lg bg-auburn/10 px-3 py-2 text-left text-xs text-auburn hover:bg-auburn/20"
                            >
                                {format(parseISO(slot.start_time), "EEE, MMM d p")} - {format(parseISO(slot.end_time), "p")}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-2">
                        <Button size="sm" onClick={() => onSend(suggestion.id, suggestion.draft_reply || undefined)}>
                            Send Availability
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => onDismiss(suggestion.id)}>
                            Dismiss
                        </Button>
                    </div>
                </div>
            ))}
        </div>
    );
}

function EventDialog({
    open,
    onOpenChange,
    event,
    settings,
    onCreate,
    onUpdate,
    onDelete,
    onGenerateBrief,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    event: CalendarEvent | null;
    settings?: CalendarSettings;
    onCreate: (payload: Parameters<typeof createManualEvent>[0]) => void;
    onUpdate: (id: number, payload: Parameters<typeof updateEvent>[1]) => void;
    onDelete: (id: number) => void;
    onGenerateBrief: (id: number) => void;
}) {
    const [title, setTitle] = useState(event?.title || "");
    const [location, setLocation] = useState(event?.location || "");
    const [description, setDescription] = useState(event?.description || "");
    const [notes, setNotes] = useState(event?.notes || "");
    const [participants, setParticipants] = useState(
        Array.isArray(event?.participants) ? event?.participants.map((p) => (typeof p === "string" ? p : p.email || "")).filter(Boolean).join(", ") : ""
    );
    const [allDay, setAllDay] = useState(event?.all_day ?? false);
    const [startValue, setStartValue] = useState(getDateInputValue(event?.start_time, event?.all_day));
    const [endValue, setEndValue] = useState(getDateInputValue(event?.end_time, event?.all_day, event?.start_time));

    const reset = () => {
        setTitle(event?.title || "");
        setLocation(event?.location || "");
        setDescription(event?.description || "");
        setNotes(event?.notes || "");
        setParticipants(
            Array.isArray(event?.participants) ? event?.participants.map((p) => (typeof p === "string" ? p : p.email || "")).filter(Boolean).join(", ") : ""
        );
        setAllDay(event?.all_day ?? false);
        setStartValue(getDateInputValue(event?.start_time, event?.all_day));
        setEndValue(getDateInputValue(event?.end_time, event?.all_day, event?.start_time));
    };

    useEffect(() => {
        reset();
    }, [event?.id, open]);

    const handleSave = () => {
        const participantList = participants
            .split(",")
            .map((p) => p.trim())
            .filter(Boolean);

        const timezone = settings?.default_timezone || "UTC";

        const { start_time, end_time } = buildTimes(startValue, endValue, allDay);
        const payload = {
            title,
            description: description || undefined,
            notes: notes || undefined,
            participants: participantList,
            all_day: allDay,
            timezone,
            location: location || undefined,
        };

        if (event) {
            onUpdate(event.id, { ...payload, start_time, end_time });
        } else {
            onCreate({ ...payload, start_time, end_time });
        }
    };

    return (
        <Dialog open={open} onOpenChange={(next) => {
            if (!next) reset();
            onOpenChange(next);
        }}>
            <DialogContent className="max-w-xl">
                <DialogHeader>
                    <DialogTitle>{event ? "Edit Event" : "New Event"}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                    <Input placeholder="Event title" value={title} onChange={(e) => setTitle(e.target.value)} />
                    <div className="grid grid-cols-2 gap-3">
                        <Input
                            type={allDay ? "date" : "datetime-local"}
                            value={startValue}
                            onChange={(e) => setStartValue(e.target.value)}
                        />
                        <Input
                            type={allDay ? "date" : "datetime-local"}
                            value={endValue}
                            onChange={(e) => setEndValue(e.target.value)}
                        />
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
                        All day
                    </label>
                    <Input placeholder="Location or link" value={location || ""} onChange={(e) => setLocation(e.target.value)} />
                    <Input placeholder="Attendees (comma separated)" value={participants} onChange={(e) => setParticipants(e.target.value)} />
                    <Textarea placeholder="Description (optional)" value={description || ""} onChange={(e) => setDescription(e.target.value)} />
                    <Textarea placeholder="Internal notes (not synced)" value={notes || ""} onChange={(e) => setNotes(e.target.value)} />
                    {event?.briefing && (
                        <div className="rounded-lg border bg-muted/40 p-4 space-y-3">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-semibold">Meeting Brief</h4>
                                {event.briefing_generated_at && (
                                    <span className="text-xs text-muted-foreground">
                                        {format(parseISO(event.briefing_generated_at), "PPP p")}
                                    </span>
                                )}
                            </div>

                            {event.briefing.agenda && event.briefing.agenda !== "No agenda provided" && (
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-1">Agenda</p>
                                    <p className="text-sm">{event.briefing.agenda}</p>
                                </div>
                            )}

                            {event.briefing.attendees && event.briefing.attendees.length > 0 && (
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-1">Attendees</p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {event.briefing.attendees.map((a, i) => (
                                            <span key={i} className="inline-flex items-center rounded-full bg-background px-2 py-0.5 text-xs border">
                                                {a.name || a.email}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {event.briefing.related_emails && event.briefing.related_emails.length > 0 && (
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-1">Related emails ({event.briefing.message_count})</p>
                                    <div className="space-y-1.5">
                                        {event.briefing.related_emails.slice(0, 3).map((e, i) => (
                                            <div key={i} className="text-xs bg-background rounded p-2 border">
                                                <span className="font-medium">{e.subject}</span>
                                                {e.sender && <span className="text-muted-foreground"> — {e.sender}</span>}
                                                {e.summary && <p className="text-muted-foreground mt-0.5">{e.summary}</p>}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {event.briefing.open_tasks && event.briefing.open_tasks.length > 0 && (
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-1">Open tasks ({event.briefing.task_count})</p>
                                    <ul className="space-y-1">
                                        {event.briefing.open_tasks.map((t, i) => (
                                            <li key={i} className="text-xs flex items-center gap-1.5">
                                                <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 shrink-0" />
                                                <span>{t.title}</span>
                                                {t.priority && t.priority !== "normal" && (
                                                    <span className={`text-[10px] px-1 rounded ${t.priority === "urgent" || t.priority === "high" ? "bg-red-100 text-red-700" : "bg-muted text-muted-foreground"}`}>
                                                        {t.priority}
                                                    </span>
                                                )}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {event.briefing.prep_warnings && event.briefing.prep_warnings.length > 0 && (
                                <div className="rounded border border-yellow-200 bg-yellow-50 p-2 dark:border-yellow-800 dark:bg-yellow-950">
                                    <p className="text-xs font-medium text-yellow-800 dark:text-yellow-200 mb-1">Prep warnings</p>
                                    <ul className="space-y-0.5">
                                        {event.briefing.prep_warnings.map((w, i) => (
                                            <li key={i} className="text-xs text-yellow-700 dark:text-yellow-300">{w}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {event.briefing.prep_complete && (
                                <p className="text-xs text-green-600 dark:text-green-400 font-medium">Prep complete</p>
                            )}
                        </div>
                    )}
                </div>
                <div className="mt-6 flex items-center justify-between">
                    {event ? (
                        <div className="flex items-center gap-2">
                            <Button variant="ghost" onClick={() => onGenerateBrief(event.id)}>Generate Brief</Button>
                            <Button variant="destructive" onClick={() => onDelete(event.id)}>Delete</Button>
                        </div>
                    ) : <div />}
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
                        <Button onClick={handleSave} disabled={!title.trim()}>Save</Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function buildTimes(startValue: string, endValue: string, allDay: boolean): { start_time: string; end_time: string } {
    if (allDay) {
        const start = new Date(`${startValue}T00:00:00`);
        const end = new Date(`${endValue || startValue}T00:00:00`);
        end.setDate(end.getDate() + 1);
        return { start_time: start.toISOString(), end_time: end.toISOString() };
    }
    const start = new Date(startValue);
    const end = new Date(endValue || startValue);
    return { start_time: start.toISOString(), end_time: end.toISOString() };
}

function getDateInputValue(iso?: string, allDay?: boolean, startIso?: string) {
    if (!iso) {
        const now = new Date();
        return allDay ? format(now, "yyyy-MM-dd") : format(now, "yyyy-MM-dd'T'HH:mm");
    }
    const date = parseISO(iso);
    if (allDay && startIso) {
        const endDate = parseISO(iso);
        endDate.setDate(endDate.getDate() - 1);
        return format(endDate, "yyyy-MM-dd");
    }
    return allDay ? format(date, "yyyy-MM-dd") : format(date, "yyyy-MM-dd'T'HH:mm");
}
