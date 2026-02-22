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
import { ChevronLeft, ChevronRight, RefreshCw, Plus, AlertTriangle, CheckCircle2 } from "lucide-react";
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
const CARD_SHADOW = "0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05)";

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
        staleTime: 60_000, // matches backend calendar cache TTL (60s)
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
        onMutate: () => { setEventDialogOpen(false); setEditingEvent(null); },
        onSuccess: () => {
            toast.success("Event created");
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        },
        onError: (error: any) => toast.error(error?.message || "Failed to create event"),
    });

    const updateEventMutation = useMutation({
        mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof updateEvent>[1] }) =>
            updateEvent(id, payload),
        onMutate: () => { setEventDialogOpen(false); setEditingEvent(null); },
        onSuccess: () => {
            toast.success("Event updated");
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        },
        onError: (error: any) => toast.error(error?.message || "Failed to update event"),
    });

    const deleteEventMutation = useMutation({
        mutationFn: deleteEvent,
        onMutate: () => { setEventDialogOpen(false); setEditingEvent(null); },
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

    const openCreateDialog = () => { setEditingEvent(null); setEventDialogOpen(true); };
    const openEditDialog = (event: CalendarEvent) => { setEditingEvent(event); setEventDialogOpen(true); };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
            <section className="space-y-5">
                {/* Header */}
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-4">
                        {/* Date nav */}
                        <div className="flex items-center gap-1">
                            <button
                                onClick={handlePrev}
                                className="p-1.5 rounded-[6px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                            >
                                <ChevronLeft size={16} />
                            </button>
                            <span className="text-sm font-medium font-inter text-foreground min-w-[130px] text-center">
                                {format(selectedDate, view === "day" ? "EEE, MMM d" : "MMMM yyyy")}
                            </span>
                            <button
                                onClick={handleNext}
                                className="p-1.5 rounded-[6px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                            >
                                <ChevronRight size={16} />
                            </button>
                        </div>
                        <button
                            onClick={() => setSelectedDate(new Date())}
                            className="px-3 py-1 rounded-full border border-border text-[12px] font-medium font-inter text-muted-foreground hover:text-foreground transition-colors"
                        >
                            Today
                        </button>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* View toggle */}
                        <div className="flex gap-1 rounded-full border border-border p-1 w-fit">
                            {(Object.keys(VIEW_LABELS) as CalendarView[]).map((v) => (
                                <button
                                    key={v}
                                    onClick={() => handleViewChange(v)}
                                    disabled={isPendingViewSave}
                                    className={cn(
                                        "px-3 py-1 rounded-full text-[12px] font-medium font-inter transition-all",
                                        view === v
                                            ? "bg-foreground text-background"
                                            : "text-muted-foreground hover:text-foreground"
                                    )}
                                >
                                    {VIEW_LABELS[v]}
                                </button>
                            ))}
                        </div>

                        {/* New Event */}
                        <button
                            onClick={openCreateDialog}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] bg-primary text-white text-[13px] font-medium font-inter hover:bg-primary/90 transition-colors"
                        >
                            <Plus size={14} />
                            New Event
                        </button>

                        {/* Sync */}
                        <button
                            onClick={() => syncMutation.mutate()}
                            disabled={syncMutation.isPending}
                            className="p-1.5 rounded-[6px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                            {syncMutation.isPending ? (
                                <span className="flex gap-0.5">
                                    <span className="teeks-dot" style={{ width: 4, height: 4 }} />
                                    <span className="teeks-dot" style={{ width: 4, height: 4 }} />
                                    <span className="teeks-dot" style={{ width: 4, height: 4 }} />
                                </span>
                            ) : (
                                <RefreshCw size={15} />
                            )}
                        </button>
                    </div>
                </div>

                {/* Calendar surface */}
                <div
                    className="rounded-[14px] border border-border bg-white p-4"
                    style={{ boxShadow: CARD_SHADOW }}
                >
                    {eventsQuery.isLoading ? (
                        <div className="flex items-center justify-center gap-1 py-24">
                            <span className="teeks-dot" />
                            <span className="teeks-dot" />
                            <span className="teeks-dot" />
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

            {/* Sidebar */}
            <aside className="space-y-4">
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

// ─── MONTH VIEW ──────────────────────────────────────────────────────────────

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
    for (let day = start; day <= end; day = addDays(day, 1)) days.push(day);

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

    const today = new Date();

    return (
        <div className="space-y-3">
            {/* Day labels */}
            <div className="grid grid-cols-7">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label) => (
                    <div key={label} className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter text-center py-1">
                        {label}
                    </div>
                ))}
            </div>
            {/* Day cells */}
            <div className="grid grid-cols-7 gap-1.5">
                {days.map((day) => {
                    const key = format(day, "yyyy-MM-dd");
                    const dayEvents = eventsByDay.get(key) || [];
                    const isToday = isSameDay(day, today);
                    const isCurrentMonth = isSameMonth(day, selectedDate);

                    return (
                        <button
                            key={key}
                            onClick={() => onSelectDate(day)}
                            className={cn(
                                "rounded-[10px] border p-2 text-left transition-all duration-150 min-h-[72px]",
                                isCurrentMonth ? "bg-white border-border hover:border-border/80" : "bg-transparent border-transparent opacity-40",
                                isToday && "border-primary/30 bg-primary/[0.03]",
                            )}
                        >
                            <div className="flex items-center justify-between mb-1.5">
                                <span className={cn(
                                    "text-[13px] font-semibold font-inter w-6 h-6 flex items-center justify-center rounded-full",
                                    isToday ? "bg-primary text-white" : "text-foreground"
                                )}>
                                    {format(day, "d")}
                                </span>
                                {dayEvents.length > 3 && (
                                    <span className="text-[10px] text-muted-foreground/50 font-inter">
                                        +{dayEvents.length - 3}
                                    </span>
                                )}
                            </div>
                            <div className="space-y-0.5">
                                {dayEvents.slice(0, 3).map((event) => (
                                    <div
                                        key={event.id}
                                        onClick={(e) => { e.stopPropagation(); onSelectEvent(event); }}
                                        className="truncate rounded-[4px] bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary font-inter font-medium cursor-pointer hover:bg-primary/15 transition-colors"
                                    >
                                        {event.title}
                                    </div>
                                ))}
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

// ─── WEEK VIEW ───────────────────────────────────────────────────────────────

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
    const today = new Date();

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-8 gap-1 text-center">
                <div />
                {days.map((day) => (
                    <div key={day.toISOString()}>
                        <div className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter">
                            {format(day, "EEE")}
                        </div>
                        <div className={cn(
                            "text-sm font-semibold font-inter mx-auto w-7 h-7 flex items-center justify-center rounded-full",
                            isSameDay(day, today) ? "bg-primary text-white" : "text-foreground"
                        )}>
                            {format(day, "d")}
                        </div>
                    </div>
                ))}
            </div>
            <TimeGrid days={days} events={events} onSelectEvent={onSelectEvent} />
        </div>
    );
}

// ─── DAY VIEW ────────────────────────────────────────────────────────────────

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

// ─── TIME GRID ───────────────────────────────────────────────────────────────

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
        <div className="grid grid-cols-[52px_1fr] gap-2">
            <div className="flex flex-col text-[11px] font-inter text-muted-foreground/50">
                {hours.map((hour) => (
                    <div key={hour} className="h-12 flex items-start justify-end pr-2 pt-0.5">
                        {format(new Date().setHours(hour, 0), "ha")}
                    </div>
                ))}
            </div>
            <div className="grid" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }}>
                {days.map((day) => (
                    <div key={day.toISOString()} className="relative border-l border-border/40 px-1">
                        {/* All-day events */}
                        <div className="flex flex-wrap gap-1 mb-1">
                            {events
                                .filter((event) => event.all_day && isSameDay(parseISO(event.start_time), day))
                                .map((event) => (
                                    <button
                                        key={event.id}
                                        onClick={() => onSelectEvent(event)}
                                        className="rounded-[4px] bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary font-inter font-medium"
                                    >
                                        {event.title}
                                    </button>
                                ))}
                        </div>
                        {/* Timed events */}
                        <div className="relative" style={{ height: hours.length * hourHeight }}>
                            {/* Hour lines */}
                            {hours.map((hour) => (
                                <div
                                    key={hour}
                                    className="absolute left-0 right-0 border-t border-border/20"
                                    style={{ top: hour * hourHeight }}
                                />
                            ))}
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
                                            className="absolute left-1 right-1 rounded-[6px] bg-primary/10 border border-primary/20 px-2 py-1 text-left hover:bg-primary/15 transition-colors"
                                            style={{ top, height }}
                                        >
                                            <div className="text-[11px] font-semibold font-inter text-primary truncate">{event.title}</div>
                                            {height > 30 && (
                                                <div className="text-[10px] font-inter text-primary/60">
                                                    {format(start, "p")}
                                                </div>
                                            )}
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

// ─── LIST VIEW ───────────────────────────────────────────────────────────────

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
    for (let day = rangeStart; day <= rangeEnd; day = addDays(day, 1)) days.push(day);

    const hasAny = days.some((day) => events.some((e) => isSameDay(parseISO(e.start_time), day)));

    if (!hasAny) {
        return (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
                <p className="font-playfair text-xl text-muted-foreground/50">Nothing scheduled</p>
                <p className="text-sm font-inter text-muted-foreground/40">No events in this range.</p>
            </div>
        );
    }

    return (
        <div className="space-y-5">
            {days.map((day) => {
                const dayEvents = events.filter((event) => isSameDay(parseISO(event.start_time), day));
                if (!dayEvents.length) return null;
                return (
                    <div key={day.toISOString()} className="space-y-2">
                        {/* Date divider — matching InboxFeed group headers */}
                        <div className="flex items-center gap-3">
                            <span className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter shrink-0">
                                {isSameDay(day, new Date()) ? "Today" : format(day, "EEE, MMM d")}
                            </span>
                            <div className="flex-1 h-px bg-border/40" />
                        </div>
                        <div className="space-y-1.5">
                            {dayEvents.map((event) => (
                                <button
                                    key={event.id}
                                    onClick={() => onSelectEvent(event)}
                                    style={{ boxShadow: CARD_SHADOW }}
                                    className="w-full rounded-[12px] border border-border bg-white px-4 py-3 text-left hover:border-border/80 transition-colors"
                                >
                                    <div className="flex items-center justify-between gap-4">
                                        <span className="font-playfair text-[15px] font-semibold text-foreground">
                                            {event.title}
                                        </span>
                                        <span className="text-[11px] font-inter text-muted-foreground/60 shrink-0">
                                            {event.all_day
                                                ? "All day"
                                                : `${format(parseISO(event.start_time), "p")} – ${format(parseISO(event.end_time), "p")}`}
                                        </span>
                                    </div>
                                    {event.location && (
                                        <p className="text-[12px] font-inter text-muted-foreground/60 mt-0.5">{event.location}</p>
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

// ─── CALENDAR SETTINGS PANEL ─────────────────────────────────────────────────

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
        } catch (error: any) {
            toast.error(error?.message || "Failed to update settings");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div
            className="rounded-[14px] border border-border bg-white p-4 space-y-4"
            style={{ boxShadow: CARD_SHADOW }}
        >
            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                Settings
            </p>

            <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter">
                    Default calendar
                </label>
                <select
                    className="w-full rounded-[8px] border border-border bg-white px-3 py-2 text-sm font-inter text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
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
                    <p className="text-sm font-medium font-inter text-foreground">Auto-generate briefs</p>
                    <p className="text-[12px] font-inter text-muted-foreground/60 mt-0.5">1 hour before meetings</p>
                </div>
                <button
                    onClick={() => handleChange({ auto_briefing_enabled: !(settings?.auto_briefing_enabled ?? true) })}
                    className={cn(
                        "relative w-9 h-5 rounded-full transition-colors duration-200",
                        (settings?.auto_briefing_enabled ?? true) ? "bg-primary" : "bg-border"
                    )}
                >
                    <span className={cn(
                        "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200",
                        (settings?.auto_briefing_enabled ?? true) ? "translate-x-4" : "translate-x-0.5"
                    )} />
                </button>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter">
                    Briefing lead time (hours)
                </label>
                <Input
                    type="number"
                    min={1}
                    value={settings?.briefing_hours_before ?? 1}
                    onChange={(e) => handleChange({ briefing_hours_before: Number(e.target.value || 1) })}
                    disabled={saving}
                    className="rounded-[8px] border-border text-sm font-inter"
                />
            </div>
        </div>
    );
}

// ─── SUGGESTIONS PANEL ───────────────────────────────────────────────────────

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
    if (suggestions.length === 0) return null;

    return (
        <div
            className="rounded-[14px] border border-border bg-white p-4 space-y-4"
            style={{ boxShadow: CARD_SHADOW }}
        >
            <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                Scheduling suggestions
            </p>

            {suggestions.map((suggestion) => (
                <div key={suggestion.id} className="space-y-3">
                    <p className="text-sm font-semibold font-inter text-foreground">
                        {suggestion.meeting_type}
                        {suggestion.participants.length > 0 && (
                            <span className="font-normal text-muted-foreground"> with {suggestion.participants.join(", ")}</span>
                        )}
                    </p>

                    <div className="space-y-1.5">
                        {suggestion.suggested_slots.slice(0, 3).map((slot, idx) => (
                            <button
                                key={`${suggestion.id}-${idx}`}
                                onClick={() => onAccept(suggestion.id, idx)}
                                className="w-full rounded-[8px] bg-copper/[0.06] border border-copper/20 px-3 py-2 text-left text-[12px] font-inter text-copper hover:bg-copper/10 transition-colors"
                            >
                                {format(parseISO(slot.start_time), "EEE, MMM d · p")} – {format(parseISO(slot.end_time), "p")}
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => onSend(suggestion.id, suggestion.draft_reply || undefined)}
                            className="flex-1 py-1.5 rounded-[8px] bg-primary text-white text-[12px] font-medium font-inter hover:bg-primary/90 transition-colors"
                        >
                            Send availability
                        </button>
                        <button
                            onClick={() => onDismiss(suggestion.id)}
                            className="px-3 py-1.5 rounded-[8px] border border-border text-muted-foreground text-[12px] font-inter hover:bg-muted/40 transition-colors"
                        >
                            Dismiss
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

// ─── EVENT DIALOG ────────────────────────────────────────────────────────────

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
        Array.isArray(event?.participants)
            ? event?.participants.map((p) => (typeof p === "string" ? p : p.email || "")).filter(Boolean).join(", ")
            : ""
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
            Array.isArray(event?.participants)
                ? event?.participants.map((p) => (typeof p === "string" ? p : p.email || "")).filter(Boolean).join(", ")
                : ""
        );
        setAllDay(event?.all_day ?? false);
        setStartValue(getDateInputValue(event?.start_time, event?.all_day));
        setEndValue(getDateInputValue(event?.end_time, event?.all_day, event?.start_time));
    };

    useEffect(() => { reset(); }, [event?.id, open]);

    const handleSave = () => {
        const participantList = participants.split(",").map((p) => p.trim()).filter(Boolean);
        const timezone = settings?.default_timezone || "UTC";
        const { start_time, end_time } = buildTimes(startValue, endValue, allDay);
        const payload = {
            title, description: description || undefined, notes: notes || undefined,
            participants: participantList, all_day: allDay, timezone, location: location || undefined,
        };
        if (event) {
            onUpdate(event.id, { ...payload, start_time, end_time });
        } else {
            onCreate({ ...payload, start_time, end_time });
        }
    };

    return (
        <Dialog open={open} onOpenChange={(next) => { if (!next) reset(); onOpenChange(next); }}>
            <DialogContent className="max-w-xl">
                <DialogHeader>
                    <DialogTitle className="font-playfair text-xl">
                        {event ? "Edit event" : "New event"}
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-3">
                    <Input
                        placeholder="Event title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        className="font-inter text-sm rounded-[8px]"
                    />
                    <div className="grid grid-cols-2 gap-3">
                        <Input
                            type={allDay ? "date" : "datetime-local"}
                            value={startValue}
                            onChange={(e) => setStartValue(e.target.value)}
                            className="font-inter text-sm rounded-[8px]"
                        />
                        <Input
                            type={allDay ? "date" : "datetime-local"}
                            value={endValue}
                            onChange={(e) => setEndValue(e.target.value)}
                            className="font-inter text-sm rounded-[8px]"
                        />
                    </div>
                    <label className="flex items-center gap-2 text-sm font-inter text-muted-foreground cursor-pointer">
                        <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} className="rounded" />
                        All day
                    </label>
                    <Input placeholder="Location or link" value={location || ""} onChange={(e) => setLocation(e.target.value)} className="font-inter text-sm rounded-[8px]" />
                    <Input placeholder="Attendees (comma separated)" value={participants} onChange={(e) => setParticipants(e.target.value)} className="font-inter text-sm rounded-[8px]" />
                    <Textarea placeholder="Description (optional)" value={description || ""} onChange={(e) => setDescription(e.target.value)} className="font-inter text-sm rounded-[8px]" />
                    <Textarea placeholder="Internal notes (not synced)" value={notes || ""} onChange={(e) => setNotes(e.target.value)} className="font-inter text-sm rounded-[8px]" />

                    {/* Meeting brief */}
                    {event?.briefing && (
                        <div className="rounded-[12px] border border-border bg-linen/40 p-4 space-y-3">
                            <div className="flex items-center justify-between">
                                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground font-inter">
                                    Meeting brief
                                </p>
                                {event.briefing_generated_at && (
                                    <span className="text-[11px] text-muted-foreground/50 font-inter">
                                        {format(parseISO(event.briefing_generated_at), "MMM d, p")}
                                    </span>
                                )}
                            </div>

                            {event.briefing.agenda && event.briefing.agenda !== "No agenda provided" && (
                                <div>
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter mb-1">Agenda</p>
                                    <p className="text-sm font-inter text-foreground/80">{event.briefing.agenda}</p>
                                </div>
                            )}

                            {event.briefing.attendees && event.briefing.attendees.length > 0 && (
                                <div>
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter mb-1.5">Attendees</p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {event.briefing.attendees.map((a, i) => (
                                            <span key={i} className="px-2 py-0.5 rounded-full border border-border bg-white text-[12px] font-inter text-foreground/70">
                                                {a.name || a.email}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {event.briefing.related_emails && event.briefing.related_emails.length > 0 && (
                                <div>
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter mb-1.5">
                                        Related emails {event.briefing.message_count > 3 && `(${event.briefing.message_count})`}
                                    </p>
                                    <div className="space-y-1.5">
                                        {event.briefing.related_emails.slice(0, 3).map((e, i) => (
                                            <div key={i} className="rounded-[8px] border border-border bg-white p-2.5">
                                                <p className="text-[12px] font-semibold font-inter text-foreground">{e.subject}</p>
                                                {e.sender && <p className="text-[11px] font-inter text-muted-foreground/60">{e.sender}</p>}
                                                {e.summary && <p className="text-[11px] font-inter text-muted-foreground/70 mt-0.5">{e.summary}</p>}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {event.briefing.open_tasks && event.briefing.open_tasks.length > 0 && (
                                <div>
                                    <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground/60 font-inter mb-1.5">
                                        Open tasks {event.briefing.task_count > 3 && `(${event.briefing.task_count})`}
                                    </p>
                                    <ul className="space-y-1">
                                        {event.briefing.open_tasks.map((t, i) => (
                                            <li key={i} className="flex items-center gap-2 text-[12px] font-inter text-foreground/80">
                                                <span className="w-1.5 h-1.5 rounded-full bg-primary/40 shrink-0" />
                                                <span>{t.title}</span>
                                                {t.priority && t.priority !== "normal" && (
                                                    <span className={cn(
                                                        "text-[10px] px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wide",
                                                        (t.priority === "urgent" || t.priority === "high")
                                                            ? "bg-primary/10 text-primary"
                                                            : "bg-muted text-muted-foreground"
                                                    )}>
                                                        {t.priority}
                                                    </span>
                                                )}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {event.briefing.prep_warnings && event.briefing.prep_warnings.length > 0 && (
                                <div className="rounded-[8px] border border-copper/20 bg-copper/[0.06] p-3">
                                    <div className="flex items-center gap-1.5 mb-1">
                                        <AlertTriangle size={11} className="text-copper" />
                                        <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-copper font-inter">Prep warnings</p>
                                    </div>
                                    <ul className="space-y-0.5">
                                        {event.briefing.prep_warnings.map((w, i) => (
                                            <li key={i} className="text-[12px] font-inter text-copper/80">{w}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {event.briefing.prep_complete && (
                                <div className="flex items-center gap-1.5">
                                    <CheckCircle2 size={13} className="text-sage" />
                                    <p className="text-[12px] font-inter text-sage font-medium">Prep complete</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div className="mt-4 flex items-center justify-between">
                    {event ? (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => onGenerateBrief(event.id)}
                                className="px-3 py-1.5 rounded-[8px] border border-border text-[13px] font-inter text-muted-foreground hover:bg-muted/40 transition-colors"
                            >
                                Generate brief
                            </button>
                            <button
                                onClick={() => onDelete(event.id)}
                                className="px-3 py-1.5 rounded-[8px] border border-destructive/30 text-[13px] font-inter text-destructive hover:bg-destructive/5 transition-colors"
                            >
                                Delete
                            </button>
                        </div>
                    ) : <div />}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => onOpenChange(false)}
                            className="px-3 py-1.5 rounded-[8px] border border-border text-[13px] font-inter text-muted-foreground hover:bg-muted/40 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={!title.trim()}
                            className="px-3 py-1.5 rounded-[8px] bg-primary text-white text-[13px] font-medium font-inter hover:bg-primary/90 disabled:opacity-40 transition-colors"
                        >
                            Save
                        </button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

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
